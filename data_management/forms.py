from django import forms

class UploadFileForm(forms.Form):
    file = forms.FileField()
    file_type = forms.ChoiceField(
        choices=[
            ('member', 'Member'),
            ('transaction', 'Transaction'),
        ],
        widget=forms.RadioSelect, # This line adds the radio button widget
        label="File Type" # Add a label to ensure it displays correctly
    )