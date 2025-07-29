from django.shortcuts import redirect
from .models import Tenant

class SubscriptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Skip these paths for all users
        excluded_paths = [
            '/accounts/login',
            '/accounts/logout',
            '/account-locked',  # The page itself
            '/static',
            '/media',
            '/master',  # Master dashboard
        ]
        
        # Check if path should be excluded
        if any(request.path.startswith(path) for path in excluded_paths):
            return self.get_response(request)
        
        # Check tenant status only if tenant exists
        if hasattr(request, 'tenant') and request.tenant is not None:
            tenant = request.tenant
            if tenant.status in ["Expired", "Suspended"]:
                return redirect('/account-locked/')
        
        return self.get_response(request)