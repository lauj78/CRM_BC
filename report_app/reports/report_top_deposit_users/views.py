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
def report_top_deposit_users_view(request):
    today = timezone.now().date()
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    top_n = request.GET.get('top_n')

    # Default dates (30 days from today)
    start_date_default = today - timezone.timedelta(days=30)
    end_date_default = today

    # Use GET parameters if provided, otherwise use defaults
    if not start_date or not end_date:
        start_date = start_date_default
        end_date = end_date_default
    else:
        try:
            start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return HttpResponseBadRequest("Invalid date format. Use YYYY-MM-DD.")

    # Validate date range
    if start_date > end_date:
        return HttpResponseBadRequest("Start date must be before or equal to end date.")

    # Parse top_n (default to 100)
    try:
        top_n = int(top_n) if top_n and int(top_n) > 0 else 100
    except ValueError:
        top_n = 100

    # Query transactions
    deposit_users = Transaction.objects.filter(
        event='Deposit',
        process_date__date__range=[start_date, end_date]
    ).values('username').annotate(
        total_deposits=Sum('amount'),
        deposit_frequency=Sum(1),  # Count of Deposit transactions
        largest_deposit=Max('amount')
    )

    # Prepare data for display
    report_top_deposit_users = []
    for user in deposit_users:
        username = user['username']
        # Fetch additional transaction data within the same range
        manual_deposits = Transaction.objects.filter(
            username=username, event='Manual Deposit',
            process_date__date__range=[start_date, end_date]
        ).aggregate(total_manual_deposits=Sum('amount'))['total_manual_deposits'] or 0
        manual_deposit_freq = Transaction.objects.filter(
            username=username, event='Manual Deposit',
            process_date__date__range=[start_date, end_date]
        ).count()
        withdrawals = Transaction.objects.filter(
            username=username, event='Withdraw',
            process_date__date__range=[start_date, end_date]
        ).aggregate(total_withdrawals=Sum('amount'))['total_withdrawals'] or 0
        withdrawal_freq = Transaction.objects.filter(
            username=username, event='Withdraw',
            process_date__date__range=[start_date, end_date]
        ).count()
        manual_withdrawals = Transaction.objects.filter(
            username=username, event='Manual Withdraw',
            process_date__date__range=[start_date, end_date]
        ).aggregate(total_manual_withdrawals=Sum('amount'))['total_manual_withdrawals'] or 0

        # Calculate average deposit (handle division by zero)
        average_deposit = user['total_deposits'] / user['deposit_frequency'] if user['deposit_frequency'] else 0

        # Approximate last login date as latest transaction
        last_login = Transaction.objects.filter(
            username=username
        ).aggregate(last_login=Max('process_date'))['last_login']

        report_top_deposit_users.append({
            'username': username,
            'total_deposits': user['total_deposits'] or 0,
            'deposit_frequency': user['deposit_frequency'],
            'average_deposit': average_deposit,
            'largest_deposit': user['largest_deposit'] or 0,
            'total_manual_deposits': manual_deposits,
            'manual_deposit_freq': manual_deposit_freq,
            'total_withdrawals': withdrawals,
            'withdrawal_freq': withdrawal_freq,
            'total_manual_withdrawals': manual_withdrawals,
            'last_login': last_login.date() if last_login else None,
        })

    # Sort by total deposits and limit to top_n
    report_top_deposit_users.sort(key=lambda x: x['total_deposits'] or 0, reverse=True)
    report_top_deposit_users = report_top_deposit_users[:top_n]

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

        # Recalculate data for export
        deposit_users = Transaction.objects.filter(
            event='Deposit',
            process_date__date__range=[start_date, end_date]
        ).values('username').annotate(
            total_deposits=Sum('amount'),
            deposit_frequency=Sum(1),
            largest_deposit=Max('amount')
        )
        export_users = []
        for user in deposit_users:
            username = user['username']
            manual_deposits = Transaction.objects.filter(
                username=username, event='Manual Deposit',
                process_date__date__range=[start_date, end_date]
            ).aggregate(total_manual_deposits=Sum('amount'))['total_manual_deposits'] or 0
            manual_deposit_freq = Transaction.objects.filter(
                username=username, event='Manual Deposit',
                process_date__date__range=[start_date, end_date]
            ).count()
            withdrawals = Transaction.objects.filter(
                username=username, event='Withdraw',
                process_date__date__range=[start_date, end_date]
            ).aggregate(total_withdrawals=Sum('amount'))['total_withdrawals'] or 0
            withdrawal_freq = Transaction.objects.filter(
                username=username, event='Withdraw',
                process_date__date__range=[start_date, end_date]
            ).count()
            manual_withdrawals = Transaction.objects.filter(
                username=username, event='Manual Withdraw',
                process_date__date__range=[start_date, end_date]
            ).aggregate(total_manual_withdrawals=Sum('amount'))['total_manual_withdrawals'] or 0

            average_deposit = user['total_deposits'] / user['deposit_frequency'] if user['deposit_frequency'] else 0
            last_login = Transaction.objects.filter(
                username=username
            ).aggregate(last_login=Max('process_date'))['last_login']

            export_users.append({
                'username': username,
                'total_deposits': user['total_deposits'] or 0,
                'deposit_frequency': user['deposit_frequency'],
                'average_deposit': average_deposit,
                'largest_deposit': user['largest_deposit'] or 0,
                'total_manual_deposits': manual_deposits,
                'manual_deposit_freq': manual_deposit_freq,
                'total_withdrawals': withdrawals,
                'withdrawal_freq': withdrawal_freq,
                'total_manual_withdrawals': manual_withdrawals,
                'last_login': last_login.date() if last_login else None,
            })

        export_users.sort(key=lambda x: x['total_deposits'] or 0, reverse=True)
        export_users = export_users[:top_n]

        # Generate CSV content
        csv_content = io.StringIO()
        writer = csv.writer(csv_content)
        writer.writerow([
            'Username', 'Total Deposits', 'Total Deposit Frequency', 'Average Deposit',
            'Largest Deposit Value', 'Total Manual Deposits', 'Total Manual Deposit Frequency',
            'Total Withdrawals', 'Total Withdrawal Frequency', 'Total Manual Withdrawals', 'Last Login Date'
        ])
        for user in export_users:
            writer.writerow([
                user['username'],
                user['total_deposits'],
                user['deposit_frequency'],
                user['average_deposit'],
                user['largest_deposit'],
                user['total_manual_deposits'],
                user['manual_deposit_freq'],
                user['total_withdrawals'],
                user['withdrawal_freq'],
                user['total_manual_withdrawals'],
                user['last_login'].strftime('%Y-%m-%d') if user['last_login'] else ''
            ])
        csv_data = csv_content.getvalue()
        csv_content.close()

        # Render template with CSV data
        context = {
            'report_top_deposit_users': export_users,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'start_date_default': start_date_default,
            'end_date_default': end_date_default,
            'top_n': top_n,
            'csv_data': csv_data,
            'filename': f"report_top_deposit_users_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.csv"
        }
        return TemplateResponse(request, 'report_app/reports/report_top_deposit_users/view.html', {'context_data': context})

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
            'Username', 'Total Deposits', 'Total Deposit Frequency', 'Average Deposit',
            'Largest Deposit Value', 'Total Manual Deposits', 'Total Manual Deposit Frequency',
            'Total Withdrawals', 'Total Withdrawal Frequency', 'Total Manual Withdrawals', 'Last Login Date'
        ])
        for user in report_top_deposit_users:
            writer.writerow([
                user['username'],
                user['total_deposits'],
                user['deposit_frequency'],
                user['average_deposit'],
                user['largest_deposit'],
                user['total_manual_deposits'],
                user['manual_deposit_freq'],
                user['total_withdrawals'],
                user['withdrawal_freq'],
                user['total_manual_withdrawals'],
                user['last_login'].strftime('%Y-%m-%d') if user['last_login'] else ''
            ])
        csv_data = csv_content.getvalue()
        csv_content.close()

        # Render template with CSV data
        context = {
            'report_top_deposit_users': report_top_deposit_users,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'start_date_default': start_date_default,
            'end_date_default': end_date_default,
            'top_n': top_n,
            'csv_data': csv_data,
            'filename': f"report_top_deposit_users_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.csv"
        }
        return TemplateResponse(request, 'report_app/reports/report_top_deposit_users/view.html', {'context_data': context})

    # Render the template for GET request (non-export)
    context = {
        'report_top_deposit_users': report_top_deposit_users,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'start_date_default': start_date_default,
        'end_date_default': end_date_default,
        'top_n': top_n,
    }
    return TemplateResponse(request, 'report_app/reports/report_top_deposit_users/view.html', {'context_data': context})