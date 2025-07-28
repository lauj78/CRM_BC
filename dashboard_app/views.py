from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def dashboard(request, tenant_id=None):
    # For master admin
    if tenant_id is None and hasattr(request, 'user') and request.user.email.endswith('@master'):
        return render(request, 'dashboard_app/master_dashboard.html')
    
    # For tenant users
    tenant = getattr(request, 'tenant', None)
    context = {
        'tenant_name': tenant.name if tenant else 'No Tenant',
        'tenant_id': tenant.tenant_id if tenant else None
    }
    return render(request, 'dashboard_app/dashboard.html', context)