from django.http import HttpResponseForbidden
from django.urls import resolve

class MasterAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        response = self.get_response(request)
        return response
        
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Check if path starts with /master/
        if request.path.startswith('/master/'):
            # Skip for login page
            if request.path == '/accounts/login/':
                return None
                
            # Check if user is from master tenant
            if not (request.user.is_authenticated and 
                    request.user.email.endswith('@master')):
                return HttpResponseForbidden("Access restricted to master tenant users")
        return None