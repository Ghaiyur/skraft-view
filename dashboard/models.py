from django.db import models


class MetricSample(models.Model):
    captured_at = models.DateTimeField(auto_now_add=True, db_index=True)
    payload = models.JSONField()

    class Meta:
        ordering = ("-captured_at",)

    def __str__(self) -> str:
        return f"MetricSample {self.captured_at:%Y-%m-%d %H:%M:%S}"


class AlertEvent(models.Model):
    fingerprint = models.CharField(max_length=255, unique=True)
    severity = models.CharField(max_length=32)
    title = models.CharField(max_length=255)
    message = models.TextField()
    occurrences = models.PositiveIntegerField(default=1)
    active = models.BooleanField(default=True, db_index=True)
    acknowledged = models.BooleanField(default=False, db_index=True)
    acknowledged_at = models.DateTimeField(blank=True, null=True)
    first_seen = models.DateTimeField(auto_now_add=True, db_index=True)
    last_seen = models.DateTimeField(auto_now=True, db_index=True)
    resolved_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-last_seen",)

    def __str__(self) -> str:
        return f"{self.severity}: {self.title}"
