from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("get_queue_logs/", views.get_queue_logs, name="get_queue_logs"),
    path("save_credentials/", views.save_credentials, name="save_credentials"),
    path("save_script/", views.save_script, name="save_script"),
     path("save_form/", views.save_form, name="save_form"),
]
