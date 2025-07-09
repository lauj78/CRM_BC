from django import forms

class UploadFileForm(forms.Form):
    file = forms.FileField()
    file_type = forms.ChoiceField(choices=[
        ('members', 'Members'),
        ('deposit', 'Deposit'),
        ('manual_deposit', 'Manual Deposit'),
        ('withdraw', 'Withdraw'),
        ('manual_withdraw', 'Manual Withdraw'),
    ])
    # Remove the event field since it's now part of file_type