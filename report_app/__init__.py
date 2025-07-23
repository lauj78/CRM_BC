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
        'name': 'Inactive User Report',
        'category': 'Retention Management',
        'view': 'report_app.reports.report_inactive_users.views',
        'function_name': 'report_inactive_users_view',
        'template': 'report_app/reports/report_inactive_users/view.html',
        'access': ['admin', 'op'],
        'params': ['start_date', 'end_date']
    },
    {
        'name': 'Top Deposit Users',
        'category': 'Revenue Management',
        'view': 'report_app.reports.report_top_deposit_users.views',
        'function_name': 'report_top_deposit_users_view',
        'template': 'report_app/reports/report_top_deposit_users/view.html',
        'access': ['admin', 'op'],
        'params': ['start_date', 'end_date', 'top_n']
    },
    {
        'name': 'Top Withdrawal Users',
        'category': 'Revenue Management',
        'view': 'report_app.reports.report_top_withdrawal_users.views',
        'function_name': 'report_top_withdrawal_users_view',
        'template': 'report_app/reports/report_top_withdrawal_users/view.html',
        'access': ['admin', 'op'],
        'params': ['start_date', 'end_date', 'top_n']
    },
    {
        'name': 'Member and Transaction Count',
        'category': 'Member Management',
        'view': 'report_app.reports.report_dummy_test.views',
        'function_name': 'member_transaction_count_view',
        'template': 'report_app/reports/report_dummy_test/view.html',
        'access': ['admin', 'op']
    },
    
]