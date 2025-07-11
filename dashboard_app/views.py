from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Sum
from .models import OperatorLog
from datetime import timedelta
from django.utils import timezone
import calendar
from data_management.models import Transaction, Member

def is_admin(user):
    return user.is_superuser

def is_operator(user):
    return not user.is_superuser

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard_app:dashboard')  # Updated to use namespace
        else:
            return render(request, 'login.html', {'error': 'Invalid credentials'})
    return render(request, 'login.html')

@login_required
def dashboard_view(request):  # Renamed from 'dashboard' to 'dashboard_view'
    today = timezone.now().date()
    thirty_days_ago = today - timedelta(days=30)

    # Prepare data for the past 30 days based on process_date
    dashboard_data = []
    current_date = thirty_days_ago
    while current_date <= today:
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
        
        # Add to dashboard data
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

    if request.method == 'POST' and request.user.is_superuser:
        OperatorLog.objects.create(user=request.user, action="Modified dashboard data")
    elif request.method == 'POST':
        OperatorLog.objects.create(user=request.user, action="Viewed dashboard report")
    logs = OperatorLog.objects.all()[:10]
    return render(request, 'dashboard_app/dashboard.html', {  # Updated template path
        'members': dashboard_data,
        'logs': logs,
    })

@login_required
@user_passes_test(lambda u: not u.is_superuser)
def upload_view(request):
    return redirect('data_management:upload_file')  # Updated to use namespace

def logout_view(request):
    logout(request)
    return redirect('data_management:login')  # Updated to use namespace