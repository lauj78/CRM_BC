from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.contrib import messages
from data_management.models import Member
from django.utils import timezone

@login_required
def report_user_management_view(request):
    results = []
    error_message = None
    success_message = None
    
    # DEBUG: Print to terminal
    print("="*50)
    print(f"USER MANAGEMENT - Method: {request.method}")
    print(f"GET params: {request.GET}")
    print(f"POST params: {request.POST}")
    print("="*50)
    
    # Handle deletion
    if request.method == "POST" and request.POST.get('action') == 'delete':
        username = request.POST.get('username')
        print(f"DELETING user: {username}")
        try:
            member = Member.objects.get(username=username)
            member.delete()
            success_message = f"User '{username}' deleted successfully."
            print("Delete successful")
        except Member.DoesNotExist:
            error_message = f"User '{username}' not found."
            print("User not found")
        except Exception as e:
            error_message = f"Error deleting user: {str(e)}"
            print(f"Error: {e}")
    
    # Handle update
    if request.method == "POST" and request.POST.get('action') == 'update':
        username = request.POST.get('username')
        print(f"UPDATING user: {username}")
        try:
            member = Member.objects.get(username=username)
            member.name = request.POST.get('name', member.name)
            member.handphone = request.POST.get('handphone', member.handphone)
            member.email = request.POST.get('email', member.email)
            member.referral = request.POST.get('referral', member.referral)
            member.save()
            success_message = f"User '{username}' updated successfully."
            print("Update successful")
        except Member.DoesNotExist:
            error_message = f"User '{username}' not found."
            print("User not found")
        except Exception as e:
            error_message = f"Error updating user: {str(e)}"
            print(f"Error: {e}")
    
    # Handle search
    if request.method == "POST" and request.POST.get('action') == 'search':
        usernames_input = request.POST.get("usernames", "").strip()
        print(f"SEARCHING for: '{usernames_input}'")
        
        if usernames_input:
            usernames = [u.strip() for u in usernames_input.split("\n") if u.strip()]
            print(f"Parsed usernames: {usernames}")
            
            if len(usernames) > 100:
                error_message = "Error: Input exceeds 100 usernames. Please limit to 100 per request."
            else:
                members = Member.objects.filter(username__in=usernames)
                print(f"Found {members.count()} members in database")
                
                for member in members:
                    handphone = member.handphone
                    if handphone and not handphone.startswith("+"):
                        handphone = f"+65{handphone}" if handphone.isdigit() and len(handphone) == 8 else handphone
                    
                    results.append({
                        "username": member.username,
                        "name": member.name,
                        "handphone": handphone,
                        "email": member.email,
                        "referral": member.referral,
                        "join_date": member.join_date
                    })
                
                print(f"Results built: {len(results)} users")
                
                # Check for not found users
                found_usernames = {r['username'] for r in results}
                not_found = [u for u in usernames if u not in found_usernames]
                if not_found:
                    error_message = f"Users not found: {', '.join(not_found)}"
                    print(f"Not found: {not_found}")
        else:
            error_message = "Please enter usernames to search."
            print("No usernames provided")
    
    context = {
        'results': results,
        'error_message': error_message,
        'success_message': success_message,
        'usernames_input': request.POST.get('usernames', '')
    }
    
    print(f"Final context - results: {len(results)}, error: {error_message}")
    print("="*50)
    
    return TemplateResponse(request, 'report_app/reports/report_user_management/view.html', {'context_data': context})