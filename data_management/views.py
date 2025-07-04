from django.shortcuts import render, redirect
import pandas as pd
from .forms import UploadFileForm
from .models import Member, Transaction
from django.http import HttpResponse
import csv
from io import StringIO, BytesIO
from datetime import datetime

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
                for index, row in df.iterrows():
                    try:
                        if file_type == 'members':
                            # Validate mandatory fields
                            if not all(row.get(field) for field in ['Username', 'Name', 'Handphone', 'Join Date']):
                                errors.append(f"Row {index+2}: Missing mandatory fields")
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
                        elif file_type in ['deposits', 'withdrawals']:
                            # Validate mandatory fields
                            if not all(row.get(field) for field in ['USERNAME', 'EVENT', 'AMOUNT', 'CREATE DATE', 'PROCESS DATE']):
                                errors.append(f"Row {index+2}: Missing mandatory fields")
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
                    except Exception as e:
                        errors.append(f"Row {index+2}: {str(e)}")
                
                if errors:
                    # Generate CSV error report
                    output = StringIO()
                    writer = csv.writer(output)
                    writer.writerow(['Error'])
                    for error in errors:
                        writer.writerow([error])
                    response = HttpResponse(content_type='text/csv')
                    response['Content-Disposition'] = 'attachment; filename="errors.csv"'
                    response.write(output.getvalue())
                    return response
                return redirect('upload_success')
            except Exception as e:
                return render(request, 'data_management/upload.html', {'form': form, 'error': str(e)})
        else:
            return render(request, 'data_management/upload.html', {'form': form, 'error': 'Invalid form submission'})
    else:
        form = UploadFileForm()
    return render(request, 'data_management/upload.html', {'form': form})