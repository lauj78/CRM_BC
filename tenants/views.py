from django.shortcuts import redirect
from django.http import JsonResponse
from .middleware import _thread_local
from .models import Tenant  # Add this import

def tenant_test(request, tenant_id=None):
    tenant = getattr(request, 'tenant', None)
    return JsonResponse({
        'tenant': tenant.name if tenant else 'No tenant',
        'database': getattr(_thread_local, 'current_db', 'default')
    })

# FIXED: Remove extra indentation from function definition
def tenant_redirect(request):
    # Detailed debug info
    print("\n===== tenant_redirect DEBUG START =====")
    print(f"Session ID: {request.session.session_key}")
    print(f"Authenticated: {request.user.is_authenticated}")
    print(f"User ID: {request.user.id if request.user.is_authenticated else 'N/A'}")
    print(f"Email: {getattr(request.user, 'email', 'N/A')}")
    print(f"Tenant exists: {hasattr(request, 'tenant')}")
    print(f"Session data: {dict(request.session)}")
    
    if request.user.is_authenticated:
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
        
        # Redirect to tenant dashboard
        if hasattr(request, 'tenant') and request.tenant:
            print(f"Redirecting to tenant dashboard: {request.tenant.tenant_id}")
            return redirect('dashboard_app:dashboard', tenant_id=request.tenant.tenant_id)
    
    print("Redirecting to login page")
    print("===== tenant_redirect DEBUG END =====\n")
    return redirect('login')