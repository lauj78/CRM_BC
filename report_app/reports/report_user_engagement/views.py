import csv
import io
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Max, Sum, Q
from django.utils import timezone
from django.http import HttpResponse, HttpResponseBadRequest
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from data_management.models import Transaction
from django.template.response import TemplateResponse
from datetime import timedelta

@login_required
def report_user_engagement_view(request):
    today = timezone.now().date()
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    page = request.GET.get('page', 1)

    # Default dates
    start_date_default = today - timedelta(days=15)
    end_date_default = today

    # Use GET parameters for initial display
    try:
        start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else start_date_default
        end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else end_date_default
    except ValueError:
        return HttpResponseBadRequest("Invalid date format. Use YYYY-MM-DD.")
    
    if start_date > end_date:
        return HttpResponseBadRequest("Start date cannot be after end date.")

    # Get all users who had a transaction within the date range
    active_users = Transaction.objects.filter(
        process_date__date__range=[start_date, end_date]
    ).values('username').annotate(
        last_activity=Max('process_date__date')
    )

    user_engagement_data = []
    for user_data in active_users:
        username = user_data['username']
        last_activity = user_data['last_activity']
        days_since_last_activity = (today - last_activity).days

        user_transactions = Transaction.objects.filter(
            username=username,
            process_date__date__range=[start_date, end_date]
        ).aggregate(
            sum_deposit=Sum('amount', filter=Q(event='Deposit')),
            sum_manual_deposit=Sum('amount', filter=Q(event='Manual Deposit')),
            sum_withdraw=Sum('amount', filter=Q(event='Withdraw')),
            sum_manual_withdraw=Sum('amount', filter=Q(event='Manual Withdraw'))
        )
        
        # Calculate totals
        total_deposits = (user_transactions['sum_deposit'] or 0) + (user_transactions['sum_manual_deposit'] or 0)
        total_withdrawals = (user_transactions['sum_withdraw'] or 0) + (user_transactions['sum_manual_withdraw'] or 0)

        user_engagement_data.append({
            'username': username,
            'last_activity': last_activity,
            'sum_deposit': user_transactions['sum_deposit'] or 0,
            'sum_manual_deposit': user_transactions['sum_manual_deposit'] or 0,
            'total_deposits': total_deposits,
            'sum_withdraw': user_transactions['sum_withdraw'] or 0,
            'sum_manual_withdraw': user_transactions['sum_manual_withdraw'] or 0,
            'total_withdrawals': total_withdrawals,
            'days_since_last_activity': days_since_last_activity,
        })

    # Sort by days_since_last_activity from largest to smallest (most inactive first)
    user_engagement_data.sort(key=lambda x: x['days_since_last_activity'], reverse=True)

    # Get total count before pagination
    total_users_count = len(user_engagement_data)
    
    # Handle POST request for export
    if request.method == 'POST' and request.POST.get('_export', '').lower() == 'csv':
        csv_content = io.StringIO()
        writer = csv.writer(csv_content)
        writer.writerow([
            'Username', 
            'Sum of Deposit', 
            'Sum of Manual Deposit', 
            'Total Sum of Deposits', 
            'Sum of Withdraw', 
            'Sum of Manual Withdraw', 
            'Total Sum of Withdrawals', 
            'Last Activity', 
            'Days Since Last Activity'
        ])
        for user in user_engagement_data:
            writer.writerow([
                user['username'],
                user['sum_deposit'],
                user['sum_manual_deposit'],
                user['total_deposits'],
                user['sum_withdraw'],
                user['sum_manual_withdraw'],
                user['total_withdrawals'],
                user['last_activity'].strftime('%Y-%m-%d'),
                user['days_since_last_activity']
            ])
        csv_data = csv_content.getvalue()
        csv_content.close()
        
        paginator = Paginator(user_engagement_data, 500)
        try:
            paginated_users = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            paginated_users = paginator.page(1)
        
        context = {
            'user_engagement_data': paginated_users,
            'total_users_count': total_users_count,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'start_date_default': start_date_default,
            'end_date_default': end_date_default,
            'csv_data': csv_data,
            'filename': f"user_engagement_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.csv"
        }
        return TemplateResponse(request, 'report_app/reports/report_user_engagement/view.html', context)
    
    # Setup pagination for normal GET request
    paginator = Paginator(user_engagement_data, 500)
    try:
        paginated_users = paginator.page(page)
    except PageNotAnInteger:
        paginated_users = paginator.page(1)
    except EmptyPage:
        paginated_users = paginator.page(paginator.num_pages)

    # Render the template for a normal GET request
    context = {
        'user_engagement_data': paginated_users,
        'total_users_count': total_users_count,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'start_date_default': start_date_default,
        'end_date_default': end_date_default,
    }
    return TemplateResponse(request, 'report_app/reports/report_user_engagement/view.html', context)