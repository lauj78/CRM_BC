from django.shortcuts import render, redirect
from django.http import JsonResponse
from .middleware import _thread_local
from .models import Tenant
from django.contrib.auth.decorators import login_required  # Add this import

def account_locked(request):
    return render(request, 'account_locked.html')

def tenant_test(request, tenant_id=None):
    tenant = getattr(request, 'tenant', None)
    return JsonResponse({
        'tenant': tenant.name if tenant else 'No tenant',
        'database': getattr(_thread_local, 'current_db', 'default')
    })

@login_required
def tenant_redirect(request):
    print("\n===== tenant_redirect DEBUG START =====")
    print(f"Session ID: {request.session.session_key}")
    print(f"Authenticated: {request.user.is_authenticated}")
    print(f"User ID: {request.user.id}")
    print(f"Email: {request.user.email}")
    print(f"Tenant exists: {hasattr(request, 'tenant')}")
    print(f"Session data: {dict(request.session)}")
    
    # REMOVED the outer if request.user.is_authenticated: block
    # because @login_required already guarantees authentication
    
    # Master user check
    if request.user.email.endswith('@master'):
        print("Redirecting to master dashboard")
        return redirect('master_dashboard:dashboard')
    
    # Try to get tenant from session if not on request
    if not hasattr(request, 'tenant'):
        tenant_id = request.session.get('tenant_id')
        if tenant_id:
            try:
                request.tenant = Tenant.objects.get(tenant_id=tenant_id)
                print(f"Retrieved tenant from session: {tenant_id}")
            except Tenant.DoesNotExist:
                pass
    
    # If still not set, try email-based resolution with FULL DOMAIN
    if not hasattr(request, 'tenant') or not request.tenant:
        email = request.user.email
        if '@' in email:
            domain = email.split('@')[1]  # Get full domain
            try:
                request.tenant = Tenant.objects.get(tenant_id=domain)
                print(f"Set tenant from full domain: {domain}")
                # Update session for future requests
                request.session['tenant_id'] = domain
            except Tenant.DoesNotExist:
                print(f"Tenant not found for domain: {domain}")
                pass
    
    # Redirect to tenant dashboard
    if hasattr(request, 'tenant') and request.tenant:
        print(f"Redirecting to tenant dashboard: {request.tenant.tenant_id}")
        return redirect('dashboard_app:dashboard', tenant_id=request.tenant.tenant_id)
    
    print("Redirecting to login page")
    print("===== tenant_redirect DEBUG END =====\n")
    return redirect('login')