import platform
import socket
from datetime import datetime, timezone
from pathlib import Path
from shutil import disk_usage

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None


def _safe_round(value: float) -> float:
    return round(value, 1)


def _format_boot_time(value: datetime) -> str:
    return value.astimezone().strftime("%Y-%m-%d %I:%M %p")


def collect_metrics() -> dict:
    cpu_percent = psutil.cpu_percent(interval=0.1) if psutil else 0.0
    virtual_memory = psutil.virtual_memory() if psutil else None
    disk_root = Path.cwd().anchor or str(Path.home().anchor) or "/"
    disk = disk_usage(disk_root)

    if psutil:
        net = psutil.net_io_counters()
        boot_time = datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc)
    else:
        net = None
        boot_time = datetime.now(tz=timezone.utc)

    memory_used_gb = 0.0
    memory_total_gb = 0.0
    memory_percent = 0.0
    if virtual_memory:
        memory_used_gb = _safe_round(
            (virtual_memory.total - virtual_memory.available) / (1024**3)
        )
        memory_total_gb = _safe_round(virtual_memory.total / (1024**3))
        memory_percent = _safe_round(virtual_memory.percent)

    return {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "cpu_percent": _safe_round(cpu_percent),
        "memory_percent": memory_percent,
        "memory_used_gb": memory_used_gb,
        "memory_total_gb": memory_total_gb,
        "disk_used_gb": _safe_round(disk.used / (1024**3)),
        "disk_total_gb": _safe_round(disk.total / (1024**3)),
        "disk_percent": _safe_round((disk.used / disk.total) * 100 if disk.total else 0),
        "bytes_sent_mb": _safe_round((net.bytes_sent / (1024**2)) if net else 0),
        "bytes_recv_mb": _safe_round((net.bytes_recv / (1024**2)) if net else 0),
        "boot_time": boot_time.isoformat(),
        "boot_time_display": _format_boot_time(boot_time),
    }


def collect_inventory() -> list[dict]:
    cpu_name = platform.processor() or "Unknown CPU"
    hostname = socket.gethostname()
    uname = platform.uname()
    architecture = platform.machine() or platform.architecture()[0]
    python_version = platform.python_version()
    inventory = [
        {"label": "Hostname", "value": hostname},
        {"label": "Operating system", "value": f"{uname.system} {uname.release}"},
        {"label": "Kernel / build", "value": uname.version},
        {"label": "Architecture", "value": architecture},
        {"label": "Processor", "value": cpu_name},
        {"label": "Python", "value": python_version},
    ]

    if psutil:
        inventory.extend(
            [
                {"label": "Physical cores", "value": str(psutil.cpu_count(logical=False) or 0)},
                {"label": "Logical cores", "value": str(psutil.cpu_count(logical=True) or 0)},
                {
                    "label": "Installed memory",
                    "value": f"{_safe_round(psutil.virtual_memory().total / (1024**3))} GB",
                },
            ]
        )

    return inventory
