import json

from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .history import (
    acknowledge_alert_event,
    annotate_alerts,
    build_alerts,
    get_recent_alert_events,
    get_recent_samples,
    history_payload,
    store_alert_events,
    store_metric_sample,
)
from .runtime_control import request_shutdown
from .session_state import close_session, touch_session
from .system import collect_inventory, collect_metrics


def home(request: HttpRequest):
    metrics = collect_metrics()
    alerts = build_alerts(metrics)
    annotated_alerts = annotate_alerts(alerts)
    store_metric_sample(metrics)
    store_alert_events(annotated_alerts)
    context = {
        "metrics": metrics,
        "inventory": collect_inventory(),
        "recent_samples": get_recent_samples(),
        "recent_alert_events": get_recent_alert_events(),
        "alerts": annotated_alerts,
    }
    return render(request, "dashboard/home.html", context)


def metrics_api(request: HttpRequest):
    metrics = collect_metrics()
    alerts = build_alerts(metrics)
    annotated_alerts = annotate_alerts(alerts)
    store_metric_sample(metrics)
    store_alert_events(annotated_alerts)
    metrics["alerts"] = annotated_alerts
    return JsonResponse(metrics)


def history_api(request: HttpRequest):
    range_key = request.GET.get("range", "24h")
    return JsonResponse(history_payload(range_key=range_key))


def alerts_api(request: HttpRequest):
    metrics = collect_metrics()
    alerts = build_alerts(metrics)
    annotated_alerts = annotate_alerts(alerts)
    store_alert_events(annotated_alerts)
    return JsonResponse(
        {
            "alerts": annotated_alerts,
            "alert_events": get_recent_alert_events(),
        }
    )


@csrf_exempt
@require_POST
def acknowledge_alert_api(request: HttpRequest):
    payload = json.loads(request.body or "{}")
    fingerprint = payload.get("fingerprint")
    if not fingerprint:
        return JsonResponse({"error": "fingerprint is required"}, status=400)
    acknowledged = acknowledge_alert_event(fingerprint)
    return JsonResponse({"ok": acknowledged})


@csrf_exempt
@require_POST
def session_heartbeat(request: HttpRequest):
    payload = json.loads(request.body or "{}")
    session_id = payload.get("sessionId")
    if not session_id:
        return JsonResponse({"error": "sessionId is required"}, status=400)
    return JsonResponse(touch_session(session_id))


@csrf_exempt
@require_POST
def session_close(request: HttpRequest):
    payload = json.loads(request.body or "{}")
    session_id = payload.get("sessionId")
    if not session_id:
        return JsonResponse({"error": "sessionId is required"}, status=400)
    return JsonResponse(close_session(session_id))


@csrf_exempt
@require_POST
def quit_app(request: HttpRequest):
    did_request = request_shutdown()
    return JsonResponse({"ok": did_request})
