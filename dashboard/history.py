from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import AlertEvent, MetricSample

HISTORY_SAMPLE_LIMIT = 120
HISTORY_RANGE_MAP = {
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "24h": timedelta(days=1),
    "7d": timedelta(days=7),
}
HISTORY_LIMIT_MAP = {
    "15m": 30,
    "1h": 60,
    "24h": 120,
    "7d": 240,
}
MIN_SAMPLE_INTERVAL = timedelta(seconds=60)


def _metric(value: dict, *path: str):
    current = value
    for segment in path:
        if not isinstance(current, dict):
            return None
        current = current.get(segment)
    return current


def store_metric_sample(metrics: dict) -> None:
    now = timezone.now()
    latest_captured_at = (
        MetricSample.objects.order_by("-captured_at").values_list(
            "captured_at", flat=True
        ).first()
    )
    if latest_captured_at and now - latest_captured_at < MIN_SAMPLE_INTERVAL:
        return
    MetricSample.objects.create(payload=metrics)
    _prune_old_samples()


def _prune_old_samples() -> None:
    sample_ids = list(
        MetricSample.objects.order_by("-captured_at").values_list("id", flat=True)[
            HISTORY_SAMPLE_LIMIT:
        ]
    )
    if not sample_ids:
        return
    MetricSample.objects.filter(id__in=sample_ids).delete()


def get_recent_samples(limit: int = 24, range_key: str = "24h") -> list[dict]:
    samples = MetricSample.objects.order_by("-captured_at")
    window = HISTORY_RANGE_MAP.get(range_key)
    if window is not None:
        samples = samples.filter(captured_at__gte=timezone.now() - window)
    samples = samples[:limit]
    return [
        {
            "captured_at": sample.captured_at,
            "cpu_percent": _metric(sample.payload, "cpu", "utilization_percent"),
            "memory_percent": _metric(sample.payload, "memory", "utilization_percent"),
            "storage_percent": _metric(
                sample.payload, "storage", "utilization_percent"
            ),
            "temperature_c": _metric(sample.payload, "cpu", "temperature_c"),
            "upload_rate_mb_s": _metric(sample.payload, "network", "upload_rate_mb_s"),
            "download_rate_mb_s": _metric(
                sample.payload, "network", "download_rate_mb_s"
            ),
        }
        for sample in reversed(samples)
    ]


def get_recent_alert_events(limit: int = 24) -> list[dict]:
    events = AlertEvent.objects.order_by("-last_seen")[:limit]
    return [
        {
            "fingerprint": event.fingerprint,
            "severity": event.severity,
            "title": event.title,
            "message": event.message,
            "occurrences": event.occurrences,
            "active": event.active,
            "acknowledged": event.acknowledged,
            "acknowledged_at": event.acknowledged_at,
            "first_seen": event.first_seen,
            "last_seen": event.last_seen,
            "resolved_at": event.resolved_at,
        }
        for event in events
    ]


def _alert_fingerprint(alert: dict) -> str:
    severity = alert.get("severity") or "info"
    title = alert.get("title") or "Alert"
    return f"{severity}:{title}"


def store_alert_events(alerts: list[dict]) -> None:
    now = timezone.now()
    fingerprints = set()

    with transaction.atomic():
        for alert in alerts:
            fingerprint = _alert_fingerprint(alert)
            fingerprints.add(fingerprint)
            event, created = AlertEvent.objects.get_or_create(
                fingerprint=fingerprint,
                defaults={
                    "severity": alert.get("severity") or "info",
                    "title": alert.get("title") or "Alert",
                    "message": alert.get("message") or "",
                    "occurrences": 1,
                    "active": True,
                },
            )
            if created:
                continue

            is_reactivated = not event.active and event.resolved_at is not None
            AlertEvent.objects.filter(pk=event.pk).update(
                severity=alert.get("severity") or event.severity,
                title=alert.get("title") or event.title,
                message=alert.get("message") or event.message,
                occurrences=event.occurrences + 1,
                active=True,
                last_seen=now,
                resolved_at=None,
                acknowledged=False if is_reactivated else event.acknowledged,
                acknowledged_at=None if is_reactivated else event.acknowledged_at,
            )

        AlertEvent.objects.filter(active=True).exclude(
            fingerprint__in=fingerprints
        ).update(
            active=False,
            resolved_at=now,
        )


def acknowledge_alert_event(fingerprint: str) -> bool:
    updated = (
        AlertEvent.objects.filter(fingerprint=fingerprint, active=True)
        .exclude(acknowledged=True)
        .update(acknowledged=True, acknowledged_at=timezone.now())
    )
    return bool(updated)


def build_alert_fingerprint(alert: dict) -> str:
    return _alert_fingerprint(alert)


def annotate_alerts(alerts: list[dict]) -> list[dict]:
    fingerprints = [build_alert_fingerprint(alert) for alert in alerts]
    events_by_fingerprint = {
        event.fingerprint: event
        for event in AlertEvent.objects.filter(fingerprint__in=fingerprints)
    }

    annotated = []
    for alert, fingerprint in zip(alerts, fingerprints):
        event = events_by_fingerprint.get(fingerprint)
        annotated.append(
            {
                **alert,
                "fingerprint": fingerprint,
                "acknowledged": bool(event.acknowledged) if event else False,
                "active": bool(event.active) if event else True,
                "occurrences": event.occurrences if event else 1,
                "first_seen": event.first_seen if event else None,
                "last_seen": event.last_seen if event else None,
                "resolved_at": event.resolved_at if event else None,
            }
        )

    return annotated


def build_alerts(metrics: dict) -> list[dict]:
    alerts = []

    cpu_percent = _metric(metrics, "cpu", "utilization_percent") or 0
    memory_percent = _metric(metrics, "memory", "utilization_percent") or 0
    storage_percent = _metric(metrics, "storage", "utilization_percent") or 0
    storage_free = _metric(metrics, "storage", "free_gb")
    cpu_temp = _metric(metrics, "cpu", "temperature_c")
    network_utilization = _metric(metrics, "network", "utilization_percent")

    if cpu_percent >= 85:
        alerts.append(
            {
                "severity": "warning",
                "title": "High CPU utilisation",
                "message": f"CPU is at {cpu_percent}%.",
            }
        )

    if memory_percent >= 90:
        alerts.append(
            {
                "severity": "warning",
                "title": "High memory usage",
                "message": f"Memory is at {memory_percent}%.",
            }
        )

    if storage_percent >= 90 or (storage_free is not None and storage_free <= 10):
        alerts.append(
            {
                "severity": "warning",
                "title": "Low storage",
                "message": "Storage space is getting tight.",
            }
        )

    if cpu_temp is not None and cpu_temp >= 80:
        alerts.append(
            {
                "severity": "critical",
                "title": "High CPU temperature",
                "message": f"CPU temperature is {cpu_temp}\u00b0C.",
            }
        )

    if network_utilization is not None and network_utilization >= 85:
        alerts.append(
            {
                "severity": "warning",
                "title": "High network usage",
                "message": f"Network link is at {network_utilization}%.",
            }
        )

    return alerts


def history_payload(limit: int = 24, range_key: str = "24h") -> dict:
    effective_range = range_key if range_key in HISTORY_RANGE_MAP else "24h"
    sample_limit = HISTORY_LIMIT_MAP.get(effective_range, limit)
    return {
        "range": effective_range,
        "samples": get_recent_samples(limit=sample_limit, range_key=effective_range),
        "alert_events": get_recent_alert_events(limit=limit),
    }
