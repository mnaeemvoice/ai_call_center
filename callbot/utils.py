
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
