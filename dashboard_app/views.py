from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from importlib import import_module
from .models import OperatorLog
from django.urls import reverse
import logging

# Set up logging
logger = logging.getLogger(__name__)

@login_required
def dynamic_dashboard(request):
    # Dynamically load available reports from report_app/reports/
    available_reports = []
    report_modules = ['report_dummy_test']  # Expand as more reports are added
    for module_name in report_modules:
        try:
            module = import_module(f'report_app.reports.{module_name}.views')
            available_reports.append(module.report_metadata)
        except ImportError as e:
            logger.error(f"Failed to load report module {module_name}: {e}")
            continue

    displayed_report = None
    if request.method == 'POST':
        logger.debug("Processing POST request")
        selected_report_name = request.POST.get('selected_report')
        logger.debug(f"Selected report name: {selected_report_name}")
        selected_report = next((r for r in available_reports if r['name'] == selected_report_name), None)
        if selected_report:
            logger.debug(f"Found selected report: {selected_report['name']}")
            # Call the report view and get its context
            response = selected_report['view'](request)
            if hasattr(response, 'context_data'):
                context = response.context_data.copy()  # Create a copy to avoid modifying the original
                context['name'] = selected_report['name']
                displayed_report = context
                logger.debug(f"Displayed report context: {context}")
            else:
                logger.warning("Response has no context_data")
            OperatorLog.objects.create(user=request.user, action=f"Viewed dashboard with report: {selected_report_name}")
        else:
            logger.warning(f"No report found for name: {selected_report_name}")
    else:
        OperatorLog.objects.create(user=request.user, action="Viewed dashboard")

    return render(request, 'dashboard_app/dashboard.html', {
        'available_reports': available_reports,
        'displayed_report': displayed_report,
    })

@login_required
def upload_view(request):
    return redirect(reverse('data_management:upload_file'))  # Redirect to data_management upload view