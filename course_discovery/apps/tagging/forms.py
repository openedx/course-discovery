from django import forms


class CSVUploadForm(forms.Form):
    """
    Form for uploading CSV file to support bulk upload feature
    """
    csv_file = forms.FileField(label="Upload CSV File")
