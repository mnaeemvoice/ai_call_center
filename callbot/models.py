from django.db import models

class CallCredential(models.Model):
    ami_host = models.CharField(max_length=100)
    ami_port = models.IntegerField(default=5038)
    ami_user = models.CharField(max_length=50)
    ami_pass = models.CharField(max_length=50)
    sip_endpoint = models.CharField(max_length=100, blank=True, null=True)  # New SIP field

    def __str__(self):
        return f"{self.ami_user} @ {self.ami_host}"


class CallScript(models.Model):
    country = models.CharField(max_length=50)
    script_text = models.TextField()
    credential = models.ForeignKey(
        CallCredential,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        default=21  # Replace with your default CallCredential ID
    )
    exten = models.CharField(max_length=20, default='1000')       # Destination number
    caller_id = models.CharField(max_length=50, default='AI Call Center')  # Caller ID

    def __str__(self):
        return f"{self.country} script"


class CallLog(models.Model):
    user_script = models.ForeignKey(CallScript, on_delete=models.CASCADE)
    ai_response = models.TextField()
    audio_path = models.CharField(max_length=200, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)


class CallQueue(models.Model):
    script = models.ForeignKey(CallScript, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, default='Queued')
    timestamp = models.DateTimeField(auto_now_add=True)


class Credential(models.Model):
    country = models.CharField(max_length=50)
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=100)
    api_key = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return f"{self.country} - {self.username}"


class UserProfile(models.Model):
    country = models.CharField(max_length=50)
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.username} ({self.country})"
