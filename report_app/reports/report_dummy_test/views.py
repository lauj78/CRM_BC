from django.shortcuts import render
from django.template.response import TemplateResponse
from data_management.models import Member, Transaction

def member_transaction_count_view(request):
    total_members = Member.objects.count()
    total_transactions = Transaction.objects.count()
    context = {
        'total_members': total_members,
        'total_transactions': total_transactions,
    }
    return TemplateResponse(request, 'report_app/reports/report_dummy_test/view.html', context)

report_metadata = {
    'name': 'Member and Transaction Count',
    'view': member_transaction_count_view,
    'template': 'report_app/reports/report_dummy_test/view.html',
    'filter_form': None  # No filters for this dummy report
}