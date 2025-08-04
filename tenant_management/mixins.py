from django.core.exceptions import PermissionDenied
import logging


logger = logging.getLogger(__name__)  # Add logger

class MasterUserRequiredMixin:
    """Verify that the current user is from the master tenant"""
    def dispatch(self, request, *args, **kwargs):
        if not self.is_master_user(request):
            tenant_id = getattr(request.tenant, 'tenant_id', 'NO TENANT')
            logger.warning(
                                f"Tenant mismatch! User: {request.user.email} "
                                f"tried to access {request.path_info} "
                                f"but belongs to {tenant_id} \n"
                            )
            raise PermissionDenied("Access restricted to master tenant users")

        return super().dispatch(request, *args, **kwargs)
    
    def is_master_user(self, request):
        return (
            request.user.is_authenticated and 
            request.user.email.endswith('@master.com')
        )