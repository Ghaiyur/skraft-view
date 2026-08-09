from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("api/metrics/", views.metrics_api, name="metrics-api"),
    path("api/history/", views.history_api, name="history-api"),
    path("api/alerts/", views.alerts_api, name="alerts-api"),
    path(
        "api/alerts/acknowledge/",
        views.acknowledge_alert_api,
        name="acknowledge-alert-api",
    ),
    path("api/alert-events/", views.alerts_api, name="alert-events-api"),
    path("api/session/heartbeat/", views.session_heartbeat, name="session-heartbeat"),
    path("api/session/close/", views.session_close, name="session-close"),
    path("api/quit/", views.quit_app, name="quit-app"),
]
