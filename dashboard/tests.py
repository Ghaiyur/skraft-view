import json

from django.test import TestCase
from django.urls import reverse

from .models import AlertEvent, MetricSample


class DashboardTests(TestCase):
    def test_home_page_loads(self) -> None:
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lightweight Real-Time PC Health")
        self.assertGreater(MetricSample.objects.count(), 0)

    def test_root_redirects_to_monitor(self) -> None:
        response = self.client.get("/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("dashboard:home"))

    def test_metrics_api_returns_nested_sections(self) -> None:
        response = self.client.get(reverse("dashboard:metrics-api"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("cpu", payload)
        self.assertIn("gpu", payload)
        self.assertIn("memory", payload)
        self.assertIn("storage", payload)
        self.assertIn("network", payload)
        self.assertIn("system", payload)
        self.assertIn("power", payload)
        self.assertIn("fans", payload)
        self.assertIn("drive_health", payload)
        self.assertIn("efficiency_score", payload)
        self.assertIn("cpu_percent", payload)
        self.assertIn("memory_percent", payload)
        self.assertIn("temperature_c", payload["cpu"])
        self.assertIn("speed_mhz", payload["memory"])
        self.assertIn("drives", payload["storage"])
        self.assertIn("io", payload)
        self.assertIn("processes", payload)
        self.assertIn("upload_rate_mb_s", payload["network"])
        self.assertIn("read_rate_mb_s", payload["io"])
        self.assertIn("top_cpu", payload["processes"])
        self.assertIn("top_memory", payload["processes"])
        self.assertIn("alerts", payload)
        self.assertIn("uptime_display", payload["system"])
        self.assertIn("motherboard_manufacturer", payload["system"])
        self.assertIn("bios_version", payload["system"])
        self.assertIn("adapters", payload["gpu"])
        self.assertIn("gpu_model", payload)

    def test_history_api_returns_samples(self) -> None:
        self.client.get(reverse("dashboard:home"))
        response = self.client.get(reverse("dashboard:history-api"), {"range": "1h"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["range"], "1h")
        self.assertIn("samples", payload)
        self.assertIn("alert_events", payload)
        self.assertGreaterEqual(len(payload["samples"]), 1)

    def test_alerts_api_returns_alerts(self) -> None:
        response = self.client.get(reverse("dashboard:alerts-api"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("alerts", payload)
        self.assertIn("alert_events", payload)

    def test_acknowledge_alert_api_marks_alert_acknowledged(self) -> None:
        AlertEvent.objects.create(
            fingerprint="warning:Test alert",
            severity="warning",
            title="Test alert",
            message="Test message",
            active=True,
        )

        response = self.client.post(
            reverse("dashboard:acknowledge-alert-api"),
            data=json.dumps({"fingerprint": "warning:Test alert"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])

        event = AlertEvent.objects.get(fingerprint="warning:Test alert")
        self.assertTrue(event.acknowledged)
        self.assertIsNotNone(event.acknowledged_at)
