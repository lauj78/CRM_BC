from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from datetime import timedelta
from django.utils import timezone
import calendar
from data_management.models import Transaction

@login_required
def report_dairy_summary_view(request):
    today = timezone.now().date()
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # Default to 30 days if no dates provided
    if not start_date or not end_date:
        start_date = today - timedelta(days=30)
        end_date = today
    else:
        start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()

    print(f"Start date type: {type(start_date)}, value: {start_date}")  # Debug
    print(f"End date type: {type(end_date)}, value: {end_date}")  # Debug

    # Prepare data for the selected date range
    dashboard_data = []
    current_date = start_date
    while current_date <= end_date:
        print(f"Current date type: {type(current_date)}, value: {current_date}")  # Debug
        day_transactions = Transaction.objects.filter(process_date__date=current_date)
        
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

    return render(request, 'report_app/reports/report_dairy_summary/view.html', {
        'members': dashboard_data,
        'start_date': start_date.strftime('%Y-%m-%d'),  # Convert to string for template
        'end_date': end_date.strftime('%Y-%m-%d'),      # Convert to string for template
    })