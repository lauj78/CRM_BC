from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from datetime import timedelta
from django.utils import timezone
import calendar
from data_management.models import Transaction
from django.template.response import TemplateResponse

@login_required
def report_daily_summary_view(request):
    today = timezone.now().date()
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # Default dates for the filter form as date objects
    start_date_default = today - timedelta(days=30)
    end_date_default = today

    # Use GET parameters if provided, otherwise use defaults
    if not start_date or not end_date:
        start_date = start_date_default
        end_date = end_date_default
    else:
        start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()

    # print(f"Debug - Start date: {start_date}, Type: {type(start_date)}")  # Debug
    # print(f"Debug - End date: {end_date}, Type: {type(end_date)}")  # Debug
    # print(f"Debug - Start date default: {start_date_default}, Type: {type(start_date_default)}")  # Debug
    # print(f"Debug - End date default: {end_date_default}, Type: {type(end_date_default)}")  # Debug

    # Prepare data for the selected date range
    dashboard_data = []
    current_date = start_date
    while current_date <= end_date:
        #print(f"Debug - Processing date: {current_date}, Type: {type(current_date)}")  # Debug
        day_transactions = Transaction.objects.filter(process_date__date=current_date)
        #print(f"Debug - Transactions for {current_date}: {day_transactions.count()}")  # Debug

        # Section: Total Form Depo
        depo_trx = day_transactions.filter(event='Deposit').count()
        manual_trx = day_transactions.filter(event='Manual Deposit').count()
        total_trx = depo_trx + manual_trx
        
        # Section: Total Coin Depo
        depo_value = day_transactions.filter(event='Deposit').aggregate(total=Sum('amount'))['total'] or 0
        manual_value = day_transactions.filter(event='Manual Deposit').aggregate(total=Sum('amount'))['total'] or 0
        total_value = depo_value + manual_value
        
        # Section: Total Form WD
        wd_trx = day_transactions.filter(event='Withdraw').count()
        manual_wd_trx = day_transactions.filter(event='Manual Withdraw').count()
        total_wd = wd_trx + manual_wd_trx
        
        # Section: Total Coin WD
        wd_value = day_transactions.filter(event='Withdraw').aggregate(total=Sum('amount'))['total'] or 0
        manual_wd_value = day_transactions.filter(event='Manual Withdraw').aggregate(total=Sum('amount'))['total'] or 0
        total_wd_value = wd_value + manual_wd_value
        
        # Section: Other Index
        active_players = day_transactions.filter(event__in=['Deposit', 'Manual Deposit']).values('username').distinct().count()
        
        dashboard_data.append({
            'date': current_date,
            'day': calendar.day_name[current_date.weekday()],
            'depo_trx': depo_trx,
            'manual_trx': manual_trx,
            'total_trx': total_trx,
            'depo_value': depo_value,
            'manual_value': manual_value,
            'total_value': total_value,
            'wd_trx': wd_trx,
            'manual_wd_trx': manual_wd_trx,
            'total_wd': total_wd,
            'wd_value': wd_value,
            'manual_wd_value': manual_wd_value,
            'total_wd_value': total_wd_value,
            'active_players': active_players,
        })
        current_date += timedelta(days=1)

    # print(f"Debug - Dashboard data length: {len(dashboard_data)}")  # Debug total rows
    context = {
        'members': dashboard_data,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'start_date_default': start_date_default,
        'end_date_default': end_date_default,
    }
    return TemplateResponse(request, 'report_app/reports/report_daily_summary/view.html', {'context_data': context})