# tenants/decorators.py
from functools import wraps

def tenant_bypass(view_func):
    """Decorator to mark views that should bypass tenant processing"""
    # Mark the view function itself
    view_func._tenant_bypass = True
    
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Mark request to skip tenant processing
        request._skip_tenant_processing = True
        return view_func(request, *args, **kwargs)
    return _wrapped_view