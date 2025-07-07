from django.shortcuts import render, redirect
import pandas as pd
from .forms import UploadFileForm
from .models import Member, Transaction, ErrorLog
from django.http import HttpResponse, FileResponse
import csv
from io import StringIO, BytesIO
from datetime import datetime
import os
from django.conf import settings

def upload_file(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            file_type = form.cleaned_data['file_type']
            try:
                # Read file content into a BytesIO object
                file_content = file.read()
                file_like_object = BytesIO(file_content)

                # Read CSV or Excel
                if file.name.endswith('.csv'):
                    df = pd.read_csv(file_like_object, sep=None, engine='python')
                else:
                    df = pd.read_excel(file_like_object)

                errors = []
                valid_records = []
                upload_time = datetime.now()

                for index, row in df.iterrows():
                    try:
                        if file_type == 'members':
                            # Validate mandatory fields
                            if not all(row.get(field) for field in ['Username', 'Name', 'Handphone', 'Join Date']):
                                errors.append({
                                    'row': index + 2,
                                    'error': 'Missing mandatory fields',
                                    'data': row.to_dict()
                                })
                                continue
                            # Parse Join Date
                            join_date = pd.to_datetime(row['Join Date'], format='%d-%m-%Y %H:%M:%S')
                            Member.objects.create(
                                username=row['Username'],
                                name=row['Name'],
                                referral=row.get('Referral', ''),
                                handphone=row['Handphone'],
                                join_date=join_date,
                                email=row.get('Email', '')
                            )
                            valid_records.append(row.to_dict())
                        elif file_type in ['deposits', 'withdrawals']:
                            # Validate mandatory fields
                            if not all(row.get(field) for field in ['USERNAME', 'EVENT', 'AMOUNT', 'CREATE DATE', 'PROCESS DATE']):
                                errors.append({
                                    'row': index + 2,
                                    'error': 'Missing mandatory fields',
                                    'data': row.to_dict()
                                })
                                continue
                            # Parse dates
                            create_date = pd.to_datetime(row['CREATE DATE'], format='%d-%m-%Y %H:%M:%S')
                            process_date = pd.to_datetime(row['PROCESS DATE'], format='%d-%m-%Y %H:%M:%S')
                            Transaction.objects.create(
                                username=row['USERNAME'],
                                event='Deposit' if file_type == 'deposits' else 'Withdraw',
                                amount=float(row['AMOUNT']),
                                create_date=create_date,
                                process_date=process_date,
                                process_by=row.get('PROCESS BY', '')
                            )
                            valid_records.append(row.to_dict())
                    except Exception as e:
                        errors.append({
                            'row': index + 2,
                            'error': str(e),
                            'data': row.to_dict()
                        })

                if errors:
                    # Save error log file
                    timestamp = upload_time.strftime('%Y%m%d_%H%M%S')
                    file_name = f"{timestamp}_{file_type}_{len(errors)}error{len(valid_records)}success_log.csv"
                    file_path = os.path.join(settings.MEDIA_ROOT, 'error_logs', file_name)
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    with open(file_path, 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(['Row', 'Error', 'Row Data'])
                        for error in errors:
                            writer.writerow([error['row'], error['error'], str(error['data'])])

                    # Save metadata to ErrorLog
                    ErrorLog.objects.create(
                        file_name=file_name,
                        file_path=file_path,
                        upload_time=upload_time,
                        file_type=file_type,
                        error_count=len(errors),
                        success_count=len(valid_records)
                    )

                    # Store summary in session
                    request.session['upload_summary'] = {
                        'file_name': file.name,
                        'file_type': file_type,
                        'record_count': len(valid_records),
                        'error_count': len(errors),
                        'upload_time': upload_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'first_record': valid_records[0] if valid_records else None,
                        'last_record': valid_records[-1] if valid_records else None,
                        'first_error': errors[0] if errors else None,
                        'last_error': errors[-1] if errors else None
                    }
                    return redirect('upload_summary')

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

def upload_success(request):
    return render(request, 'data_management/upload_success.html')

def upload_summary(request):
    summary = request.session.get('upload_summary', {})
    return render(request, 'data_management/upload_summary.html', summary)

def download_errors(request):
    summary = request.session.get('upload_summary', {})
    errors = summary.get('errors', [])
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Row', 'Error', 'Row Data'])
    for error in errors:
        writer.writerow([error['row'], error['error'], str(error['data'])])
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="errors.csv"'
    response.write(output.getvalue())
    return response

def error_logs_list(request):
    logs = ErrorLog.objects.order_by('-upload_time')
    return render(request, 'data_management/error_logs_list.html', {'logs': logs})

def download_log(request, log_id):
    log = ErrorLog.objects.get(id=log_id)
    return FileResponse(open(log.file_path, 'rb'), as_attachment=True, filename=log.file_name)

def delete_log(request, log_id):
    if request.method == 'POST':
        log = ErrorLog.objects.get(id=log_id)
        if os.path.exists(log.file_path):
            os.remove(log.file_path)
        log.delete()
        return redirect('error_logs_list')
    return redirect('error_logs_list')