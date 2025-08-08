# report_app/reports/report_duplicated_phone_number/views.py
import csv
import io
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from data_management.models import Member
from django.template.response import TemplateResponse
from django.http import HttpResponseBadRequest
from django.utils import timezone
from datetime import timedelta

@login_required
def report_duplicated_phone_number_view(request):
    duplicate_phone_data = []
    phone_number_query = request.GET.get('phone_number', '').strip()
    search_all = request.GET.get('search_all', 'false').lower() == 'true'

    # Initialize date string variables to None to prevent UnboundLocalError
    start_date_str = None
    end_date_str = None

    base_queryset = Member.objects.all()

    # Handle date range filtering
    if search_all:
        start_date = None
        end_date = None
    else:
        # Get dates from the request, or set a default to the last 30 days
        start_date_param = request.GET.get('start_date')
        end_date_param = request.GET.get('end_date')

        if start_date_param and end_date_param:
            try:
                start_date = timezone.datetime.strptime(start_date_param, '%Y-%m-%d').date()
                end_date = timezone.datetime.strptime(end_date_param, '%Y-%m-%d').date()
                if start_date > end_date:
                    return HttpResponseBadRequest("Start date cannot be after end date.")
                start_date_str = start_date_param
                end_date_str = end_date_param
            except ValueError:
                return HttpResponseBadRequest("Invalid date format. Use YYYY-MM-DD.")
        else:
            # Default to the last 30 days if no dates are provided and 'Search All' is not selected.
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=30)
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')

        base_queryset = base_queryset.filter(join_date__date__range=[start_date, end_date])

    if phone_number_query:
        members_with_phone = base_queryset.filter(handphone=phone_number_query).order_by('username')
        if members_with_phone.count() > 1:
            duplicate_phone_data.append({
                'handphone': phone_number_query,
                'users': list(members_with_phone),
                'user_count': members_with_phone.count(),
            })
    else:
        duplicate_phones_qs = base_queryset.values('handphone').annotate(
            user_count=Count('username')
        ).filter(user_count__gt=1).order_by('handphone')

        for phone in duplicate_phones_qs:
            handphone = phone['handphone']
            users = base_queryset.filter(handphone=handphone).order_by('username')
            duplicate_phone_data.append({
                'handphone': handphone,
                'users': list(users),
                'user_count': phone['user_count'],
            })

    # Pagination for the list of duplicate phone numbers
    paginator = Paginator(duplicate_phone_data, 20)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # Handle CSV Export
    if request.method == 'POST' and request.POST.get('_export', '').lower() == 'csv':
        csv_content = io.StringIO()
        writer = csv.writer(csv_content)

        writer.writerow(['Phone Number', 'Username', 'Name', 'Join Date', 'Email', 'Referral'])

        for item in duplicate_phone_data:
            for user in item['users']:
                writer.writerow([
                    item['handphone'],
                    user.username,
                    user.name,
                    user.join_date.strftime('%Y-%m-%d %H:%M:%S'),
                    user.email,
                    user.referral
                ])

        csv_data = csv_content.getvalue()
        csv_content.close()

        context = {
            'page_obj': page_obj,
            'phone_number_query': phone_number_query,
            'start_date': start_date_str,
            'end_date': end_date_str,
            'search_all': search_all,
            'csv_data': csv_data,
            'filename': f"duplicate_phone_numbers_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv",
        }
        return TemplateResponse(request, 'report_app/reports/report_duplicated_phone_number/view.html', context)

    context = {
        'page_obj': page_obj,
        'phone_number_query': phone_number_query,
        'start_date': start_date_str,
        'end_date': end_date_str,
        'search_all': search_all,
    }

    return TemplateResponse(request, 'report_app/reports/report_duplicated_phone_number/view.html', context)