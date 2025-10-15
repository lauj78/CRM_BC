#report_app/reports/report_phone_user_lookup/views.py 

from django.contrib.auth.decorators import login_required
from django.template.response import TemplateResponse
from django.utils import timezone
from data_management.models import Member
import csv
import io
import re

@login_required
def report_phone_user_lookup_view(request):
    """
    Reverse lookup: Search for user details by phone number
    """
    results = []
    error_message = None
    
    # Handle initial lookup - NOTE THE request.GET.get('report') CHECK!
    if request.method == "POST" and request.GET.get('report') == 'Phone number to user Lookup' and not request.POST.get('_export'):
        phones_input = request.POST.get("phone_numbers", "").strip()
        if phones_input:
            phone_numbers = [p.strip() for p in phones_input.split("\n") if p.strip()]
            
            if len(phone_numbers) > 2000:
                error_message = "Error: Input exceeds 2000 phone numbers. Please limit to 2000 per request."
            else:
                # Normalize phone numbers for search
                normalized_phones = []
                phone_mapping = {}  # Map normalized to original
                
                for phone in phone_numbers:
                    # Remove all non-digit characters
                    digits_only = re.sub(r'\D', '', phone)
                    
                    # Handle different formats
                    if digits_only.startswith('65') and len(digits_only) == 10:
                        normalized = digits_only[2:]  # Remove country code
                    else:
                        normalized = digits_only
                    
                    normalized_phones.append(normalized)
                    phone_mapping[normalized] = phone  # Store original format
                
                # Search in database
                members = Member.objects.filter(
                    handphone__in=normalized_phones
                ).values("username", "name", "handphone", "join_date")
                
                # Create lookup dictionary
                member_dict = {}
                for m in members:
                    # Normalize the database phone too
                    db_phone = re.sub(r'\D', '', m["handphone"] or "")
                    if db_phone.startswith('65') and len(db_phone) == 10:
                        db_phone = db_phone[2:]
                    member_dict[db_phone] = m
                
                # Build results maintaining input order
                for normalized_phone in normalized_phones:
                    original_phone = phone_mapping[normalized_phone]
                    
                    if normalized_phone in member_dict:
                        member = member_dict[normalized_phone]
                        # Format phone number for display
                        display_phone = member["handphone"]
                        if display_phone and not display_phone.startswith("+"):
                            display_phone = f"+65{display_phone}" if display_phone.isdigit() and len(display_phone) == 8 else display_phone
                        
                        results.append({
                            "search_phone": original_phone,
                            "username": member["username"],
                            "name": member["name"],
                            "handphone": display_phone,
                            "join_date": member["join_date"],
                            "status": "Found"
                        })
                    else:
                        results.append({
                            "search_phone": original_phone,
                            "username": "Not Found",
                            "name": "Not Found",
                            "handphone": original_phone,
                            "join_date": None,
                            "status": "Not Found"
                        })
        else:
            error_message = "Please enter phone numbers to look up."

    # Handle export (POST with _export=csv)
    if request.method == 'POST' and request.POST.get('_export', '').lower() == 'csv' and (results or request.POST.get('phone_numbers')):
        phones_input = request.POST.get("phone_numbers", "").strip()
        if phones_input:
            phone_numbers = [p.strip() for p in phones_input.split("\n") if p.strip()]
            
            if len(phone_numbers) > 2000:
                error_message = "Error: Input exceeds 2000 phone numbers. Please limit to 2000 per request."
            else:
                # Same logic as above
                normalized_phones = []
                phone_mapping = {}
                
                for phone in phone_numbers:
                    digits_only = re.sub(r'\D', '', phone)
                    if digits_only.startswith('65') and len(digits_only) == 10:
                        normalized = digits_only[2:]
                    else:
                        normalized = digits_only
                    
                    normalized_phones.append(normalized)
                    phone_mapping[normalized] = phone
                
                members = Member.objects.filter(
                    handphone__in=normalized_phones
                ).values("username", "name", "handphone", "join_date")
                
                member_dict = {}
                for m in members:
                    db_phone = re.sub(r'\D', '', m["handphone"] or "")
                    if db_phone.startswith('65') and len(db_phone) == 10:
                        db_phone = db_phone[2:]
                    member_dict[db_phone] = m
                
                for normalized_phone in normalized_phones:
                    original_phone = phone_mapping[normalized_phone]
                    
                    if normalized_phone in member_dict:
                        member = member_dict[normalized_phone]
                        display_phone = member["handphone"]
                        if display_phone and not display_phone.startswith("+"):
                            display_phone = f"+65{display_phone}" if display_phone.isdigit() and len(display_phone) == 8 else display_phone
                        
                        results.append({
                            "search_phone": original_phone,
                            "username": member["username"],
                            "name": member["name"],
                            "handphone": display_phone,
                            "join_date": member["join_date"],
                            "status": "Found"
                        })
                    else:
                        results.append({
                            "search_phone": original_phone,
                            "username": "Not Found",
                            "name": "Not Found",
                            "handphone": original_phone,
                            "join_date": None,
                            "status": "Not Found"
                        })
        else:
            error_message = "Please enter phone numbers to look up."

        # Generate CSV
        csv_content = io.StringIO()
        writer = csv.writer(csv_content)
        writer.writerow(['Search Phone', 'Username', 'Name', 'Handphone', 'Join Date', 'Status'])
        
        for result in results:
            join_date_str = result['join_date'].strftime('%Y-%m-%d %H:%M:%S') if result['join_date'] else 'Not Found'
            writer.writerow([
                result['search_phone'],
                result['username'],
                result['name'],
                result['handphone'],
                join_date_str,
                result['status']
            ])
        
        csv_data = csv_content.getvalue()
        csv_content.close()
        
        context = {
            'results': results,
            'error_message': error_message,
            'csv_data': csv_data,
            'filename': f"phone_user_lookup_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        }
        return TemplateResponse(request, 'report_app/reports/report_phone_user_lookup/view.html', {'context_data': context})

    # Render the template for non-export requests
    context = {
        'results': results,
        'error_message': error_message,
    }
    return TemplateResponse(request, 'report_app/reports/report_phone_user_lookup/view.html', {'context_data': context})