#report/report_inactive_users/views.py
import csv
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Max, Sum
from django.utils import timezone
from django.http import HttpResponse
from data_management.models import Transaction
from django.template.response import TemplateResponse

@login_required
def report_inactive_users_view(request):
    today = timezone.now().date()
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # Default dates for the filter form as date objects (30 days from today)
    start_date_default = today - timezone.timedelta(days=30)
    end_date_default = today

    # Use GET parameters if provided, otherwise use defaults
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

    # Identify inactive users
    inactive_users = []
    for lt in latest_transactions:
        username = lt['username']
        last_activity = lt['last_activity']
        days_inactive = (today - last_activity).days

        if days_inactive >= 7:
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

    # Handle export to CSV
    if request.GET.get('_export', '').lower() == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="inactive_users_{start_date.strftime("%Y%m%d")}_to_{end_date.strftime("%Y%m%d")}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Username', 'Last Activity', 'Total Deposits', 'Total Withdrawals', 'Days Inactive'])
        for user in inactive_users:
            writer.writerow([
                user['username'],
                user['last_activity'].strftime('%Y-%m-%d'),  # Ensure date format for CSV
                user['total_deposits'],
                user['total_withdrawals'],
                user['days_inactive']
            ])
        return response

    # Render the template for normal view
    context = {
        'inactive_users': inactive_users,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'start_date_default': start_date_default,
        'end_date_default': end_date_default,
    }
    return TemplateResponse(request, 'report_app/reports/report_inactive_users/view.html', {'context_data': context})