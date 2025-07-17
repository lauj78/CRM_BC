from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
import pandas as pd
from .forms import UploadFileForm
from .models import Member, Transaction, ErrorLog
from django.http import HttpResponse, FileResponse
import csv
from io import StringIO, BytesIO
from datetime import datetime
import os
from django.conf import settings
from django.utils import timezone
import pytz
from decimal import Decimal
import re

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('data_management:upload_file')  # Updated from 'upload_file'
        else:
            return render(request, 'login.html', {'error': 'Invalid credentials'})
    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('data_management:login')

@login_required
def upload_file(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            file_type = form.cleaned_data['file_type']

            # Validate file is CSV
            if not file.name.lower().endswith('.csv'):
                return render(request, 'data_management/upload.html', {
                    'form': form,
                    'error': 'Please install a file with .csv extension.'
                })
            if file.content_type not in ['text/csv', 'application/vnd.ms-excel']:
                return render(request, 'data_management/upload.html', {
                    'form': form,
                    'error': 'Invalid file type. Please upload a CSV file.'
                })

            try:
                file_content = file.read().decode('utf-8-sig')
                file_like_object = StringIO(file_content)
                df = pd.read_csv(file_like_object, sep=None, engine='python', quotechar='"', encoding='utf-8-sig')  # Handle quoted fields

                errors = []
                valid_records = []
                upload_time = timezone.now()

                for index, row in df.iterrows():
                    try:
                        if file_type == 'members':
                            if not all(row.get(field) for field in ['Username', 'Name', 'Handphone', 'Join Date']):
                                errors.append({
                                    'row': index + 2,
                                    'error': 'Missing mandatory fields',
                                    'data': row.to_dict()
                                })
                                continue
                            join_date_str = str(row['Join Date'])
                            join_date = pd.to_datetime(join_date_str, format='%d/%m/%Y %H:%M', errors='coerce')  # Primary format
                            if pd.isna(join_date):
                                join_date = pd.to_datetime(join_date_str, format='%d-%m-%Y %H:%M', errors='coerce')  # Fallback for hyphens
                                if pd.isna(join_date):
                                    raise ValueError(f"Invalid date format for Join Date at row {index + 2}: {join_date_str}")
                            join_date = timezone.make_aware(join_date, timezone.get_current_timezone()).astimezone(pytz.UTC)
                            Member.objects.create(
                                username=row['Username'],
                                name=row['Name'],
                                referral=row.get('Referral', ''),
                                handphone=row['Handphone'],
                                join_date=join_date,
                                email=row.get('Email', '')
                            )
                            valid_records.append(row.to_dict())
                        elif file_type in ['deposit', 'manual_deposit', 'withdraw', 'manual_withdraw']:
                            if not all(row.get(field) for field in ['USERNAME', 'EVENT', 'AMOUNT', 'CREATE DATE', 'PROCESS DATE']):
                                errors.append({
                                    'row': index + 2,
                                    'error': 'Missing mandatory fields',
                                    'data': row.to_dict()
                                })
                                continue
                            create_date_str = str(row['CREATE DATE'])
                            process_date_str = str(row['PROCESS DATE'])
                            create_date = pd.to_datetime(create_date_str, format='%d/%m/%Y %H:%M', errors='coerce')  # Primary format
                            process_date = pd.to_datetime(process_date_str, format='%d/%m/%Y %H:%M', errors='coerce')  # Primary format
                            if pd.isna(create_date):
                                create_date = pd.to_datetime(create_date_str, format='%d-%m-%Y %H:%M', errors='coerce')  # Fallback for hyphens
                                if pd.isna(create_date):
                                    raise ValueError(f"Invalid date format for CREATE DATE at row {index + 2}: {create_date_str}")
                            if pd.isna(process_date):
                                process_date = pd.to_datetime(process_date_str, format='%d-%m-%Y %H:%M', errors='coerce')  # Fallback for hyphens
                                if pd.isna(process_date):
                                    raise ValueError(f"Invalid date format for PROCESS DATE at row {index + 2}: {process_date_str}")
                            create_date = timezone.make_aware(create_date, timezone.get_current_timezone()).astimezone(pytz.UTC)
                            process_date = timezone.make_aware(process_date, timezone.get_current_timezone()).astimezone(pytz.UTC)

                            # Clean and convert amount with quote and comma handling
                            amount_str = str(row['AMOUNT']).strip('"')  # Remove quotes
                            cleaned_amount = re.sub(r'[^\d.]', '', amount_str)  # Remove commas and non-numeric
                            if not cleaned_amount:
                                raise ValueError(f"Invalid amount format at row {index + 2}: {amount_str}")
                            amount = Decimal(cleaned_amount)

                            # Create transaction with individual save to catch unique constraint errors
                            transaction = Transaction(
                                username=row['USERNAME'],
                                event=file_type.replace('_', ' ').title(),
                                amount=amount,
                                create_date=create_date,
                                process_date=process_date,
                                process_by=row.get('PROCESS BY', '')
                            )
                            transaction.save()  # Save individually to handle exceptions
                            valid_records.append(row.to_dict())
                    except Exception as e:
                        errors.append({
                            'row': index + 2,
                            'error': str(e),
                            'data': row.to_dict()
                        })

                if errors:
                    timestamp = upload_time.strftime('%Y%m%d_%H%M%S')
                    file_name = f"{timestamp}_{file_type}_{len(errors)}error{len(valid_records)}success_log.csv"
                    file_path = os.path.join(settings.MEDIA_ROOT, 'error_logs', file_name)
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    with open(file_path, 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(['Row', 'Error', 'Row Data'])
                        for error in errors:
                            writer.writerow([error['row'], error['error'], str(error['data'])])

                    ErrorLog.objects.create(
                        file_name=file_name,
                        file_path=file_path,
                        upload_time=upload_time,
                        file_type=file_type,
                        error_count=len(errors),
                        success_count=len(valid_records)
                    )

                    request.session['upload_summary'] = {
                        'file_name': file.name,
                        'file_type': file_type,
                        'record_count': len(valid_records),
                        'error_count': len(errors),
                        'upload_time': upload_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'first_record': valid_records[0] if valid_records else None,
                        'last_record': valid_records[-1] if valid_records else None,
                        'first_error': errors[0] if errors else None,
                        'last_error': errors[-1] if errors else None,
                        'error_log_path': file_path if errors else None
                    }
                    return redirect('data_management:upload_summary')

                return render(request, 'data_management/upload_success.html', {
                    'file_name': file.name,
                    'record_count': len(valid_records),
                    'upload_time': upload_time,
                    'first_record': valid_records[0] if valid_records else None,
                    'last_record': valid_records[-1] if valid_records else None,
                    'file_type': file_type
                })
            except Exception as e:
                return render(request, 'data_management/upload.html', {'form': form, 'error': str(e)})
        else:
            return render(request, 'data_management/upload.html', {'form': form, 'error': 'Invalid form submission'})
    else:
        form = UploadFileForm()
        return render(request, 'data_management/upload.html', {'form': form})

@login_required
def upload_success(request):
    return render(request, 'data_management/upload_success.html')

@login_required
def upload_summary(request):
    summary = request.session.get('upload_summary', {})
    if not summary:
        return render(request, 'data_management/upload_summary.html', {'error': 'No upload summary available.'})
    return render(request, 'data_management/upload_summary.html', {
        'file_name': summary.get('file_name'),
        'file_type': summary.get('file_type'),
        'record_count': summary.get('record_count', 0),
        'error_count': summary.get('error_count', 0),
        'upload_time': summary.get('upload_time'),
        'first_record': summary.get('first_record'),
        'last_record': summary.get('last_record'),
        'first_error': summary.get('first_error'),
        'last_error': summary.get('last_error'),
        'error_log_path': summary.get('error_log_path')
    })

@login_required
def download_errors(request):
    summary = request.session.get('upload_summary', {})
    errors = summary.get('first_error', {}).get('data', []) if summary.get('error_count', 0) > 0 else []
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Row', 'Error', 'Row Data'])
    if errors:
        writer.writerow([summary.get('first_error', {}).get('row'), summary.get('first_error', {}).get('error'), str(summary.get('first_error', {}).get('data'))])
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="errors.csv"'
    response.write(output.getvalue())
    return response

@login_required
def error_logs_list(request):
    logs = ErrorLog.objects.order_by('-upload_time')
    return render(request, 'data_management/error_logs_list.html', {'logs': logs})

@login_required
def download_log(request, log_id):
    log = ErrorLog.objects.get(id=log_id)
    return FileResponse(open(log.file_path, 'rb'), as_attachment=True, filename=log.file_name)

@login_required
def delete_log(request, log_id):
    if request.method == 'POST':
        log = ErrorLog.objects.get(id=log_id)
        if os.path.exists(log.file_path):
            os.remove(log.file_path)
        log.delete()
        return redirect('data_management:error_logs_list')
    return redirect('data_management:error_logs_list')