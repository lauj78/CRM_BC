from django.shortcuts import render
from importlib import import_module
from django.http import Http404

def report_view(request, report_name):
    try:
        # Map report_name to submodule
        module_path = f'report_app.reports.{report_name}.views'
        module = import_module(module_path)
        view_func = module.report_metadata['view']
        # Call the report view and render its template
        response = view_func(request)
        if hasattr(response, 'context_data'):
            context = response.context_data
            context['name'] = module.report_metadata['name']
            return render(request, module.report_metadata['template'], context)
        return response
    except (ImportError, KeyError, AttributeError):
        raise Http404("Report not found")