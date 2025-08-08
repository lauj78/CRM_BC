import csv
import io
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Max, Sum
from django.utils import timezone
from django.http import HttpResponse, HttpResponseBadRequest
from data_management.models import Transaction
from django.template.response import TemplateResponse
import json

@login_required
def report_inactive_users_view(request):
    today = timezone.now().date()
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # Default dates for the filter form as date objects (30 days from today)
    start_date_default = today - timezone.timedelta(days=30)
    end_date_default = today

    # Use GET parameters for initial display
    if not start_date or not end_date:
        start_date = start_date_default
        end_date = end_date_default
    else:
        start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()

    # Get the latest transaction date per username within the date range
    latest_transactions = Transaction.objects.filter(
        process_date__date__range=[start_date, end_date]
    ).values('username').annotate(last_activity=Max('process_date__date'))

    # Identify all users (no 7-day threshold)
    inactive_users = []
    for lt in latest_transactions:
        username = lt['username']
        last_activity = lt['last_activity']
        days_inactive = (today - last_activity).days

        deposits = Transaction.objects.filter(
            username=username, event__in=['Deposit', 'Manual Deposit'],
            process_date__date__range=[start_date, end_date]
        ).aggregate(total_deposits=Sum('amount'))['total_deposits'] or 0
        withdrawals = Transaction.objects.filter(
            username=username, event__in=['Withdraw', 'Manual Withdraw'],
            process_date__date__range=[start_date, end_date]
        ).aggregate(total_withdrawals=Sum('amount'))['total_withdrawals'] or 0

        inactive_users.append({
            'username': username,
            'last_activity': last_activity,
            'total_deposits': deposits,
            'total_withdrawals': withdrawals,
            'days_inactive': days_inactive,
        })

    # Sort by days inactive
    inactive_users.sort(key=lambda x: x['days_inactive'], reverse=True)

    # Handle POST request for export
    if request.method == 'POST' and request.POST.get('_export', '').lower() == 'csv':
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')
        try:
            if not start_date_str or not end_date_str:
                return HttpResponseBadRequest("Please set valid start and end dates.")
            start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            if start_date > end_date:
                return HttpResponseBadRequest("Start date must be before or equal to end date.")
        except ValueError:
            return HttpResponseBadRequest("Invalid date format. Use YYYY-MM-DD.")

        # Prepare data for export (no 7-day threshold)
        latest_transactions = Transaction.objects.filter(
            process_date__date__range=[start_date, end_date]
        ).values('username').annotate(last_activity=Max('process_date__date'))
        export_users = []
        for lt in latest_transactions:
            username = lt['username']
            last_activity = lt['last_activity']
            days_inactive = (today - last_activity).days

            deposits = Transaction.objects.filter(
                username=username, event__in=['Deposit', 'Manual Deposit'],
                process_date__date__range=[start_date, end_date]
            ).aggregate(total_deposits=Sum('amount'))['total_deposits'] or 0
            withdrawals = Transaction.objects.filter(
                username=username, event__in=['Withdraw', 'Manual Withdraw'],
                process_date__date__range=[start_date, end_date]
            ).aggregate(total_withdrawals=Sum('amount'))['total_withdrawals'] or 0

            export_users.append({
                'username': username,
                'last_activity': last_activity,
                'total_deposits': deposits,
                'total_withdrawals': withdrawals,
                'days_inactive': days_inactive,
            })
        export_users.sort(key=lambda x: x['days_inactive'], reverse=True)

        # Convert export data to CSV content
        csv_content = io.StringIO()
        writer = csv.writer(csv_content)
        writer.writerow(['Username', 'Last Activity', 'Total Deposits', 'Total Withdrawals', 'Days Inactive'])
        for user in export_users:
            writer.writerow([
                user['username'],
                user['last_activity'].strftime('%Y-%m-%d'),
                user['total_deposits'],
                user['total_withdrawals'],
                user['days_inactive']
            ])
        csv_data = csv_content.getvalue()
        csv_content.close()

        # Render template with CSV data for JavaScript download
        context = {
            'inactive_users': export_users,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'start_date_default': start_date_default,
            'end_date_default': end_date_default,
            'csv_data': csv_data,
            'filename': f"inactive_users_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.csv"
        }
        return TemplateResponse(request, 'report_app/reports/report_inactive_users/view.html', {'context_data': context})

    # Handle GET request for export
    if request.method == 'GET' and request.GET.get('_export', '').lower() == 'csv':
        try:
            if not start_date or not end_date:
                return HttpResponseBadRequest("Please set valid start and end dates.")
            if start_date > end_date:
                return HttpResponseBadRequest("Start date must be before or equal to end date.")
        except ValueError:
            return HttpResponseBadRequest("Invalid date format. Use YYYY-MM-DD.")

        # Generate CSV content
        csv_content = io.StringIO()
        writer = csv.writer(csv_content)
        writer.writerow(['Username', 'Last Activity', 'Total Deposits', 'Total Withdrawals', 'Days Inactive'])
        for user in inactive_users:
            writer.writerow([
                user['username'],
                user['last_activity'].strftime('%Y-%m-%d'),
                user['total_deposits'],
                user['total_withdrawals'],
                user['days_inactive']
            ])
        csv_data = csv_content.getvalue()
        csv_content.close()

        # Render template with CSV data for JavaScript download
        context = {
            'inactive_users': inactive_users,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'start_date_default': start_date_default,
            'end_date_default': end_date_default,
            'csv_data': csv_data,
            'filename': f"inactive_users_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.csv"
        }
        return TemplateResponse(request, 'report_app/reports/report_inactive_users/view.html', {'context_data': context})

    # Render the template for GET request (non-export)
    context = {
        'inactive_users': inactive_users,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'start_date_default': start_date_default,
        'end_date_default': end_date_default,
    }
    return TemplateResponse(request, 'report_app/reports/report_inactive_users/view.html', {'context_data': context})