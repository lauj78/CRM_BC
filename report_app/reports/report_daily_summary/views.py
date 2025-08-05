from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from datetime import timedelta
from django.utils import timezone
import calendar
from data_management.models import Transaction, Member
from django.template.response import TemplateResponse

@login_required
# The function signature is modified to accept 'tenant_id'.
# This is required because the parent view ('report_hub_view') will pass it.
def report_daily_summary_view(request, tenant_id):
    """
    Generates a daily summary report for a specific tenant.
    The tenant_id is received from the URL and used by the middleware
    to switch the database connection.
    """
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

    # Prepare data for the selected date range
    dashboard_data = []
    current_date = start_date
    while current_date <= end_date:
        # These queries automatically use the correct tenant's database
        # because the TenantMiddleware has already handled the connection.
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
        
        # New Metrics
        new_members = Member.objects.filter(join_date__date=current_date).count()  # Compare date only
        new_member_usernames = Member.objects.filter(join_date__date=current_date).values('username')
        new_member_deposited = day_transactions.filter(
            event__in=['Deposit', 'Manual Deposit'],
            username__in=new_member_usernames
        ).distinct().count()
        old_player = max(0, active_players - new_member_deposited)  # Avoid negative values

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
            'new_member': new_members,
            'new_member_deposited': new_member_deposited,
            'old_player': old_player,
        })
        current_date += timedelta(days=1)

    context = {
        'members': dashboard_data,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'start_date_default': start_date_default,
        'end_date_default': end_date_default,
    }
    return TemplateResponse(request, 'report_app/reports/report_daily_summary/view.html', {'context_data': context})