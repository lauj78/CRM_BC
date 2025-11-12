# report_app/reports/report_new_member_deposit_activity/views.py

from django.contrib.auth.decorators import login_required
from django.template.response import TemplateResponse
from data_management.models import Transaction, Member
from django.utils import timezone
from datetime import datetime, timedelta
from collections import defaultdict

@login_required
def report_new_member_deposit_activity_view(request):
    results = []
    error_message = None
    deposit_dates = []
    
    # Default parameters: last 2 weeks
    default_reg_start = (timezone.now() - timedelta(days=14)).date()
    default_reg_end = timezone.now().date()
    default_dep_start = (timezone.now() - timedelta(days=14)).date()
    default_dep_end = timezone.now().date()
    
    # Handle form submission
    if request.method == "POST":
        try:
            # Get parameters
            reg_start_str = request.POST.get('reg_start_date')
            reg_end_str = request.POST.get('reg_end_date')
            dep_start_str = request.POST.get('dep_start_date')
            dep_end_str = request.POST.get('dep_end_date')
            
            reg_start = datetime.strptime(reg_start_str, '%Y-%m-%d').date()
            reg_end = datetime.strptime(reg_end_str, '%Y-%m-%d').date()
            dep_start = datetime.strptime(dep_start_str, '%Y-%m-%d').date()
            dep_end = datetime.strptime(dep_end_str, '%Y-%m-%d').date()
            
            if reg_start > reg_end:
                error_message = "Registration start date must be before end date"
            elif dep_start > dep_end:
                error_message = "Deposit start date must be before end date"
            else:
                # Step 1: Get all members registered in the first date range
                members_by_date = defaultdict(list)
                members = Member.objects.filter(
                    join_date__date__gte=reg_start,
                    join_date__date__lte=reg_end
                ).order_by('join_date')
                
                for member in members:
                    reg_date = member.join_date.date()
                    members_by_date[reg_date].append(member.username)
                
                # Step 2: Generate list of dates in deposit monitoring period
                current_date = dep_start
                while current_date <= dep_end:
                    deposit_dates.append(current_date)
                    current_date += timedelta(days=1)
                
                # Step 3: For each registration date, check deposit activity
                current_date = reg_start
                while current_date <= reg_end:
                    if current_date in members_by_date:
                        usernames = members_by_date[current_date]
                        row_data = {
                            'registration_date': current_date,
                            'new_members_count': len(usernames),
                            'deposit_activity': []
                        }
                        
                        # For each deposit monitoring date, calculate metrics
                        for dep_date in deposit_dates:
                            # Get deposits made by these members on this specific date
                            deposits = Transaction.objects.filter(
                                username__in=usernames,
                                event='Deposit',  # Only 'Deposit', not 'Manual Deposit'
                                process_date__date=dep_date
                            )
                            
                            # Calculate metrics
                            unique_members = deposits.values('username').distinct().count()
                            transaction_count = deposits.count()
                            total_amount = sum([d.amount for d in deposits])
                            
                            row_data['deposit_activity'].append({
                                'date': dep_date,
                                'member_count': unique_members,
                                'transaction_count': transaction_count,
                                'deposit_amount': total_amount
                            })
                        
                        results.append(row_data)
                    
                    current_date += timedelta(days=1)
                
        except ValueError as e:
            error_message = f"Invalid date format: {str(e)}"
        except Exception as e:
            error_message = f"Error processing report: {str(e)}"
    
    # Render the template
    context = {
        'results': results,
        'deposit_dates': deposit_dates,
        'error_message': error_message,
        'default_reg_start': default_reg_start,
        'default_reg_end': default_reg_end,
        'default_dep_start': default_dep_start,
        'default_dep_end': default_dep_end
    }
    
    return TemplateResponse(request, 'report_app/reports/report_new_member_deposit_activity/view.html', context)