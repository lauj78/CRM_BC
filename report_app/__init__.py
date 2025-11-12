# report_app/__init__.py
REPORTS = [
    {
        'name': 'Daily Summary',
        'category': 'Transaction Management',
        'view': 'report_app.reports.report_daily_summary.views',
        'function_name': 'report_daily_summary_view',
        'template': 'report_app/reports/report_daily_summary/view.html',
        #'access': ['admin', 'op'],
        'params': ['start_date', 'end_date'],
        'description': 'A daily overview of transactions, including deposit and withdrawal summaries.'
    },
    {
        'name': 'Daily General Transaction Summary',
        'category': 'Transaction Management',
        'view': 'report_app.reports.report_daily_general_transaction_summary.views',
        'function_name': 'report_daily_general_transaction_summary_view',
        'template': 'report_app/reports/report_daily_general_transaction_summary/view.html',
        'params': ['start_date', 'end_date'],
        'description': 'A detailed daily summary focusing on deposit frequency, user age, and key financial ratios.'
    },  
    {
        'name': 'User Engagement Report',
        'category': 'Retention Management',
        'view': 'report_app.reports.report_user_engagement.views',
        'function_name': 'report_user_engagement_view',
        'template': 'report_app/reports/report_user_engagement/view.html',
        #'access': ['admin', 'op'],
        'params': ['start_date', 'end_date'],
        'description': 'Analyze user activity over a specific time period, and show each user total deposit and withdrawal within that period'
    },
    {
        'name': 'New Member Deposit Activity',
        'category': 'Retention Management',
        'view': 'report_app.reports.report_new_member_deposit_activity.views',
        'function_name': 'report_new_member_deposit_activity_view',
        'template': 'report_app/reports/report_new_member_deposit_activity/view.html',
        'params': ['reg_start_date', 'reg_end_date', 'dep_start_date', 'dep_end_date'],
        'description': 'Track deposit behavior of newly registered members across different time periods.'
    },
    {
        'name': 'Inactive Withdrawers',
        'category': 'Retention Management',
        'view': 'report_app.reports.report_inactive_withdrawers.views',
        'function_name': 'report_inactive_withdrawers_view',
        'template': 'report_app/reports/report_inactive_withdrawers/view.html',
        'params': ['wd_start_date', 'wd_end_date', 'inactive_days'],
        'description': 'Find members who made withdrawals but haven\'t been active recently - for reactivation campaigns.'
    },
    {
        'name': 'Inactive Depositors',
        'category': 'Retention Management',
        'view': 'report_app.reports.report_inactive_depositors.views',
        'function_name': 'report_inactive_depositors_view',
        'template': 'report_app/reports/report_inactive_depositors/view.html',
        'params': ['dep_start_date', 'dep_end_date', 'inactive_days'],
        'description': "Find members who made deposits but haven't been active recently - for re-engagement campaigns."
    },          
    {
        'name': 'Top Deposit Users',
        'category': 'Revenue Management',
        'view': 'report_app.reports.report_top_deposit_users.views',
        'function_name': 'report_top_deposit_users_view',
        'template': 'report_app/reports/report_top_deposit_users/view.html',
        #'access': ['admin', 'op'],
        'params': ['start_date', 'end_date', 'top_n'],
        'description': 'Find the top users by deposit amount within a specified date range.'
    },
    {
        'name': 'Top Withdrawal Users',
        'category': 'Revenue Management',
        'view': 'report_app.reports.report_top_withdrawal_users.views',
        'function_name': 'report_top_withdrawal_users_view',
        'template': 'report_app/reports/report_top_withdrawal_users/view.html',
        #'access': ['admin', 'op'],
        'params': ['start_date', 'end_date', 'top_n'],
        'description': 'Find the top users by withdrawal amount within a specified date range.'
    },
    {
        'name': 'Member and Transaction Count',
        'category': 'Data Management',
        'view': 'report_app.reports.report_dummy_test.views',
        'function_name': 'member_transaction_count_view',
        'template': 'report_app/reports/report_dummy_test/view.html',
        #'access': ['admin', 'op'],
        'description': 'Calculate database size (count of members and transactions).'
    },
    {
        'name': 'User Phone Lookup',
        'category': 'Member Management',
        'view': 'report_app.reports.report_user_phone_lookup.views',
        'function_name': 'report_user_phone_lookup_view',
        'template': 'report_app/reports/report_user_phone_lookup/view.html',
        #'access': ['admin', 'op'],
        'params': [],
        'description': 'Search for a user phone number by their usernames.'
    }, 
    {
        'name': 'Phone number to user Lookup',
        'category': 'Member Management',
        'view': 'report_app.reports.report_phone_user_lookup.views',
        'function_name': 'report_phone_user_lookup_view',
        'template': 'report_app/reports/report_phone_user_lookup/view.html',
        #'access': ['admin', 'op'],
        'params': [],
        'description': 'Search for a User detal  by their pphone usernames.'
    }, 
    {
        'name': 'Duplicate Phone Numbers',
        'category': 'Member Management',
        'view': 'report_app.reports.report_duplicated_phone_number.views',
        'function_name': 'report_duplicated_phone_number_view',
        'template': 'report_app/reports/report_duplicated_phone_number/view.html',
        # 'access': ['admin', 'op'],
        'params': ['phone_number', 'start_date', 'end_date'],
        'description': 'Identify user accounts with duplicate phone numbers.'
    },
    {
        'name': 'User Management',
        'category': 'Member Management',
        'view': 'report_app.reports.report_user_management.views',
        'function_name': 'report_user_management_view',
        'template': 'report_app/reports/report_user_management/view.html',
        'params': [],
        'description': 'Search, edit, and delete user accounts.'
    },
    
    
]