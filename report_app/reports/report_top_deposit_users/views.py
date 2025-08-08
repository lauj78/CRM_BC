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
def report_top_deposit_users_view(request):
    today = timezone.now().date()
    start_date_param = request.GET.get('start_date')
    end_date_param = request.GET.get('end_date')
    top_n_param = request.GET.get('top_n')

    start_date_default = today - timedelta(days=15)
    end_date_default = today

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

    relevant_transactions = Transaction.objects.filter(
        Q(event__in=['Deposit', 'Manual Deposit', 'Withdraw', 'Manual Withdraw']),
        process_date__date__range=[start_date, end_date]
    )

    top_deposit_usernames = relevant_transactions.filter(event__in=['Deposit', 'Manual Deposit']).values('username').annotate(
        total_deposits=Sum('amount')
    ).order_by('-total_deposits')[:top_n].values_list('username', flat=True)

    top_users_data = {}
    for username in top_deposit_usernames:
        user_transactions = relevant_transactions.filter(username=username)

        total_deposits = user_transactions.filter(event__in=['Deposit', 'Manual Deposit']).aggregate(sum=Sum('amount'))['sum'] or 0
        total_withdrawals = user_transactions.filter(event__in=['Withdraw', 'Manual Withdraw']).aggregate(sum=Sum('amount'))['sum'] or 0
        deposit_frequency = user_transactions.filter(event__in=['Deposit', 'Manual Deposit']).count()
        
        manual_deposits = user_transactions.filter(event='Manual Deposit').aggregate(sum=Sum('amount'))['sum'] or 0
        manual_withdrawals = user_transactions.filter(event='Manual Withdraw').aggregate(sum=Sum('amount'))['sum'] or 0
        
        largest_deposit = user_transactions.filter(event__in=['Deposit', 'Manual Deposit']).aggregate(max=Max('amount'))['max'] or 0
        
        last_activity = Transaction.objects.filter(username=username).aggregate(max=Max('process_date'))['max']

        inactive_days = (today - last_activity.date()).days if last_activity else None
        
        # Corrected WINLOSE calculation
        player_winlose = total_withdrawals - total_deposits

        top_users_data[username] = {
            'username': username,
            'total_deposits': total_deposits,
            'deposit_frequency': deposit_frequency,
            'average_deposit': total_deposits / deposit_frequency if deposit_frequency else 0,
            'largest_deposit': largest_deposit,
            'total_manual_deposits': manual_deposits,
            'total_manual_withdrawals': manual_withdrawals,
            'total_withdrawals': total_withdrawals,
            'last_activity': last_activity.date() if last_activity else None,
            'inactive_days': inactive_days,
            'player_winlose': player_winlose,
        }

    report_top_deposit_users = sorted(top_users_data.values(), key=lambda x: x['total_deposits'], reverse=True)

    if request.method == 'POST' and request.POST.get('_export', '').lower() == 'csv':
        csv_content = io.StringIO()
        writer = csv.writer(csv_content)
        writer.writerow([
            'Username', 'Total Deposits', 'Total Manual Deposits', 'Total Withdrawals', 
            'Total Manual Withdrawals', 'Player WINLOSE', 'Inactive Days', 
            'Last Activity Date', 'Deposit Frequency', 'Average Deposit', 'Largest Deposit Value'
        ])
        for user in report_top_deposit_users:
            writer.writerow([
                user['username'],
                user['total_deposits'],
                user['total_manual_deposits'],
                user['total_withdrawals'],
                user['total_manual_withdrawals'],
                user['player_winlose'],
                user['inactive_days'],
                user['last_activity'].strftime('%Y-%m-%d') if user['last_activity'] else '',
                user['deposit_frequency'],
                user['average_deposit'],
                user['largest_deposit']
            ])
        csv_data = csv_content.getvalue()
        csv_content.close()

        context = {
            'report_top_deposit_users': report_top_deposit_users,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'start_date_default': start_date_default,
            'end_date_default': end_date_default,
            'top_n': top_n,
            'csv_data': csv_data,
            'filename': f"report_top_deposit_users_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.csv"
        }
        return TemplateResponse(request, 'report_app/reports/report_top_deposit_users/view.html', context)

    context = {
        'report_top_deposit_users': report_top_deposit_users,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'start_date_default': start_date_default,
        'end_date_default': end_date_default,
        'top_n': top_n,
    }
    return TemplateResponse(request, 'report_app/reports/report_top_deposit_users/view.html', context)