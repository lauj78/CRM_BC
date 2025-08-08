import csv
import io
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Max, Sum, Q
from django.utils import timezone
from django.http import HttpResponseBadRequest
from data_management.models import Transaction
from django.template.response import TemplateResponse
from datetime import timedelta

@login_required
def report_top_withdrawal_users_view(request):
    today = timezone.now().date()
    start_date_param = request.GET.get('start_date')
    end_date_param = request.GET.get('end_date')
    top_n_param = request.GET.get('top_n')

    # Default dates (30 days from today)
    start_date_default = today - timedelta(days=15)
    end_date_default = today

    # Use GET parameters if provided, otherwise use defaults
    try:
        if start_date_param and end_date_param:
            start_date = timezone.datetime.strptime(start_date_param, '%Y-%m-%d').date()
            end_date = timezone.datetime.strptime(end_date_param, '%Y-%m-%d').date()
        else:
            start_date = start_date_default
            end_date = end_date_default
        
        if start_date > end_date:
            return HttpResponseBadRequest("Start date must be before or equal to end date.")
        
        top_n = int(top_n_param) if top_n_param and int(top_n_param) > 0 else 50
    except ValueError:
        return HttpResponseBadRequest("Invalid date or top_n format. Use YYYY-MM-DD for dates and a positive integer for top_n.")

    # Optimized Query: Get all relevant transactions for all users in the range
    relevant_transactions = Transaction.objects.filter(
        Q(event__in=['Deposit', 'Manual Deposit', 'Withdraw', 'Manual Withdraw']),
        process_date__date__range=[start_date, end_date]
    )

    # Get a list of unique usernames who have withdrawals in the range
    top_withdrawal_usernames = relevant_transactions.filter(event__in=['Withdraw', 'Manual Withdraw']).values('username').annotate(
        total_withdrawals=Sum('amount')
    ).order_by('-total_withdrawals')[:top_n].values_list('username', flat=True)

    # Now, get all data for these specific top users
    top_users_data = {}
    for username in top_withdrawal_usernames:
        user_transactions = relevant_transactions.filter(username=username)
        
        total_withdrawals = user_transactions.filter(event__in=['Withdraw', 'Manual Withdraw']).aggregate(sum=Sum('amount'))['sum'] or 0
        total_deposits = user_transactions.filter(event__in=['Deposit', 'Manual Deposit']).aggregate(sum=Sum('amount'))['sum'] or 0
        
        withdrawal_frequency = user_transactions.filter(event__in=['Withdraw', 'Manual Withdraw']).count()
        deposit_frequency = user_transactions.filter(event__in=['Deposit', 'Manual Deposit']).count()
        
        largest_withdrawal = user_transactions.filter(event__in=['Withdraw', 'Manual Withdraw']).aggregate(max=Max('amount'))['max'] or 0

        manual_withdrawals = user_transactions.filter(event='Manual Withdraw').aggregate(sum=Sum('amount'))['sum'] or 0
        manual_withdrawal_freq = user_transactions.filter(event='Manual Withdraw').count()
        manual_deposits = user_transactions.filter(event='Manual Deposit').aggregate(sum=Sum('amount'))['sum'] or 0
        
        last_activity = Transaction.objects.filter(username=username).aggregate(max=Max('process_date'))['max']

        # Calculate new fields
        inactive_days = (today - last_activity.date()).days if last_activity else None
        player_winlose = total_withdrawals - total_deposits

        top_users_data[username] = {
            'username': username,
            'total_withdrawals': total_withdrawals,
            'withdrawal_frequency': withdrawal_frequency,
            'average_withdrawal': total_withdrawals / withdrawal_frequency if withdrawal_frequency else 0,
            'largest_withdrawal': largest_withdrawal,
            'total_manual_withdrawals': manual_withdrawals,
            'manual_withdrawal_freq': manual_withdrawal_freq,
            'total_deposits': total_deposits,
            'deposit_freq': deposit_frequency,
            'total_manual_deposits': manual_deposits,
            'last_activity': last_activity.date() if last_activity else None,
            'inactive_days': inactive_days,
            'player_winlose': player_winlose,
        }

    report_top_withdrawal_users = sorted(top_users_data.values(), key=lambda x: x['total_withdrawals'], reverse=True)

    # Handle POST request for export
    if request.method == 'POST' and request.POST.get('_export', '').lower() == 'csv':
        csv_content = io.StringIO()
        writer = csv.writer(csv_content)
        writer.writerow([
            'Username', 'Total Withdrawals', 'Total Manual Withdrawals', 'Total Deposits', 
            'Total Manual Deposits', 'Player WINLOSE', 'Inactive Days', 
            'Last Activity Date', 'Withdrawal Frequency', 'Average Withdrawal', 'Largest Withdrawal Value'
        ])
        for user in report_top_withdrawal_users:
            writer.writerow([
                user['username'],
                user['total_withdrawals'],
                user['total_manual_withdrawals'],
                user['total_deposits'],
                user['total_manual_deposits'],
                user['player_winlose'],
                user['inactive_days'],
                user['last_activity'].strftime('%Y-%m-%d') if user['last_activity'] else '',
                user['withdrawal_frequency'],
                user['average_withdrawal'],
                user['largest_withdrawal']
            ])
        csv_data = csv_content.getvalue()
        csv_content.close()

        context = {
            'report_top_withdrawal_users': report_top_withdrawal_users,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'start_date_default': start_date_default,
            'end_date_default': end_date_default,
            'top_n': top_n,
            'csv_data': csv_data,
            'filename': f"report_top_withdrawal_users_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.csv"
        }
        return TemplateResponse(request, 'report_app/reports/report_top_withdrawal_users/view.html', context)

    # Render the template for GET request (non-export)
    context = {
        'report_top_withdrawal_users': report_top_withdrawal_users,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'start_date_default': start_date_default,
        'end_date_default': end_date_default,
        'top_n': top_n,
    }
    return TemplateResponse(request, 'report_app/reports/report_top_withdrawal_users/view.html', context)