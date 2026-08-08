import json

from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .runtime_control import request_shutdown
from .session_state import close_session, touch_session
from .system import collect_inventory, collect_metrics


def home(request: HttpRequest):
    context = {
        "metrics": collect_metrics(),
        "inventory": collect_inventory(),
    }
    return render(request, "dashboard/home.html", context)


def metrics_api(request: HttpRequest):
    return JsonResponse(collect_metrics())


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
