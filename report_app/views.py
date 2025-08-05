# report_app/views.py

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponseForbidden
from importlib import import_module
from . import REPORTS
import inspect # We'll use this to check function signatures

@login_required
# The view function must accept the tenant_id parameter from the URL.
# We remove the '=None' because your URL pattern guarantees its presence.
def report_hub_view(request, tenant_id):
    """
    Main view for the report hub. This function orchestrates the calling
    of other report-specific views dynamically.
    """
    user_groups = [g.name for g in request.user.groups.all()]
    print(f"Debug: User groups: {user_groups}")
    print(f"Debug: Tenant ID: {tenant_id}")
    
    accessible_reports = [
        r for r in REPORTS if not r.get('access') or any(group in r['access'] for group in user_groups)
    ]
    print(f"Debug: Accessible reports: {accessible_reports}")

    if request.GET.get('report'):
        selected_report = next((r for r in REPORTS if r['name'] == request.GET['report']), None)

        if selected_report and (not selected_report.get('access') or any(group in selected_report['access'] for group in user_groups)):
            try:
                module = import_module(selected_report['view'])
                view_func = getattr(module, selected_report['function_name'])
                
                # Use inspect to check if the view function accepts 'tenant_id'.
                # This is more explicit and less "magic" than a try/except.
                view_signature = inspect.signature(view_func)
                
                if 'tenant_id' in view_signature.parameters:
                    # The view is multi-tenant aware, pass the tenant_id.
                    print(f"Debug: Calling {view_func.__name__} with tenant_id")
                    response = view_func(request, tenant_id=tenant_id)
                else:
                    # The view is not multi-tenant aware, call it without the tenant_id.
                    print(f"Debug: Calling {view_func.__name__} without tenant_id (legacy mode)")
                    response = view_func(request)
            
            except (ImportError, AttributeError) as e:
                # Handle cases where the module or function doesn't exist
                print(f"Error: Could not import report view. {e}")
                return HttpResponseForbidden("Report view not found.")
            
            # This part of your code handles the response context.
            if hasattr(response, 'context_data'):
                context = response.context_data.copy()
                if 'context_data' in context:
                    context.update(context.pop('context_data'))
            else:
                context = response.context_data = response.context
            
            return render(request, selected_report['template'], context)

        return HttpResponseForbidden("You do not have access to this report.")
    
    return render(request, 'report_app/hub.html', {'reports': accessible_reports})