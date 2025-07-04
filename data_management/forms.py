
from django import forms

class UploadFileForm(forms.Form):
    file = forms.FileField()
    file_type = forms.ChoiceField(choices=[
        ('members', 'New Members'),
        ('deposits', 'Deposits'),
        ('withdrawals', 'Withdrawals')
    ])