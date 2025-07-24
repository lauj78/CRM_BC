from django.shortcuts import render, redirect
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
                            required_fields = ['Username', 'Name', 'Handphone', 'Join Date']
                            if not all(row.get(field) is not None and not pd.isna(row[field]) and str(row[field]).strip() != '' for field in required_fields):
                                missing_field = next((field for field in required_fields if not row.get(field) or pd.isna(row[field]) or str(row[field]).strip() == ''), None)
                                errors.append({
                                    'row': index + 2,
                                    'error': f"Missing or empty field: {missing_field}" if missing_field else 'Missing mandatory fields',
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
                            required_fields = ['USERNAME', 'EVENT', 'AMOUNT', 'CREATE DATE', 'PROCESS DATE', 'PROCESS BY']
                            if not all(row.get(field) is not None and not pd.isna(row[field]) and str(row[field]).strip() != '' for field in required_fields):
                                missing_field = next((field for field in required_fields if not row.get(field) or pd.isna(row[field]) or str(row[field]).strip() == ''), None)
                                errors.append({
                                    'row': index + 2,
                                    'error': f"Missing or empty field: {missing_field}" if missing_field else 'Missing mandatory fields',
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

                            # Clean and convert amount with enhanced validation
                            amount_str = str(row['AMOUNT']).strip('"')  # Remove quotes
                            cleaned_amount = re.sub(r'[^\d.]', '', amount_str)  # Remove non-numeric except decimal
                            if not cleaned_amount:
                                raise ValueError(f"Invalid amount format at row {index + 2}: {amount_str}")
                            # Allow commas as thousand separators; check for other non-numeric characters
                            non_numeric = ''.join(c for c in amount_str if c not in cleaned_amount and c not in ',')
                            if non_numeric and not all(c.isdigit() or c == ',' for c in amount_str.replace(cleaned_amount, '')):
                                raise ValueError(f"Invalid amount format at row {index + 2}: {amount_str} (non-numeric characters detected)")
                            amount = Decimal(cleaned_amount)

                            # Create transaction with individual save to catch unique constraint errors
                            transaction = Transaction(
                                username=row['USERNAME'],
                                event=file_type.replace('_', ' ').title(),
                                amount=amount,
                                create_date=create_date,
                                process_date=process_date,
                                process_by=row['PROCESS BY']  # Removed default empty string
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