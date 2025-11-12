# report_app/reports/report_new_member_deposit_tracking_days/views.py

from django.contrib.auth.decorators import login_required
from django.template.response import TemplateResponse
from data_management.models import Transaction, Member
from django.utils import timezone
from datetime import datetime, timedelta
from collections import defaultdict

@login_required
def report_new_member_deposit_tracking_days_view(request):
    results = []
    error_message = None
    days_to_track = 7
    
    # Default parameters: last 7 days
    default_reg_start = (timezone.now() - timedelta(days=7)).date()
    default_reg_end = timezone.now().date()
    default_days = 7
    
    # Handle form submission
    if request.method == "POST":
        try:
            # Get parameters
            reg_start_str = request.POST.get('reg_start_date')
            reg_end_str = request.POST.get('reg_end_date')
            days_to_track = int(request.POST.get('days_to_track', default_days))
            
            reg_start = datetime.strptime(reg_start_str, '%Y-%m-%d').date()
            reg_end = datetime.strptime(reg_end_str, '%Y-%m-%d').date()
            
            if reg_start > reg_end:
                error_message = "Registration start date must be before end date"
            elif days_to_track < 1 or days_to_track > 30:
                error_message = "Days to track must be between 1 and 30"
            else:
                # Step 1: Get all members registered in the date range
                members_by_date = defaultdict(list)
                members = Member.objects.filter(
                    join_date__date__gte=reg_start,
                    join_date__date__lte=reg_end
                ).order_by('join_date')
                
                for member in members:
                    reg_date = member.join_date.date()
                    members_by_date[reg_date].append(member.username)
                
                # Step 2: For each registration date, track deposits for N days
                current_date = reg_start
                while current_date <= reg_end:
                    if current_date in members_by_date:
                        usernames = members_by_date[current_date]
                        row_data = {
                            'registration_date': current_date,
                            'new_members_count': len(usernames),
                            'day_activity': []
                        }
                        
                        # For each day offset (Day 0, Day 1, Day 2, etc.)
                        for day_offset in range(days_to_track + 1):  # +1 to include Day 0
                            tracking_date = current_date + timedelta(days=day_offset)
                            
                            # Get deposits made by these members on this specific day
                            deposits = Transaction.objects.filter(
                                username__in=usernames,
                                event='Deposit',  # Only 'Deposit', not 'Manual Deposit'
                                process_date__date=tracking_date
                            )
                            
                            # Calculate metrics
                            unique_members = deposits.values('username').distinct().count()
                            transaction_count = deposits.count()
                            total_amount = sum([d.amount for d in deposits])
                            
                            row_data['day_activity'].append({
                                'day_offset': day_offset,
                                'actual_date': tracking_date,
                                'member_count': unique_members,
                                'transaction_count': transaction_count,
                                'deposit_amount': total_amount
                            })
                        
                        results.append(row_data)
                    
                    current_date += timedelta(days=1)
                
        except ValueError as e:
            error_message = f"Invalid input: {str(e)}"
        except Exception as e:
            error_message = f"Error processing report: {str(e)}"
    
    # Render the template
    context = {
        'results': results,
        'days_to_track': days_to_track,
        'error_message': error_message,
        'default_reg_start': default_reg_start,
        'default_reg_end': default_reg_end,
        'default_days': default_days
    }
    
    return TemplateResponse(request, 'report_app/reports/report_new_member_deposit_tracking_days/view.html', context)