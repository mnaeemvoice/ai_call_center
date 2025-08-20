from django.shortcuts import render, redirect
from django.http import JsonResponse
from .forms import CredentialForm, ScriptForm
from .models import CallQueue, CallLog, CallCredential, CallScript
from .utils import generate_ai_voice, enqueue_call
from .models import CallCredential
import requests 
from asterisk.ami import AMIClient, SimpleAction




# 🏠 Home View (Main Dashboard)
def home(request):
    if request.method == "POST":
        cred_form = CredentialForm(request.POST)
        script_form = ScriptForm(request.POST)

        if cred_form.is_valid() and script_form.is_valid():
            credential = cred_form.save()
            script = script_form.save()

            # Save to queue
            queue_obj = CallQueue.objects.create(script=script)
            enqueue_call(queue_obj)

            # Generate AI voice
            audio_path = generate_ai_voice(script.script_text, script.country)

            # AJAX response
            return JsonResponse({
                "status": "success",
                "ai_response": f"✅ Call queued for {script.country}",
                "audio_path": audio_path,
                "queue_html": render(request, "partials/queue.html", {"queue": CallQueue.objects.all()}).content.decode(),
                "logs_html": render(request, "partials/logs.html", {"logs": CallLog.objects.all()}).content.decode()
            })
        else:
            return JsonResponse({"status": "error", "errors": cred_form.errors | script_form.errors}, status=400)

    # GET request
    cred_form = CredentialForm()
    script_form = ScriptForm()
    queue = CallQueue.objects.all().order_by("-timestamp")
    logs = CallLog.objects.all().order_by("-timestamp")
    return render(request, "callbot/home.html", {
        "cred_form": cred_form,
        "script_form": script_form,
        "queue": queue,
        "logs": logs
    })



# ✅ Save AMI/Credentials
def save_credentials(request):
    if request.method == "POST":
        cred_form = CredentialForm(request.POST)
        if cred_form.is_valid():
            cred_form.save()
            return redirect("home")  # success -> home page
    else:
        cred_form = CredentialForm()

    return render(request, "credentials_form.html", {"form": cred_form})


# ✅ Save Call Script
def save_script(request):
    if request.method == "POST":
        script_form = ScriptForm(request.POST)
        if script_form.is_valid():
            script_form.save()
            return redirect("home")
    else:
        script_form = ScriptForm()

    return render(request, "script_form.html", {"form": script_form})


def get_queue_logs(request):
    queue = CallQueue.objects.select_related("script").values(
        "id", "status", "timestamp", "script__script_text", "script__country"
    )
    logs = CallLog.objects.select_related("user_script").values(
        "id", "ai_response", "timestamp", "audio_path", "user_script__country"
    )

    queue_data = [
        {
            "id": q["id"],
            "status": q["status"],
            "timestamp": q["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            "script_text": q["script__script_text"],
            "country": q["script__country"]
        } for q in queue
    ]

    logs_data = [
        {
            "id": l["id"],
            "ai_response": l["ai_response"],
            "timestamp": l["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            "audio_path": l["audio_path"],
            "country": l["user_script__country"]
        } for l in logs
    ]

    return JsonResponse({"queue": queue_data, "logs": logs_data})

def save_form(request):
    if request.method == "POST":
        print("POST request received")  # Server console
        cred_form = CredentialForm(request.POST)
        script_form = ScriptForm(request.POST)

        if cred_form.is_valid() and script_form.is_valid():
            print("Forms valid, saving data...")  # Server console
            credential = cred_form.save()
            script = script_form.save()

            # Queue the call
            queue_obj = CallQueue.objects.create(script=script)
            print("Calling enqueue_call()...")
            enqueue_call(queue_obj)  # Print inside this function will show in console

            # Generate AI audio
            audio_path = generate_ai_voice(script.script_text, script.country)

            return JsonResponse({
                "status": "success",
                "msg": f"✅ Data saved for {script.country}",
                "audio_path": audio_path
            })
        else:
            return JsonResponse({
                "status": "error",
                "errors": cred_form.errors | script_form.errors
            }, status=400)

    return JsonResponse({"status": "error", "msg": "Invalid request"}, status=400)

 # agar AMI API ya external service ho
# Agar aapka AMI server Asterisk hai to aap py-Asterisk ya pyst2 use kar sakte hain

def enqueue_call(queue_obj):
    try:
        # Get saved AMI credentials
        ami_host = queue_obj.script.credential.ami_host
        ami_port = queue_obj.script.credential.ami_port
        ami_user = queue_obj.script.credential.ami_user
        ami_pass = queue_obj.script.credential.ami_pass

        # Connect to AMI
        client = AMIClient(address=ami_host, port=ami_port)
        future = client.login(username=ami_user, secret=ami_pass)
        if not future.response.success:
            return f"❌ AMI login failed: {future.response}"

        # Originate call
        action = SimpleAction(
            'Originate',
            Channel=f'SIP/{queue_obj.script.country}',  # Replace with real SIP channel
            Context='from-internal',                     # Your Asterisk context
            Exten='1000',                                # Destination extension / number
            Priority=1,
            CallerID='AI Call Center',
            Async='true'
        )
        resp = client.send_action(action)
        client.logoff()

        # Save log in database
        CallLog.objects.create(
            user_script=queue_obj.script,
            ai_response=f"Call enqueued successfully",
            audio_path=""  # update if audio generated
        )

        print(f"✅ Call enqueued successfully: {queue_obj.script.script_text}")
        return f"✅ Call enqueued for: {queue_obj.script.script_text}"

    except Exception as e:
        print(f"❌ Error enqueuing call: {e}")
        return f"❌ Error: {e}"