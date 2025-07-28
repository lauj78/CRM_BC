from .models import Tenant

def get_tenant_from_request(request):
    # Extract tenant_id from the URL path
    path = request.path_info
    if path.startswith('/tenant/'):
        tenant_id = path.split('/tenant/')[1].split('/')[0]
        try:
            return Tenant.objects.get(tenant_id=tenant_id)
        except Tenant.DoesNotExist:
            return None
    return None