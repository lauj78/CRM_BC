from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from datetime import timedelta
from django.utils import timezone
import calendar
from data_management.models import Transaction, Member
from django.template.response import TemplateResponse
from collections import Counter, defaultdict

@login_required
def report_daily_general_transaction_summary_view(request, tenant_id):
    """
    Generates a daily summary report focused on deposit frequency, user age, and transaction values.
    """
    today = timezone.now().date()
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    # Default dates for the filter form
    start_date_default = today - timedelta(days=15)
    end_date_default = today

    # Use GET parameters if provided, otherwise use defaults
    if not start_date_str or not end_date_str:
        start_date = start_date_default
        end_date = end_date_default
    else:
        start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date()


    # Pre-fetch all unique depositor usernames for the entire date range to optimize member queries
    all_deposits = Transaction.objects.filter(
        process_date__date__range=(start_date, end_date),
        event__in=['Deposit']
    )
    all_depositor_usernames = set(all_deposits.values_list('username', flat=True).distinct())
    
    # Fetch all relevant members at once with proper error handling
    depositor_members = {}
    if all_depositor_usernames:
        members_qs = Member.objects.filter(username__in=all_depositor_usernames).select_related()
        depositor_members = {m.username: m for m in members_qs}
        
    def get_percentage(count, total):
        return (count / total) * 100 if total > 0 else 0

    report_data = []
    current_date = start_date
    
    while current_date <= end_date:
        # Get daily transactions
        daily_deposits = Transaction.objects.filter(
            process_date__date=current_date,
            event__in=['Deposit']
        )
        daily_withdrawals = Transaction.objects.filter(
            process_date__date=current_date,
            event__in=['Withdraw']
        )
        
        
        unique_depositor_usernames = list(daily_deposits.values_list('username', flat=True).distinct())
        total_unique_depositors = len(unique_depositor_usernames)

        # --- Calculate Deposit Frequency ---
        deposit_frequency_data = {}
        if total_unique_depositors > 0:
            deposit_counts = Counter(daily_deposits.values_list('username', flat=True))
            freq_1 = sum(1 for count in deposit_counts.values() if count == 1)
            freq_2 = sum(1 for count in deposit_counts.values() if count == 2)
            freq_3 = sum(1 for count in deposit_counts.values() if count == 3)
            freq_4 = sum(1 for count in deposit_counts.values() if count == 4)
            freq_5_9 = sum(1 for count in deposit_counts.values() if 5 <= count <= 9)
            freq_10_plus = sum(1 for count in deposit_counts.values() if count >= 10)
            
            deposit_frequency_data = {
                '1_time': {'count': freq_1, 'percent': get_percentage(freq_1, total_unique_depositors)},
                '2_times': {'count': freq_2, 'percent': get_percentage(freq_2, total_unique_depositors)},
                '3_times': {'count': freq_3, 'percent': get_percentage(freq_3, total_unique_depositors)},
                '4_times': {'count': freq_4, 'percent': get_percentage(freq_4, total_unique_depositors)},
                '5_9_times': {'count': freq_5_9, 'percent': get_percentage(freq_5_9, total_unique_depositors)},
                '10_plus_times': {'count': freq_10_plus, 'percent': get_percentage(freq_10_plus, total_unique_depositors)},
            }

        # --- Calculate Depositor Age Segmentation with better debugging ---
        depositor_age_data = {}
        age_counts = defaultdict(int)  # Use defaultdict to avoid KeyError
        
        if unique_depositor_usernames:
            members_found = 0
            members_with_join_date = 0
            
            for username in unique_depositor_usernames:
                member = depositor_members.get(username)
                if member:
                    members_found += 1
                    if member.join_date:
                        members_with_join_date += 1
                        # Handle both datetime and date objects
                        if hasattr(member.join_date, 'date'):
                            join_date = member.join_date.date()
                        else:
                            join_date = member.join_date
                            
                        member_age_days = (current_date - join_date).days
                        
                        # Debug print for first few members
                        if members_with_join_date <= 3:
                            print(f"DEBUG: Username {username}, join_date: {join_date}, age_days: {member_age_days}")
                        
                        if member_age_days == 0: 
                            age_counts['day_0'] += 1
                        elif 1 <= member_age_days <= 7: 
                            age_counts['day_1_7'] += 1
                        elif 8 <= member_age_days <= 14: 
                            age_counts['day_8_14'] += 1
                        elif 15 <= member_age_days <= 30: 
                            age_counts['day_15_30'] += 1
                        elif 31 <= member_age_days <= 60: 
                            age_counts['day_31_60'] += 1
                        elif 61 <= member_age_days <= 90: 
                            age_counts['day_61_90'] += 1
                        elif 91 <= member_age_days <= 180: 
                            age_counts['day_91_180'] += 1
                        else: 
                            age_counts['day_180_plus'] += 1
                    else:
                        print(f"DEBUG: Member {username} has no join_date")
                else:
                    print(f"DEBUG: No member found for username {username}")
            

            
            depositor_age_data = {
                'day_0': {'count': age_counts['day_0'], 'percent': get_percentage(age_counts['day_0'], total_unique_depositors)},
                'day_1_7': {'count': age_counts['day_1_7'], 'percent': get_percentage(age_counts['day_1_7'], total_unique_depositors)},
                'day_8_14': {'count': age_counts['day_8_14'], 'percent': get_percentage(age_counts['day_8_14'], total_unique_depositors)},
                'day_15_30': {'count': age_counts['day_15_30'], 'percent': get_percentage(age_counts['day_15_30'], total_unique_depositors)},
                'day_31_60': {'count': age_counts['day_31_60'], 'percent': get_percentage(age_counts['day_31_60'], total_unique_depositors)},
                'day_61_90': {'count': age_counts['day_61_90'], 'percent': get_percentage(age_counts['day_61_90'], total_unique_depositors)},
                'day_91_180': {'count': age_counts['day_91_180'], 'percent': get_percentage(age_counts['day_91_180'], total_unique_depositors)},
                'day_180_plus': {'count': age_counts['day_180_plus'], 'percent': get_percentage(age_counts['day_180_plus'], total_unique_depositors)},
            }

        # --- Calculate other metrics ---
        total_deposit_value = daily_deposits.aggregate(total=Sum('amount'))['total'] or 0
        total_deposit_transactions = daily_deposits.count()
        average_deposit_amount = (total_deposit_value / total_deposit_transactions) if total_deposit_transactions > 0 else 0
        
        total_withdrawal_value = daily_withdrawals.aggregate(total=Sum('amount'))['total'] or 0
        withdrawal_to_deposit_ration = (total_withdrawal_value / total_deposit_value) if total_withdrawal_value > 0 else float('inf')

        report_data.append({
            'date': current_date,
            'day': calendar.day_name[current_date.weekday()],
            'total_unique_depositors': total_unique_depositors,
            'deposit_frequency': deposit_frequency_data,
            'average_deposit_amount': average_deposit_amount,
            'depositor_age_segmentation': depositor_age_data,
            'withdrawal_to_deposit_ration': withdrawal_to_deposit_ration,
            'total_deposit_value': total_deposit_value,
            'total_withdrawal_value': total_withdrawal_value,
        })

        current_date += timedelta(days=1)


    #if report_data:
    #    print(f"First item depositor_age_segmentation: {report_data[0]['depositor_age_segmentation']}")
    
    context = {
        'members': report_data,  # Changed from 'report_data' to 'members' to match template
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'start_date_default': start_date_default,
        'end_date_default': end_date_default,
    }
    
     
    return TemplateResponse(request, 'report_app/reports/report_daily_general_transaction_summary/view.html', {'context_data': context})