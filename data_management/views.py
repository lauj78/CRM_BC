from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
import pandas as pd
from .forms import UploadFileForm
from .models import Member, Transaction, ErrorLog
from django.http import HttpResponse, FileResponse, HttpResponseForbidden, HttpResponseRedirect
from django.urls import reverse
import csv
from io import StringIO
from django.conf import settings
from django.utils import timezone
import pytz
from decimal import Decimal
import re
import os
import uuid

# Hardcoded standard event types
STANDARD_EVENTS = ['Deposit', 'Manual Deposit', 'Withdraw', 'Manual Withdraw']


@login_required
def upload_file(request, tenant_id=None):
    # Setup
    request_id = uuid.uuid4().hex[:8]
    tenant = getattr(request, 'tenant', None)
    db_alias = tenant.db_alias if tenant else 'default'
    
    print(f"\n{'='*80}")
    print(f"DEBUG: START REQUEST {request_id}")
    print(f"Tenant: {tenant.tenant_id if tenant else 'default'}")
    print(f"Database: {db_alias}")
    print(f"Method: {request.method}")
    print(f"{'='*80}\n")
    
    # Check for duplicate processing
    if request.method == 'POST' and request.session.get('upload_in_progress'):
        print(f"DEBUG: REQUEST {request_id} - DUPLICATE DETECTED")
        return HttpResponse("Upload already in progress", status=400)
    
    if request.method == 'POST':
        # Set upload in progress flag
        request.session['upload_in_progress'] = True
        
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            file_type = form.cleaned_data['file_type']
            
            print(f"\n{'='*80}")
            print(f"DEBUG: REQUEST {request_id} - FILE METADATA")
            print(f"File: {file.name} ({file.size} bytes)")
            print(f"Type: {file_type}")
            print(f"{'='*80}\n")
            
            # File validation
            if not file.name.lower().endswith('.csv'):
                error = 'Please upload a file with .csv extension.'
                request.session.pop('upload_in_progress', None)
                return render(request, 'data_management/upload.html', {
                    'form': form,
                    'error': error,
                    'tenant_id': tenant_id or getattr(request.tenant, 'tenant_id', None)
                })
                
            if file.content_type not in ['text/csv', 'application/vnd.ms-excel']:
                error = 'Invalid file type. Please upload a CSV file.'
                request.session.pop('upload_in_progress', None)
                return render(request, 'data_management/upload.html', {
                    'form': form,
                    'error': error,
                    'tenant_id': tenant_id or getattr(request.tenant, 'tenant_id', None)
                })

            try:
                # Read and validate file content
                raw_bytes = file.read()  
                print(f"DEBUG: Read {len(raw_bytes)} bytes from file")
    
                # Handle empty file
                if len(raw_bytes) == 0:
                    if file.size > 0:
                        print("DEBUG: File read empty but size > 0 - retrying")
                        file.seek(0)
                        raw_bytes = file.read()
                        print(f"DEBUG: After retry, read {len(raw_bytes)} bytes")
                    
                    if len(raw_bytes) == 0:
                        error = 'Uploaded file is empty'
                        request.session.pop('upload_in_progress', None)
                        return render(request, 'data_management/upload.html', {
                            'form': form,
                            'error': error,
                            'tenant_id': tenant_id or getattr(request.tenant, 'tenant_id', None)
                        })
    
                # Decode content
                try:
                    file_content = raw_bytes.decode('utf-8-sig')
                except UnicodeDecodeError:
                    file_content = raw_bytes.decode('latin-1')
    
                print("\n" + "="*80)
                print("DEBUG: DECODED CONTENT (first 500 chars):")
                print(file_content[:500])
                print("="*80 + "\n")
                
                # Process CSV
                try:
                    df = pd.read_csv(
                        StringIO(file_content), 
                        sep=',',
                        engine='python', 
                        quotechar='"'
                    )
                except pd.errors.EmptyDataError:
                    error = 'CSV file is empty'
                    request.session.pop('upload_in_progress', None)
                    return render(request, 'data_management/upload.html', {
                        'form': form,
                        'error': error,
                        'tenant_id': tenant_id or getattr(request.tenant, 'tenant_id', None)
                    })
                
                print("\n" + "="*80)
                print("DEBUG: DATAFRAME INFO")
                print(f"Shape: {df.shape}")
                print(f"Columns: {df.columns.tolist()}")
                
                if not df.empty:
                    print("\nFirst 2 rows:")
                    for i in range(min(2, len(df))):
                        print(f"Row {i}: {df.iloc[i].to_dict()}")
                else:
                    print("DataFrame is empty")
                print("="*80 + "\n")
                    
                # Process records
                errors = []
                valid_records = []
                upload_time = timezone.now()

                for index, row in df.iterrows():
                    try:
                        if file_type == 'member':
                            required_fields = ['Username', 'Name', 'Handphone', 'Join Date']
                            if not all(row.get(field) is not None and not pd.isna(row[field]) and str(row[field]).strip() != '' for field in required_fields):
                                missing_field = next((field for field in required_fields if not row.get(field) or pd.isna(row[field]) or str(row[field]).strip() == ''), None)
                                errors.append({
                                    'row': index + 2,
                                    'error': f"Missing field: {missing_field}" if missing_field else 'Missing mandatory fields',
                                    'data': row.to_dict()
                                })
                                continue
                                
                            # Parse join date
                            join_date_str = str(row['Join Date']).strip()
                            join_date = pd.to_datetime(join_date_str, dayfirst=True, errors='coerce')
                            if pd.isna(join_date):
                                raise ValueError(f"Invalid date format: {join_date_str}")
                                
                            if join_date.hour == 0 and join_date.minute == 0 and join_date.second == 0:
                                raise ValueError(f"Missing time component: {join_date_str}")
                                
                            if join_date.second == 0 and join_date.minute > 0:
                                join_date = join_date.replace(second=0)
                                
                            join_date = timezone.make_aware(join_date, timezone.get_current_timezone()).astimezone(pytz.UTC)
                            
                            # Create member
                            print(f"DEBUG: Creating Member in {db_alias}: {row['Username']}")
                            Member.objects.using(db_alias).create(
                                username=row['Username'],
                                name=row['Name'],
                                referral=row.get('Referral', ''),
                                handphone=row['Handphone'],
                                join_date=join_date,
                                email=row.get('Email', '')
                            )
                            valid_records.append(row.to_dict())
                            
                        elif file_type == 'transaction':
                            required_fields = ['USERNAME', 'EVENT', 'AMOUNT', 'CREATE DATE', 'PROCESS DATE', 'PROCESS BY']
                            if not all(row.get(field) is not None and not pd.isna(row[field]) and str(row[field]).strip() != '' for field in required_fields):
                                missing_field = next((field for field in required_fields if not row.get(field) or pd.isna(row[field]) or str(row[field]).strip() == ''), None)
                                errors.append({
                                    'row': index + 2,
                                    'error': f"Missing field: {missing_field}" if missing_field else 'Missing mandatory fields',
                                    'data': row.to_dict()
                                })
                                continue
                                
                            # Parse dates
                            create_date = pd.to_datetime(str(row['CREATE DATE']).strip(), dayfirst=True, errors='coerce')
                            process_date = pd.to_datetime(str(row['PROCESS DATE']).strip(), dayfirst=True, errors='coerce')
                            
                            if pd.isna(create_date):
                                raise ValueError(f"Invalid CREATE DATE: {row['CREATE DATE']}")
                            if pd.isna(process_date):
                                raise ValueError(f"Invalid PROCESS DATE: {row['PROCESS DATE']}")
                                
                            if create_date.hour == 0 and create_date.minute == 0 and create_date.second == 0:
                                raise ValueError(f"Missing time in CREATE DATE")
                            if process_date.hour == 0 and process_date.minute == 0 and process_date.second == 0:
                                raise ValueError(f"Missing time in PROCESS DATE")
                                
                            create_date = timezone.make_aware(create_date, timezone.get_current_timezone()).astimezone(pytz.UTC)
                            process_date = timezone.make_aware(process_date, timezone.get_current_timezone()).astimezone(pytz.UTC)

                            # Validate event
                            event = str(row['EVENT']).strip()
                            event_lower = event.lower()
                            if event_lower not in [e.lower() for e in STANDARD_EVENTS]:
                                raise ValueError(f"Invalid event: {event}")
                                
                            standardized_event = next(e for e in STANDARD_EVENTS if e.lower() == event_lower)

                            # Process amount
                            amount_str = str(row['AMOUNT']).strip('"')
                            cleaned_amount = re.sub(r'[^\d.]', '', amount_str)
                            if not cleaned_amount:
                                raise ValueError(f"Invalid amount: {amount_str}")
                                
                            amount = Decimal(cleaned_amount)

                            # Create transaction
                            print(f"DEBUG: Creating Transaction in {db_alias}: {row['USERNAME']}, {amount}")
                            transaction = Transaction(
                                username=row['USERNAME'],
                                event=standardized_event,
                                amount=amount,
                                create_date=create_date,
                                process_date=process_date,
                                process_by=row['PROCESS BY']
                            )
                            transaction.save(using=db_alias)
                            valid_records.append(row.to_dict())
                            
                    except Exception as e:
                        errors.append({
                            'row': index + 2,
                            'error': str(e),
                            'data': row.to_dict()
                        })

                # Clear upload flag
                request.session.pop('upload_in_progress', None)

                # Handle results - Simple redirect like File 2 but with robust HttpResponseRedirect
                if errors:
                    # Create error log file
                    if tenant:
                        tenant_id_clean = re.sub(r'[^\w\.-]', '', tenant.tenant_id)
                    else:
                        tenant_id_clean = 'default'
                                            
                    timestamp = upload_time.strftime('%Y%m%d_%H%M%S')
                    file_name = f"{timestamp}_{file_type}_{len(errors)}error{len(valid_records)}success_log.csv"
                    tenant_dir = os.path.join(settings.MEDIA_ROOT, 'error_logs', tenant_id_clean)
                    os.makedirs(tenant_dir, exist_ok=True)
                    file_path = os.path.join(tenant_dir, file_name)
                                            
                    with open(file_path, 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(['Row', 'Error', 'Row Data'])
                        for error in errors:
                            writer.writerow([error['row'], error['error'], str(error['data'])])

                    # Create error log using correct tenant_id (domain string)
                    print(f"DEBUG: Creating ErrorLog in {db_alias}: {file_name}")
                    print(f"DEBUG: Tenant: {tenant.tenant_id if tenant else None} (ID: {tenant.id if tenant else None})")
                    ErrorLog.objects.using(db_alias).create(
                        tenant_id=tenant.tenant_id,  # Pass the tenant's domain string
                        file_name=file_name,
                        file_path=file_path,
                        upload_time=upload_time,
                        file_type=file_type,
                        error_count=len(errors),
                        success_count=len(valid_records)
                    )
                    
                    # Store summary in session (keep data for display)
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
                        'error_log_path': file_path,
                        'all_errors': errors,
                        'tenant_id': tenant.tenant_id if tenant else 'default'
                    }
                    
                    return HttpResponseRedirect(
                        reverse('data_management:upload_summary', 
                                kwargs={'tenant_id': tenant.tenant_id if tenant else 'default'}),
                        status=303
                    )
                    
                # Handle success
                else:
                    request.session['upload_success'] = {
                        'file_name': file.name,
                        'record_count': len(valid_records),
                        'upload_time': upload_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'first_record': valid_records[0] if valid_records else None,
                        'last_record': valid_records[-1] if valid_records else None,
                        'file_type': file_type,
                        'tenant_id': tenant.tenant_id if tenant else 'default'
                    }
                    
                    return HttpResponseRedirect(
                        reverse('data_management:upload_success', 
                                kwargs={'tenant_id': tenant.tenant_id if tenant else 'default'}),
                        status=303
                    )
                    
            except Exception as e:
                # Clear upload flag on error
                request.session.pop('upload_in_progress', None)
                print(f"DEBUG: REQUEST {request_id} - Exception: {str(e)}")
                return render(request, 'data_management/upload.html', {
                    'form': form,
                    'error': str(e),
                    'tenant_id': tenant_id or getattr(request.tenant, 'tenant_id', None)
                })
                
        else:
            # Clear upload flag on invalid form
            request.session.pop('upload_in_progress', None)
            return render(request, 'data_management/upload.html', {
                'form': form,
                'error': 'Invalid form submission',
                'tenant_id': tenant_id or getattr(request.tenant, 'tenant_id', None)
            })
    else:
        form = UploadFileForm()
        return render(request, 'data_management/upload.html', {
            'form': form,
            'tenant_id': tenant_id or getattr(request.tenant, 'tenant_id', None)
        })
    
    print(f"\n{'='*80}")
    print(f"DEBUG: END REQUEST {request_id}")
    print(f"{'='*80}\n")

@login_required
def upload_success(request, tenant_id=None):
    print(f"\n{'='*80}")
    print("DEBUG: REACHED UPLOAD_SUCCESS VIEW")
    print(f"{'='*80}\n")
    
    # Retrieve and remove session data to prevent reuse
    success_data = request.session.pop('upload_success', {})
    
    # Fallback to URL parameter if tenant_id not in session
    tenant_id = success_data.get('tenant_id', tenant_id)
    
    return render(request, 'data_management/upload_success.html', {
        'file_name': success_data.get('file_name'),
        'record_count': success_data.get('record_count'),
        'upload_time': success_data.get('upload_time'),
        'first_record': success_data.get('first_record'),
        'last_record': success_data.get('last_record'),
        'file_type': success_data.get('file_type'),
        'tenant_id': tenant_id or getattr(request.tenant, 'tenant_id', None)
    }) 

@login_required
def upload_summary(request, tenant_id=None):
    # Retrieve and remove session data to prevent reuse
    summary = request.session.pop('upload_summary', {})
    
    # Fallback to URL parameter if tenant_id not in session
    tenant_id = summary.get('tenant_id', tenant_id)
    
    if not summary:
        return render(request, 'data_management/upload_summary.html', {
            'error': 'No upload summary available.',
            'tenant_id': tenant_id or getattr(request.tenant, 'tenant_id', 'default')
        })
        
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
        'error_log_path': summary.get('error_log_path'),
        'tenant_id': tenant_id or getattr(request.tenant, 'tenant_id', 'default'),
        'all_errors': summary.get('all_errors', [])
    })

@login_required
def download_errors(request, tenant_id=None):
    summary = request.session.get('upload_summary', {})
    errors = summary.get('all_errors', [])
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Row', 'Error', 'Row Data'])
    for error in errors:
        writer.writerow([error['row'], error['error'], str(error['data'])])
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="errors.csv"'
    response.write(output.getvalue())
    return response

@login_required
def error_logs_list(request, tenant_id=None):
    tenant = getattr(request, 'tenant', None)
    try:
        db_alias = tenant.db_alias if tenant else 'default'
        
        # Query ErrorLogs from tenant database, but filter by tenant ID string
        logs = ErrorLog.objects.using(db_alias).filter(
            tenant_id=tenant.tenant_id if tenant else 'default'
        ).order_by('-upload_time')
            
        return render(request, 'data_management/error_logs_list.html', {
            'logs': logs,
            'tenant_id': tenant_id or getattr(request.tenant, 'tenant_id', None)
        })
        
    except Exception as e:
        print(f"Database error: {e}")
        raise

@login_required
def download_log(request, log_id, tenant_id=None):
    tenant = getattr(request, 'tenant', None)
    try:
        db_alias = tenant.db_alias if tenant else 'default'
        
        log = ErrorLog.objects.using(db_alias).get(
            id=log_id,
            tenant_id=tenant.tenant_id if tenant else 'default'
        )
        return FileResponse(open(log.file_path, 'rb'), as_attachment=True, filename=log.file_name)
        
    except ErrorLog.DoesNotExist:
        return HttpResponseForbidden("Access denied")

@login_required
def delete_log(request, log_id, tenant_id=None):
    if request.method == 'POST':
        tenant = getattr(request, 'tenant', None)
        try:
            db_alias = tenant.db_alias if tenant else 'default'
            
            log = ErrorLog.objects.using(db_alias).get(
                id=log_id,
                tenant_id=tenant.tenant_id if tenant else 'default'
            )
            
            if os.path.exists(log.file_path):
                os.remove(log.file_path)
            log.delete(using=db_alias)
            return redirect('data_management:error_logs_list')
            
        except ErrorLog.DoesNotExist:
            return HttpResponseForbidden("Access denied")
            
    return redirect('data_management:error_logs_list')


@login_required
def bulk_delete_logs(request, tenant_id=None):
    if request.method == 'POST':
        tenant = getattr(request, 'tenant', None)
        try:
            db_alias = tenant.db_alias if tenant else 'default'
            
            # Get selected log IDs from POST data
            selected_logs_str = request.POST.get('selected_logs', '')
            if not selected_logs_str:
                return redirect('data_management:error_logs_list', tenant_id=tenant_id)
            
            # Convert string to list of integers
            log_ids = []
            for log_id in selected_logs_str.split(','):
                if log_id.isdigit():
                    log_ids.append(int(log_id))
            
            if not log_ids:
                return redirect('data_management:error_logs_list', tenant_id=tenant_id)
            
            # Get the logs to be deleted
            logs_to_delete = ErrorLog.objects.using(db_alias).filter(
                id__in=log_ids,
                tenant_id=tenant.tenant_id if tenant else 'default'
            )
            
            # Delete physical files and database records
            deleted_count = 0
            for log in logs_to_delete:
                try:
                    if os.path.exists(log.file_path):
                        os.remove(log.file_path)
                    log.delete(using=db_alias)
                    deleted_count += 1
                except Exception as e:
                    print(f"Error deleting log {log.id}: {e}")
            
            print(f"Bulk deleted {deleted_count} error logs")
            
        except Exception as e:
            print(f"Bulk delete error: {e}")
            
    return redirect('data_management:error_logs_list', tenant_id=tenant_id)