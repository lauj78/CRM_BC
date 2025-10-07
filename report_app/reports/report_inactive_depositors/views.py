#report_app/reports/report_inactive_depositors/views.py

from django.contrib.auth.decorators import login_required
from django.template.response import TemplateResponse
from data_management.models import Transaction, Member
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Max, Count
import csv
import io

@login_required
def report_inactive_depositors_view(request):
    results = []
    error_message = None
    summary = {}
    
    # Default parameters
    default_dep_start = (timezone.now() - timedelta(days=30)).date()
    default_dep_end = timezone.now().date()
    default_inactive_days = 7
    
    # Handle form submission (both initial and export)
    if request.method == "POST":
        try:
            # Get parameters
            dep_start_str = request.POST.get('dep_start_date')
            dep_end_str = request.POST.get('dep_end_date')
            inactive_days = int(request.POST.get('inactive_days', default_inactive_days))
            
            dep_start = datetime.strptime(dep_start_str, '%Y-%m-%d').date()
            dep_end = datetime.strptime(dep_end_str, '%Y-%m-%d').date()
            
            if dep_start > dep_end:
                error_message = "Start date must be before end date"
            else:
                # Calculate inactive cutoff date
                inactive_cutoff = timezone.now() - timedelta(days=inactive_days)
                
                # Find members with deposits in the period
                depositors = Transaction.objects.filter(
                    event__in=['Deposit', 'Manual Deposit'],
                    process_date__date__gte=dep_start,
                    process_date__date__lte=dep_end
                ).values('username').distinct()
                
                depositor_usernames = [d['username'] for d in depositors]
                
                # For each depositor, check their last activity
                for username in depositor_usernames:
                    # Get member details
                    try:
                        member = Member.objects.get(username=username)
                    except Member.DoesNotExist:
                        continue
                    
                    # Get last transaction date (any type)
                    last_activity = Transaction.objects.filter(
                        username=username
                    ).aggregate(
                        last_date=Max('process_date')
                    )['last_date']
                    
                    # Check if inactive
                    if last_activity and last_activity < inactive_cutoff:
                        # Get deposit stats in period
                        dep_stats = Transaction.objects.filter(
                            username=username,
                            event__in=['Deposit', 'Manual Deposit'],
                            process_date__date__gte=dep_start,
                            process_date__date__lte=dep_end
                        ).aggregate(
                            total_deposits=Count('id'),
                            last_dep=Max('process_date')
                        )
                        
                        days_inactive = (timezone.now() - last_activity).days
                        
                        results.append({
                            'username': username,
                            'name': member.name,
                            'handphone': member.handphone,
                            'join_date': member.join_date,
                            'total_deposits': dep_stats['total_deposits'],
                            'last_deposit': dep_stats['last_dep'],
                            'last_activity': last_activity,
                            'days_inactive': days_inactive
                        })
                
                # Sort by days inactive (most inactive first)
                results.sort(key=lambda x: x['days_inactive'], reverse=True)
                
                # Summary stats
                summary = {
                    'total_members': len(results),
                    'avg_inactive_days': sum(r['days_inactive'] for r in results) / len(results) if results else 0,
                    'dep_period_start': dep_start,
                    'dep_period_end': dep_end,
                    'inactive_threshold': inactive_days
                }
                
        except ValueError as e:
            error_message = f"Invalid date format: {str(e)}"
        except Exception as e:
            error_message = f"Error processing report: {str(e)}"
    
    # Handle CSV export
    if request.method == 'POST' and request.POST.get('_export', '').lower() == 'csv' and results:
        # Generate CSV
        csv_content = io.StringIO()
        writer = csv.writer(csv_content)
        writer.writerow(['Username', 'Name', 'Phone', 'Join Date', 'Total Deposits', 'Last Deposit', 'Last Activity', 'Days Inactive'])
        
        for r in results:
            writer.writerow([
                r['username'],
                r['name'],
                r['handphone'],
                r['join_date'].strftime('%Y-%m-%d %H:%M') if r['join_date'] else '',
                r['total_deposits'],
                r['last_deposit'].strftime('%Y-%m-%d %H:%M') if r['last_deposit'] else '',
                r['last_activity'].strftime('%Y-%m-%d %H:%M') if r['last_activity'] else '',
                r['days_inactive']
            ])
        
        csv_data = csv_content.getvalue()
        csv_content.close()

        context = {
            'results': results,
            'summary': summary,
            'error_message': error_message,
            'default_dep_start': default_dep_start,
            'default_dep_end': default_dep_end,
            'default_inactive_days': default_inactive_days,
            'csv_data': csv_data,
            'filename': f"inactive_depositors_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        }
        return TemplateResponse(request, 'report_app/reports/report_inactive_depositors/view.html', context)
    
    # Render the template for non-export requests
    context = {
        'results': results,
        'summary': summary,
        'error_message': error_message,
        'default_dep_start': default_dep_start,
        'default_dep_end': default_dep_end,
        'default_inactive_days': default_inactive_days
    }
    
    return TemplateResponse(request, 'report_app/reports/report_inactive_depositors/view.html', context)