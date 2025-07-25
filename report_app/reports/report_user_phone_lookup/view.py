from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from datetime import timedelta
from django.utils import timezone
import calendar
from data_management.models import Transaction, Member
from django.template.response import TemplateResponse

@login_required
def report_user_phone_lookup_view(request):
    results = []
    error_message = None
    if request.method == "POST" and request.GET.get('report') == 'User Phone Lookup':
        usernames_input = request.POST.get("usernames", "").strip()
        if usernames_input:
            usernames = [u.strip() for u in usernames_input.split("\n") if u.strip()]
            if len(usernames) > 2000:
                error_message = "Error: Input exceeds 2000 usernames. Please limit to 2000 per request."
            else:
                members = Member.objects.filter(username__in=usernames).values("username", "name", "handphone")
                member_dict = {m["username"]: m for m in members}
                for username in usernames:
                    member = member_dict.get(username, {"username": username, "name": "Not Found", "handphone": "Not Found"})
                    handphone = member["handphone"]
                    if handphone and not handphone.startswith("+"):
                        handphone = f"+65{handphone}" if handphone.isdigit() and len(handphone) == 8 else handphone
                    results.append({
                        "username": username,
                        "name": member["name"],
                        "handphone": handphone
                    })
        else:
            error_message = "Please enter usernames to look up."
    context = {
        "results": results,
        "error_message": error_message,
    }
    return TemplateResponse(request, "report_app/reports/report_user_phone_lookup/view.html", context)