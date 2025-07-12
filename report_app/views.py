from django.http import Http404
import importlib

def report_view(request, report_name):
    print(f"Attempting to load report: {report_name}")  # Debug print
    try:
        module = importlib.import_module(f'report_app.reports.{report_name}.views')
        print(f"Module loaded: {module}")  # Debug print
        view_func = getattr(module, f'{report_name}_view')
        print(f"Found view function: {view_func}")  # Debug print
        return view_func(request)
    except (ImportError, AttributeError) as e:
        print(f"Error: {e}")  # Debug print
        raise Http404("Report not found")