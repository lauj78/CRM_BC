# report_app/__init__.py
REPORTS = [
    {
        'name': 'Daily Summary',
        'category': 'Transaction Management',
        'view': 'report_app.reports.report_daily_summary.views',
        'function_name': 'report_daily_summary_view',  # Updated to match the function name
        'template': 'report_app/reports/report_daily_summary/view.html',
        'access': ['admin', 'op'],
        'params': ['start_date', 'end_date']
    },
    {
        'name': 'Member and Transaction Count',
        'category': 'Member Management',
        'view': 'report_app.reports.report_dummy_test.views',
        'function_name': 'member_transaction_count_view',
        'template': 'report_app/reports/report_dummy_test/view.html',
        'access': ['admin', 'op'],
    }
]