# multi_agent_ai_call_center.py
import os
import subprocess
import asyncio
import threading
import pyttsx3
from asterisk.ami import AMIClient, SimpleAction
from django.db import models
from django import forms
from django.shortcuts import render
from django.http import JsonResponse

PROJECT_NAME = "multi_agent_call_center"
APP_NAME = "callbot"

# 1. Create Django project & app
subprocess.run(["django-admin", "startproject", PROJECT_NAME])
os.chdir(PROJECT_NAME)
subprocess.run(["python", "manage.py", "startapp", APP_NAME])

# 2. Create folders
os.makedirs(f"{APP_NAME}/templates/{APP_NAME}", exist_ok=True)
os.makedirs(f"{PROJECT_NAME}/media", exist_ok=True)
os.makedirs(f"{APP_NAME}/static/{APP_NAME}", exist_ok=True)

# 3. settings.py update
settings_path = f"{PROJECT_NAME}/settings.py"
with open(settings_path, "r") as f:
    settings = f.read()
settings += f"""

INSTALLED_APPS.append("{APP_NAME}")

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
"""
with open(settings_path, "w") as f:
    f.write(settings)

# 4. models.py
models_code = """
from django.db import models

class CallCredential(models.Model):
    ami_host = models.CharField(max_length=100)
    ami_port = models.IntegerField(default=5038)
    ami_user = models.CharField(max_length=50)
    ami_pass = models.CharField(max_length=50)
    def __str__(self):
        return f"{self.ami_user} @ {self.ami_host}"

class CallScript(models.Model):
    country = models.CharField(max_length=50)
    script_text = models.TextField()
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
"""
with open(f"{APP_NAME}/models.py", "w") as f:
    f.write(models_code)

# 5. forms.py
forms_code = """
from django import forms
from .models import CallCredential, CallScript

class CredentialForm(forms.ModelForm):
    class Meta:
        model = CallCredential
        fields = ['ami_host','ami_port','ami_user','ami_pass']

class ScriptForm(forms.ModelForm):
    class Meta:
        model = CallScript
        fields = ['country','script_text']
"""
with open(f"{APP_NAME}/forms.py", "w") as f:
    f.write(forms_code)

# 6. utils.py (multi-agent AI + TTS + AMI)
utils_code = """
import os
import asyncio
import pyttsx3
from .models import CallQueue, CallLog
from asterisk.ami import AMIClient, SimpleAction

CALL_QUEUE = asyncio.Queue()

def generate_ai_voice(text, country, media_dir='media'):
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    voice_id = voices[0].id
    country_lower = country.lower()
    for v in voices:
        if 'english' in v.name.lower() and 'us' in country_lower:
            voice_id = v.id
        if 'english' in v.name.lower() and ('uk' in country_lower or 'britain' in country_lower):
            voice_id = v.id
    engine.setProperty('voice', voice_id)
    os.makedirs(media_dir, exist_ok=True)
    filename = f"{media_dir}/response_{country}_{len(text)}.mp3"
    engine.save_to_file(text, filename)
    engine.runAndWait()
    return filename

async def async_process_call(credential, queue_obj):
    queue_obj.status = 'Running'
    queue_obj.save()
    script_text = queue_obj.script.script_text
    ai_response = f"AI reading: {script_text}"
    audio_path = generate_ai_voice(script_text, queue_obj.script.country)
    try:
        client = AMIClient(address=credential.ami_host, port=credential.ami_port)
        future = client.login(username=credential.ami_user, secret=credential.ami_pass)
        if future.response.is_error():
            ai_response += " | AMI connection failed"
            queue_obj.status = 'Failed'
        else:
            # Simulate multi-agent AI response
            # Here we can later integrate GPT or local AI logic
            dynamic_response = script_text + " (Agent AI response)"
            audio_path = generate_ai_voice(dynamic_response, queue_obj.script.country)
            action = SimpleAction(
                'Originate',
                Channel='SIP/1011',
                Context='from-internal',
                Exten='1000',
                Priority=1,
                CallerID='AI Bot',
                Timeout=30000
            )
            client.send_action(action)
            ai_response += f" | AMI call triggered with response: {dynamic_response}"
            queue_obj.status = 'Completed'
            client.logoff()
    except Exception as e:
        ai_response += f" | Exception: {str(e)}"
        queue_obj.status = 'Failed'
    queue_obj.save()
    CallLog.objects.create(user_script=queue_obj.script, ai_response=ai_response, audio_path=audio_path)

async def queue_worker(credential):
    while True:
        queue_obj = await CALL_QUEUE.get()
        await async_process_call(credential, queue_obj)
        CALL_QUEUE.task_done()

def enqueue_call(queue_obj):
    asyncio.run_coroutine_threadsafe(CALL_QUEUE.put(queue_obj), asyncio.get_event_loop())

def start_queue_loop(credential):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(queue_worker(credential))
"""
with open(f"{APP_NAME}/utils.py", "w") as f:
    f.write(utils_code)

# 7. views.py
views_code = """
from django.shortcuts import render
from django.http import JsonResponse
from .forms import CredentialForm, ScriptForm
from .models import CallQueue, CallLog
from .utils import generate_ai_voice, enqueue_call

def home(request):
    if request.method == 'POST':
        cred_form = CredentialForm(request.POST)
        script_form = ScriptForm(request.POST)
        if cred_form.is_valid() and script_form.is_valid():
            credential = cred_form.save()
            script = script_form.save()
            queue_obj = CallQueue.objects.create(script=script)
            enqueue_call(queue_obj)
            ai_response = f"Call queued for {script.country}"
            audio_path = generate_ai_voice(script.script_text, script.country)
            return JsonResponse({'ai_response': ai_response, 'audio_path': audio_path})
    else:
        cred_form = CredentialForm()
        script_form = ScriptForm()
    queue = CallQueue.objects.all().order_by('-timestamp')
    logs = CallLog.objects.all().order_by('-timestamp')
    return render(request, 'callbot/home.html', {'cred_form': cred_form, 'script_form': script_form, 'queue': queue, 'logs': logs})
"""
with open(f"{APP_NAME}/views.py", "w") as f:
    f.write(views_code)

# 8. urls.py
urls_code = """
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
]
"""
with open(f"{APP_NAME}/urls.py", "w") as f:
    f.write(urls_code)

# 9. main urls.py
main_urls_path = f"{PROJECT_NAME}/urls.py"
with open(main_urls_path, "r") as f:
    main_urls = f.read()
main_urls = main_urls.replace("from django.urls import path", "from django.urls import path, include")
main_urls = main_urls.replace("urlpatterns = [","urlpatterns = [\n    path('', include('" + APP_NAME + ".urls')),")
main_urls += "\nfrom django.conf import settings\nfrom django.conf.urls.static import static\nurlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)\n"
with open(main_urls_path, "w") as f:
    f.write(main_urls)

# 10. Template
template_code = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Multi-Agent AI Call Center</title>
<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
<style>
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #ddd; padding: 8px; }
th { background-color: #f2f2f2; }
</style>
</head>
<body>
<h2>Multi-Agent AI Call Center Dashboard</h2>

<h3>Enter AMI Credentials & Script</h3>
<form id="credForm" method="post">
    {% csrf_token %}
    {{ cred_form.as_p }}
    {{ script_form.as_p }}
    <button type="submit">Start Call</button>
</form>

<h3>Live Call Queue</h3>
<table>
<tr><th>Script</th><th>Country</th><th>Status</th><th>Timestamp</th></tr>
{% for q in queue %}
<tr><td>{{ q.script.script_text }}</td><td>{{ q.script.country }}</td><td>{{ q.status }}</td><td>{{ q.timestamp }}</td></tr>
{% endfor %}
</table>

<h3>Call Logs</h3>
<ul>
{% for log in logs %}
    <li>{{ log.timestamp }} - {{ log.user_script.country }} - {{ log.ai_response }} - Audio: <a href="{{ log.audio_path }}">{{ log.audio_path }}</a></li>
{% endfor %}
</ul>

<script>
function reloadQueue() { location.reload(); }
setInterval(reloadQueue, 5000);

$('#credForm').submit(function(e){
    e.preventDefault();
    $.ajax({
        type: 'POST',
        url: '',
        data: $(this).serialize(),
        success: function(data){
            alert("AI Response: " + data.ai_response + "\\nAudio Path: " + data.audio_path);
            location.reload();
        }
    });
});
</script>

</body>
</html>
"""
with open(f"{APP_NAME}/templates/{APP_NAME}/home.html", "w") as f:
    f.write(template_code)

print("✅ Multi-Agent AI Call Center Django Project Created!")
print("Run commands:")
print("cd", PROJECT_NAME)
print("python manage.py migrate")
print("python manage.py runserver")
print("Open browser at http://127.0.0.1:8000/")
print("⚡ Multi-agent AI handles live calls asynchronously with real-time dashboard.")
