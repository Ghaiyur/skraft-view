from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("api/metrics/", views.metrics_api, name="metrics-api"),
    path("api/session/heartbeat/", views.session_heartbeat, name="session-heartbeat"),
    path("api/session/close/", views.session_close, name="session-close"),
    path("api/quit/", views.quit_app, name="quit-app"),
]
