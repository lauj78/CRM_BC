# dashboard_app/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def dashboard(request):
    return render(request, 'dashboard_app/dashboard.html')