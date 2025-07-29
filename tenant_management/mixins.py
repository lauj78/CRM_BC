from django.core.exceptions import PermissionDenied

class MasterUserRequiredMixin:
    """Verify that the current user is from the master tenant"""
    def dispatch(self, request, *args, **kwargs):
        if not self.is_master_user(request):
            raise PermissionDenied("Access restricted to master tenant users")
        return super().dispatch(request, *args, **kwargs)
    
    def is_master_user(self, request):
        return (
            request.user.is_authenticated and 
            request.user.email.endswith('@master')
        )