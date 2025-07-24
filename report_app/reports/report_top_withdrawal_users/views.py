import csv
import io
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Max, Sum
from django.utils import timezone
from django.http import HttpResponseBadRequest
from data_management.models import Transaction
from django.template.response import TemplateResponse

@login_required
def report_top_withdrawal_users_view(request):
    print(f"Received GET params: start_date={request.GET.get('start_date')}, end_date={request.GET.get('end_date')}, top_n={request.GET.get('top_n')}")
    today = timezone.now().date()
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    top_n = request.GET.get('top_n')

    # Default dates (30 days from today)
    start_date_default = today - timezone.timedelta(days=30)
    end_date_default = today

    # Use GET parameters if provided, otherwise use defaults
    if not start_date or not end_date:
        print(f"Using defaults: start_date={start_date_default}, end_date={end_date_default}")
        start_date = start_date_default
        end_date = end_date_default
    else:
        try:
            print(f"Parsing dates: start_date={start_date}, end_date={end_date}")
            start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return HttpResponseBadRequest("Invalid date format. Use YYYY-MM-DD.")

    # Validate date range
    if start_date > end_date:
        return HttpResponseBadRequest("Start date must be before or equal to end date.")

    # Parse top_n (default to 100)
    try:
        print(f"Parsing top_n: {top_n}")
        top_n = int(top_n) if top_n and int(top_n) > 0 else 100
    except ValueError:
        print(f"Invalid top_n, using default: 100")
        top_n = 100

    # Query transactions for Withdraw only (ranking metric)
    withdrawal_users = Transaction.objects.filter(
        event='Withdraw',
        process_date__date__range=[start_date, end_date]
    ).values('username').annotate(
        total_withdrawals=Sum('amount'),
        withdrawal_frequency=Sum(1),  # Count of Withdraw transactions
        largest_withdrawal=Max('amount')
    )
    print(f"Found {withdrawal_users.count()} withdrawal users for range {start_date} to {end_date}")

    # Prepare data for display
    report_top_withdrawal_users = []
    for user in withdrawal_users:
        username = user['username']
        # Fetch additional transaction data within the same range
        deposits = Transaction.objects.filter(
            username=username, event__in=['Deposit', 'Manual Deposit'],
            process_date__date__range=[start_date, end_date]
        ).aggregate(total_deposits=Sum('amount'))['total_deposits'] or 0
        deposit_freq = Transaction.objects.filter(
            username=username, event__in=['Deposit', 'Manual Deposit'],
            process_date__date__range=[start_date, end_date]
        ).count()
        manual_withdrawals = Transaction.objects.filter(
            username=username, event='Manual Withdraw',
            process_date__date__range=[start_date, end_date]
        ).aggregate(total_manual_withdrawals=Sum('amount'))['total_manual_withdrawals'] or 0
        manual_withdrawal_freq = Transaction.objects.filter(
            username=username, event='Manual Withdraw',
            process_date__date__range=[start_date, end_date]
        ).count()
        manual_deposits = Transaction.objects.filter(
            username=username, event='Manual Deposit',
            process_date__date__range=[start_date, end_date]
        ).aggregate(total_manual_deposits=Sum('amount'))['total_manual_deposits'] or 0

        # Calculate average withdrawal (handle division by zero)
        average_withdrawal = user['total_withdrawals'] / user['withdrawal_frequency'] if user['withdrawal_frequency'] else 0

        # Approximate last login date as latest transaction
        last_login = Transaction.objects.filter(
            username=username
        ).aggregate(last_login=Max('process_date'))['last_login']

        report_top_withdrawal_users.append({
            'username': username,
            'total_withdrawals': user['total_withdrawals'] or 0,
            'withdrawal_frequency': user['withdrawal_frequency'],
            'average_withdrawal': average_withdrawal,
            'largest_withdrawal': user['largest_withdrawal'] or 0,
            'total_manual_withdrawals': manual_withdrawals,
            'manual_withdrawal_freq': manual_withdrawal_freq,
            'total_deposits': deposits,
            'deposit_freq': deposit_freq,
            'total_manual_deposits': manual_deposits,
            'last_login': last_login.date() if last_login else None,
        })

    # Sort by total withdrawals and limit to top_n
    report_top_withdrawal_users.sort(key=lambda x: x['total_withdrawals'] or 0, reverse=True)
    report_top_withdrawal_users = report_top_withdrawal_users[:top_n]

    # Handle POST request for export
    if request.method == 'POST' and request.POST.get('_export', '').lower() == 'csv':
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')
        top_n_str = request.POST.get('top_n')
        try:
            if not start_date_str or not end_date_str:
                return HttpResponseBadRequest("Please set valid start and end dates.")
            start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            if start_date > end_date:
                return HttpResponseBadRequest("Start date must be before or equal to end date.")
            top_n = int(top_n_str) if top_n_str and int(top_n_str) > 0 else 100
        except ValueError:
            return HttpResponseBadRequest("Invalid date or top_n format. Use YYYY-MM-DD for dates and a positive integer for top_n.")

        # Query transactions for Withdraw only (ranking metric) for export
        withdrawal_users = Transaction.objects.filter(
            event='Withdraw',
            process_date__date__range=[start_date, end_date]
        ).values('username').annotate(
            total_withdrawals=Sum('amount'),
            withdrawal_frequency=Sum(1),
            largest_withdrawal=Max('amount')
        )
        export_users = []
        for user in withdrawal_users:
            username = user['username']
            deposits = Transaction.objects.filter(
                username=username, event__in=['Deposit', 'Manual Deposit'],
                process_date__date__range=[start_date, end_date]
            ).aggregate(total_deposits=Sum('amount'))['total_deposits'] or 0
            deposit_freq = Transaction.objects.filter(
                username=username, event__in=['Deposit', 'Manual Deposit'],
                process_date__date__range=[start_date, end_date]
            ).count()
            manual_withdrawals = Transaction.objects.filter(
                username=username, event='Manual Withdraw',
                process_date__date__range=[start_date, end_date]
            ).aggregate(total_manual_withdrawals=Sum('amount'))['total_manual_withdrawals'] or 0
            manual_withdrawal_freq = Transaction.objects.filter(
                username=username, event='Manual Withdraw',
                process_date__date__range=[start_date, end_date]
            ).count()
            manual_deposits = Transaction.objects.filter(
                username=username, event='Manual Deposit',
                process_date__date__range=[start_date, end_date]
            ).aggregate(total_manual_deposits=Sum('amount'))['total_manual_deposits'] or 0

            average_withdrawal = user['total_withdrawals'] / user['withdrawal_frequency'] if user['withdrawal_frequency'] else 0
            last_login = Transaction.objects.filter(
                username=username
            ).aggregate(last_login=Max('process_date'))['last_login']

            export_users.append({
                'username': username,
                'total_withdrawals': user['total_withdrawals'] or 0,
                'withdrawal_frequency': user['withdrawal_frequency'],
                'average_withdrawal': average_withdrawal,
                'largest_withdrawal': user['largest_withdrawal'] or 0,
                'total_manual_withdrawals': manual_withdrawals,
                'manual_withdrawal_freq': manual_withdrawal_freq,
                'total_deposits': deposits,
                'deposit_freq': deposit_freq,
                'total_manual_deposits': manual_deposits,
                'last_login': last_login.date() if last_login else None,
            })

        export_users.sort(key=lambda x: x['total_withdrawals'] or 0, reverse=True)
        export_users = export_users[:top_n]

        # Generate CSV content
        csv_content = io.StringIO()
        writer = csv.writer(csv_content)
        writer.writerow([
            'Username', 'Total Withdrawals', 'Total Withdrawal Frequency', 'Average Withdrawal',
            'Largest Withdrawal Value', 'Total Manual Withdrawals', 'Total Manual Withdrawal Frequency',
            'Total Deposits', 'Total Deposit Frequency', 'Total Manual Deposits', 'Last Login Date'
        ])
        for user in export_users:
            writer.writerow([
                user['username'],
                user['total_withdrawals'],
                user['withdrawal_frequency'],
                user['average_withdrawal'],
                user['largest_withdrawal'],
                user['total_manual_withdrawals'],
                user['manual_withdrawal_freq'],
                user['total_deposits'],
                user['deposit_freq'],
                user['total_manual_deposits'],
                user['last_login'].strftime('%Y-%m-%d') if user['last_login'] else ''
            ])
        csv_data = csv_content.getvalue()
        csv_content.close()

        # Render template with CSV data
        context = {
            'report_top_withdrawal_users': export_users,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'start_date_default': start_date_default,
            'end_date_default': end_date_default,
            'top_n': top_n,
            'csv_data': csv_data,
            'filename': f"report_top_withdrawal_users_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.csv"
        }
        return TemplateResponse(request, 'report_app/reports/report_top_withdrawal_users/view.html', {'context_data': context})

    # Handle GET request for export
    if request.method == 'GET' and request.GET.get('_export', '').lower() == 'csv':
        try:
            if start_date > end_date:
                return HttpResponseBadRequest("Start date must be before or equal to end date.")
        except ValueError:
            return HttpResponseBadRequest("Invalid date format. Use YYYY-MM-DD.")

        # Generate CSV content
        csv_content = io.StringIO()
        writer = csv.writer(csv_content)
        writer.writerow([
            'Username', 'Total Withdrawals', 'Total Withdrawal Frequency', 'Average Withdrawal',
            'Largest Withdrawal Value', 'Total Manual Withdrawals', 'Total Manual Withdrawal Frequency',
            'Total Deposits', 'Total Deposit Frequency', 'Total Manual Deposits', 'Last Login Date'
        ])
        for user in report_top_withdrawal_users:
            writer.writerow([
                user['username'],
                user['total_withdrawals'],
                user['withdrawal_frequency'],
                user['average_withdrawal'],
                user['largest_withdrawal'],
                user['total_manual_withdrawals'],
                user['manual_withdrawal_freq'],
                user['total_deposits'],
                user['deposit_freq'],
                user['total_manual_deposits'],
                user['last_login'].strftime('%Y-%m-%d') if user['last_login'] else ''
            ])
        csv_data = csv_content.getvalue()
        csv_content.close()

        # Render template with CSV data
        context = {
            'report_top_withdrawal_users': report_top_withdrawal_users,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'start_date_default': start_date_default,
            'end_date_default': end_date_default,
            'top_n': top_n,
            'csv_data': csv_data,
            'filename': f"report_top_withdrawal_users_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.csv"
        }
        return TemplateResponse(request, 'report_app/reports/report_top_withdrawal_users/view.html', {'context_data': context})

    # Render the template for GET request (non-export)
    context = {
        'report_top_withdrawal_users': report_top_withdrawal_users,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'start_date_default': start_date_default,
        'end_date_default': end_date_default,
        'top_n': top_n,
    }
    return TemplateResponse(request, 'report_app/reports/report_top_withdrawal_users/view.html', {'context_data': context})