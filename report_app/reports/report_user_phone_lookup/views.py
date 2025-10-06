from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from datetime import timedelta
from django.utils import timezone
import calendar
from data_management.models import Transaction, Member
from django.template.response import TemplateResponse
from django.http import HttpResponse, HttpResponseBadRequest
import csv
import io

@login_required
def report_user_phone_lookup_view(request):
    results = []
    error_message = None
    
    # Handle initial lookup
    if request.method == "POST" and request.GET.get('report') == 'User Phone Lookup' and not request.POST.get('_export'):
        usernames_input = request.POST.get("usernames", "").strip()
        if usernames_input:
            usernames = [u.strip() for u in usernames_input.split("\n") if u.strip()]
            if len(usernames) > 2000:
                error_message = "Error: Input exceeds 2000 usernames. Please limit to 2000 per request."
            else:
                # ADD join_date to the query
                members = Member.objects.filter(username__in=usernames).values("username", "name", "handphone", "join_date")
                member_dict = {m["username"]: m for m in members}
                for username in usernames:
                    member = member_dict.get(username, {
                        "username": username, 
                        "name": "Not Found", 
                        "handphone": "Not Found",
                        "join_date": None  # ADD this
                    })
                    handphone = member["handphone"]
                    if handphone and not handphone.startswith("+"):
                        handphone = f"+65{handphone}" if handphone.isdigit() and len(handphone) == 8 else handphone
                    results.append({
                        "username": username,
                        "name": member["name"],
                        "handphone": handphone,
                        "join_date": member["join_date"]  # ADD this
                    })
        else:
            error_message = "Please enter usernames to look up."

    # Handle export (POST with _export=csv)
    if request.method == 'POST' and request.POST.get('_export', '').lower() == 'csv' and (results or request.POST.get('usernames')):
        usernames_input = request.POST.get("usernames", "").strip()
        if usernames_input:
            usernames = [u.strip() for u in usernames_input.split("\n") if u.strip()]
            if len(usernames) > 2000:
                error_message = "Error: Input exceeds 2000 usernames. Please limit to 2000 per request."
            else:
                # ADD join_date to the query
                members = Member.objects.filter(username__in=usernames).values("username", "name", "handphone", "join_date")
                member_dict = {m["username"]: m for m in members}
                for username in usernames:
                    member = member_dict.get(username, {
                        "username": username, 
                        "name": "Not Found", 
                        "handphone": "Not Found",
                        "join_date": None  # ADD this
                    })
                    handphone = member["handphone"]
                    if handphone and not handphone.startswith("+"):
                        handphone = f"+65{handphone}" if handphone.isdigit() and len(handphone) == 8 else handphone
                    results.append({
                        "username": username,
                        "name": member["name"],
                        "handphone": handphone,
                        "join_date": member["join_date"]  # ADD this
                    })
        else:
            error_message = "Please enter usernames to look up."

        csv_content = io.StringIO()
        writer = csv.writer(csv_content)
        writer.writerow(['Username', 'Name', 'Handphone', 'Join Date'])  # ADD Join Date header
        for result in results:
            join_date_str = result['join_date'].strftime('%Y-%m-%d %H:%M:%S') if result['join_date'] else 'Not Found'
            writer.writerow([result['username'], result['name'], result['handphone'], join_date_str])
        csv_data = csv_content.getvalue()
        csv_content.close()
        context = {
            'results': results,
            'error_message': error_message,
            'csv_data': csv_data,
            'filename': f"user_phone_lookup_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        }
        return TemplateResponse(request, 'report_app/reports/report_user_phone_lookup/view.html', {'context_data': context})

    # Render the template for non-export requests
    context = {
        'results': results,
        'error_message': error_message,
    }
    return TemplateResponse(request, 'report_app/reports/report_user_phone_lookup/view.html', {'context_data': context})