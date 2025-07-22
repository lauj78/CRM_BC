# report_app/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponseForbidden
from importlib import import_module
from . import REPORTS

@login_required
def report_hub_view(request):
    user_groups = [g.name for g in request.user.groups.all()]
    print(f"Debug: User groups: {user_groups}")  # Debug output
    accessible_reports = [
        r for r in REPORTS if not r.get('access') or any(group in r['access'] for group in user_groups)
    ]
    print(f"Debug: Accessible reports: {accessible_reports}")  # Debug output
    if request.GET.get('report'):
        selected_report = next((r for r in REPORTS if r['name'] == request.GET['report']), None)
        if selected_report and (not selected_report.get('access') or any(group in selected_report['access'] for group in user_groups)):
            module = import_module(selected_report['view'])
            view_func = getattr(module, selected_report['function_name'])
            response = view_func(request)
            if hasattr(response, 'context_data'):
                context = response.context_data.copy()  # Unwrap context_data
                if 'context_data' in context:
                    context.update(context.pop('context_data'))  # Merge nested context_data
            else:
                context = response.context_data = response.context  # Fallback
            # print(f"Debug: Rendered context: {context}")  # Debug the final context
            return render(request, selected_report['template'], context)
        return HttpResponseForbidden("You do not have access to this report.")
    return render(request, 'report_app/hub.html', {'reports': accessible_reports})