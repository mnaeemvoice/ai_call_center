from django import forms
from .models import CallCredential, CallScript

class CredentialForm(forms.ModelForm):
    class Meta:
        model = CallCredential
        fields = ['ami_host', 'ami_port', 'ami_user', 'ami_pass', 'sip_endpoint']  # comma fixed
        widgets = {
            'ami_pass': forms.PasswordInput(attrs={'placeholder': 'Enter AMI Password'}),
        }

class ScriptForm(forms.ModelForm):
    class Meta:
        model = CallScript
        fields = ['country', 'script_text']
        widgets = {
            'script_text': forms.Textarea(attrs={
                'rows': 6, 
                'cols': 40,
                'placeholder': 'اپنا اسکرپٹ یہاں لکھیں...'
            }),
        }

class CallScriptForm(forms.ModelForm):
    credential = forms.ModelChoiceField(
        queryset=CallCredential.objects.all(),
        label="Select Credential",
        empty_label="Choose SIP Credential"
    )
    exten = forms.CharField(label="Destination Number", max_length=20)
    caller_id = forms.CharField(label="Caller ID", max_length=50, initial="AI Call Center")

    class Meta:
        model = CallScript
        fields = ['country', 'script_text', 'credential', 'exten', 'caller_id']
