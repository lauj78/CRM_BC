from django.contrib.auth.decorators import login_required
from django.template.response import TemplateResponse
from data_management.models import Transaction, Member
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Max, Count
import csv
import io

@login_required
def report_inactive_withdrawers_view(request):
    results = []
    error_message = None
    summary = {}
    
    # Default parameters
    default_wd_start = (timezone.now() - timedelta(days=30)).date()
    default_wd_end = timezone.now().date()
    default_inactive_days = 7
    
    # Handle form submission (both initial and export)
    if request.method == "POST":
        try:
            # Get parameters
            wd_start_str = request.POST.get('wd_start_date')
            wd_end_str = request.POST.get('wd_end_date')
            inactive_days = int(request.POST.get('inactive_days', default_inactive_days))
            
            wd_start = datetime.strptime(wd_start_str, '%Y-%m-%d').date()
            wd_end = datetime.strptime(wd_end_str, '%Y-%m-%d').date()
            
            if wd_start > wd_end:
                error_message = "Start date must be before end date"
            else:
                # Calculate inactive cutoff date
                inactive_cutoff = timezone.now() - timedelta(days=inactive_days)
                
                # Find members with withdrawals in the period
                withdrawers = Transaction.objects.filter(
                    event__in=['Withdraw', 'Manual Withdraw'],
                    process_date__date__gte=wd_start,
                    process_date__date__lte=wd_end
                ).values('username').distinct()
                
                withdrawer_usernames = [w['username'] for w in withdrawers]
                
                # For each withdrawer, check their last activity
                for username in withdrawer_usernames:
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
                        # Get withdrawal stats in period
                        wd_stats = Transaction.objects.filter(
                            username=username,
                            event__in=['Withdraw', 'Manual Withdraw'],
                            process_date__date__gte=wd_start,
                            process_date__date__lte=wd_end
                        ).aggregate(
                            total_withdrawals=Count('id'),
                            last_wd=Max('process_date')
                        )
                        
                        days_inactive = (timezone.now() - last_activity).days
                        
                        results.append({
                            'username': username,
                            'name': member.name,
                            'handphone': member.handphone,
                            'join_date': member.join_date,
                            'total_withdrawals': wd_stats['total_withdrawals'],
                            'last_withdrawal': wd_stats['last_wd'],
                            'last_activity': last_activity,
                            'days_inactive': days_inactive
                        })
                
                # Sort by days inactive (most inactive first)
                results.sort(key=lambda x: x['days_inactive'], reverse=True)
                
                # Summary stats
                summary = {
                    'total_members': len(results),
                    'avg_inactive_days': sum(r['days_inactive'] for r in results) / len(results) if results else 0,
                    'wd_period_start': wd_start,
                    'wd_period_end': wd_end,
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
        writer.writerow(['Username', 'Name', 'Phone', 'Join Date', 'Total Withdrawals', 'Last Withdrawal', 'Last Activity', 'Days Inactive'])
        
        for r in results:
            writer.writerow([
                r['username'],
                r['name'],
                r['handphone'],
                r['join_date'].strftime('%Y-%m-%d %H:%M') if r['join_date'] else '',
                r['total_withdrawals'],
                r['last_withdrawal'].strftime('%Y-%m-%d %H:%M') if r['last_withdrawal'] else '',
                r['last_activity'].strftime('%Y-%m-%d %H:%M') if r['last_activity'] else '',
                r['days_inactive']
            ])
        
        csv_data = csv_content.getvalue()
        csv_content.close()

        context = {
            'results': results,
            'summary': summary,
            'error_message': error_message,
            'default_wd_start': default_wd_start,
            'default_wd_end': default_wd_end,
            'default_inactive_days': default_inactive_days,
            'csv_data': csv_data,
            'filename': f"inactive_withdrawers_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        }
        return TemplateResponse(request, 'report_app/reports/report_inactive_withdrawers/view.html', context)
    
    # Render the template for non-export requests
    context = {
        'results': results,
        'summary': summary,
        'error_message': error_message,
        'default_wd_start': default_wd_start,
        'default_wd_end': default_wd_end,
        'default_inactive_days': default_inactive_days
    }
    
    return TemplateResponse(request, 'report_app/reports/report_inactive_withdrawers/view.html', context)