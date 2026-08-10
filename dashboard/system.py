import csv
import json
import os
import platform
import socket
import subprocess
import threading
import time
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
from shutil import disk_usage

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None


_SAMPLE_LOCK = threading.Lock()
_LAST_NETWORK_SAMPLE = None
_LAST_IO_SAMPLE = None
_PROCESS_SAMPLES = {}
_WINDOWS_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _run_subprocess(command: list[str], **kwargs):
    if os.name == "nt":
        kwargs.setdefault("creationflags", _WINDOWS_NO_WINDOW)
    check = kwargs.pop("check", False)
    return subprocess.run(command, check=check, **kwargs)


def _safe_round(value: float) -> float:
    return round(value, 1)


def _format_boot_time(value: datetime) -> str:
    local_value = value.astimezone()
    return local_value.strftime("%Y-%m-%d %I:%M %p %Z")


def _format_uptime(value: timedelta) -> str:
    total_seconds = int(value.total_seconds())
    days, remainder = divmod(total_seconds, 24 * 60 * 60)
    hours, remainder = divmod(remainder, 60 * 60)
    minutes, _ = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def _round_gb(value: float) -> float:
    return _safe_round(value / (1024**3))


def _safe_disk_usage(path: str):
    try:
        return disk_usage(path)
    except (FileNotFoundError, OSError):
        return None


def _choose_active_interface() -> str | None:
    if not psutil:
        return None

    stats = psutil.net_if_stats()
    for name, stat in stats.items():
        if stat.isup:
            return name

    return next(iter(stats), None)


def _collect_cpu_temperature() -> tuple[float | None, str | None]:
    if not psutil or not hasattr(psutil, "sensors_temperatures"):
        return None, None

    sensors = psutil.sensors_temperatures(fahrenheit=False) or {}
    preferred_keys = ("coretemp", "k10temp", "cpu_thermal", "acpitz")

    for key in preferred_keys:
        entries = sensors.get(key) or []
        for entry in entries:
            if entry.current is not None:
                return _safe_round(entry.current), entry.label or key

    for key, entries in sensors.items():
        for entry in entries:
            if entry.current is not None:
                return _safe_round(entry.current), entry.label or key

    return None, None


def _collect_memory_speed_mhz() -> float | None:
    if os.name != "nt":
        return None

    try:
        result = _run_subprocess(
            ["wmic", "memorychip", "get", "speed"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None

    speeds = []
    for line in result.stdout.splitlines():
        value = line.strip()
        if value.isdigit():
            speeds.append(int(value))

    if not speeds:
        return None

    return _safe_round(sum(speeds) / len(speeds))


def _parse_csv_output(output: str) -> list[dict[str, str]]:
    reader = csv.DictReader(StringIO(output))
    return [
        {
            str(key).strip().lower(): (
                str(value).strip() if value is not None else ""
            )
            for key, value in row.items()
        }
        for row in reader
        if any(str(value).strip() for value in row.values() if value is not None)
    ]


def _collect_windows_hardware_info() -> dict[str, str | None]:
    if os.name != "nt":
        return {
            "motherboard_manufacturer": None,
            "motherboard_model": None,
            "motherboard_serial": None,
            "bios_version": None,
        }

    def _run_wmic(command: list[str]) -> str:
        try:
            result = _run_subprocess(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            return ""
        return result.stdout

    board_output = _run_wmic(
        [
            "wmic",
            "baseboard",
            "get",
            "Manufacturer,Product,SerialNumber",
            "/format:list",
        ]
    )
    bios_output = _run_wmic(
        ["wmic", "bios", "get", "SMBIOSBIOSVersion,Version", "/format:list"]
    )

    def _parse_list(output: str) -> dict[str, str]:
        values = {}
        for line in output.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip().lower()] = value.strip()
        return values

    board_values = _parse_list(board_output)
    bios_values = _parse_list(bios_output)
    bios_version = bios_values.get("smbiosbiosversion") or bios_values.get("version")

    return {
        "motherboard_manufacturer": board_values.get("manufacturer") or None,
        "motherboard_model": board_values.get("product") or None,
        "motherboard_serial": board_values.get("serialnumber") or None,
        "bios_version": bios_version or None,
    }


def _collect_fan_speeds() -> list[dict[str, str | float | None]]:
    if not psutil or not hasattr(psutil, "sensors_fans"):
        return []

    try:
        sensors = psutil.sensors_fans() or {}
    except (OSError, AttributeError):
        return []

    fans = []
    for name, entries in sensors.items():
        for entry in entries:
            fans.append(
                {
                    "label": entry.label or name,
                    "speed_rpm": _safe_round(entry.current)
                    if entry.current is not None
                    else None,
                }
            )
    return fans


def _collect_windows_drive_health() -> list[dict[str, str | float | None]]:
    if os.name != "nt":
        return []

    commands = [
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "Get-PhysicalDisk | "
                "Select-Object FriendlyName, MediaType, HealthStatus, OperationalStatus, Size | "
                "ConvertTo-Json -Depth 2"
            ),
        ],
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "Get-PhysicalDisk | ForEach-Object { "
                "  $counter = Get-StorageReliabilityCounter -PhysicalDisk $_ -ErrorAction SilentlyContinue; "
                "  [PSCustomObject]@{ "
                "    FriendlyName = $_.FriendlyName; "
                "    MediaType = $_.MediaType; "
                "    HealthStatus = $_.HealthStatus; "
                "    TemperatureC = $counter.Temperature; "
                "    Wear = $counter.Wear; "
                "  } "
                "} | ConvertTo-Json -Depth 2"
            ),
        ],
    ]

    for command in commands:
        try:
            result = _run_subprocess(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            continue

        if result.returncode != 0 or not result.stdout.strip():
            continue

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            continue

        if isinstance(data, dict):
            data = [data]

        drives = []
        for item in data or []:
            if not isinstance(item, dict):
                continue
            drives.append(
                {
                    "label": item.get("FriendlyName") or "Drive",
                    "media_type": item.get("MediaType") or None,
                    "health_status": item.get("HealthStatus") or None,
                    "operational_status": item.get("OperationalStatus") or None,
                    "temperature_c": _safe_round(float(item["TemperatureC"]))
                    if item.get("TemperatureC") not in (None, "")
                    and str(item.get("TemperatureC")).replace(".", "", 1).isdigit()
                    else None,
                    "wear_percent": _safe_round(float(item["Wear"]))
                    if item.get("Wear") not in (None, "")
                    and str(item.get("Wear")).replace(".", "", 1).isdigit()
                    else None,
                }
            )

        if drives:
            return drives

    return []


def _collect_power_metrics(cpu: dict, gpu: dict) -> dict:
    cpu_power_w = None
    system_power_w = None

    if cpu.get("utilization_percent") is not None:
        cpu_power_w = _safe_round(max(cpu["utilization_percent"], 0) * 1.2)

    if gpu.get("power_w") is not None:
        system_power_w = _safe_round(gpu["power_w"] + (cpu_power_w or 0))
    elif cpu_power_w is not None:
        system_power_w = cpu_power_w

    return {
        "cpu_power_w": cpu_power_w,
        "system_power_w": system_power_w,
    }


def _collect_efficiency_score(
    cpu: dict, memory: dict, storage: dict, gpu: dict
) -> float | None:
    values = []
    for value in (
        cpu.get("utilization_percent"),
        memory.get("utilization_percent"),
        storage.get("utilization_percent"),
        gpu.get("utilization_percent"),
    ):
        if value is not None:
            values.append(float(value))

    if not values:
        return None

    load_penalty = sum(values) / len(values)
    temperature_penalty = 0.0
    for value in (cpu.get("temperature_c"), gpu.get("temperature_c")):
        if value is not None:
            temperature_penalty += max(float(value) - 40.0, 0.0) / 2

    score = 100.0 - load_penalty - temperature_penalty
    return _safe_round(max(min(score, 100.0), 0.0))


def _collect_nvidia_gpu_adapters() -> list[dict[str, str | float | None]]:
    query = (
        "name,memory.total,memory.used,utilization.gpu,temperature.gpu,"
        "power.draw,clocks.sm"
    )
    try:
        result = _run_subprocess(
            [
                "nvidia-smi",
                f"--query-gpu={query}",
                "--format=csv,noheader,nounits",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return []

    if result.returncode != 0 or not result.stdout.strip():
        return []

    adapters = []
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 7:
            continue
        (
            model,
            memory_total,
            memory_used,
            utilization,
            temperature,
            power_draw,
            clock,
        ) = parts[:7]
        adapters.append(
            {
                "model": model or "Unknown GPU",
                "vram_total_gb": _safe_round(float(memory_total) / 1024)
                if memory_total.replace(".", "", 1).isdigit()
                else None,
                "vram_used_gb": _safe_round(float(memory_used) / 1024)
                if memory_used.replace(".", "", 1).isdigit()
                else None,
                "utilization_percent": _safe_round(float(utilization))
                if utilization.replace(".", "", 1).isdigit()
                else None,
                "temperature_c": _safe_round(float(temperature))
                if temperature.replace(".", "", 1).isdigit()
                else None,
                "power_w": _safe_round(float(power_draw))
                if power_draw.replace(".", "", 1).isdigit()
                else None,
                "clock_mhz": _safe_round(float(clock))
                if clock.replace(".", "", 1).isdigit()
                else None,
            }
        )

    return adapters


def _collect_windows_gpu_adapters() -> list[dict[str, str | float | None]]:
    if os.name != "nt":
        return []

    try:
        result = _run_subprocess(
            [
                "wmic",
                "path",
                "win32_VideoController",
                "get",
                "Name,AdapterRAM",
                "/format:csv",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return []

    if result.returncode != 0 or not result.stdout.strip():
        return []

    adapters = []
    for row in _parse_csv_output(result.stdout):
        adapter_ram = row.get("adapterram") or ""
        vram_total_gb = None
        if adapter_ram.isdigit():
            vram_total_gb = _safe_round(int(adapter_ram) / (1024**3))
        adapters.append(
            {
                "model": row.get("name") or "Unknown GPU",
                "vram_total_gb": vram_total_gb,
                "vram_used_gb": None,
                "utilization_percent": None,
                "temperature_c": None,
                "power_w": None,
                "clock_mhz": None,
            }
        )

    return adapters


def _collect_gpu_metrics() -> dict:
    adapters = _collect_nvidia_gpu_adapters()
    if not adapters:
        adapters = _collect_windows_gpu_adapters()

    primary = adapters[0] if adapters else {}
    return {
        "model": primary.get("model") if primary else None,
        "vram_total_gb": primary.get("vram_total_gb") if primary else None,
        "vram_used_gb": primary.get("vram_used_gb") if primary else None,
        "utilization_percent": primary.get("utilization_percent") if primary else None,
        "temperature_c": primary.get("temperature_c") if primary else None,
        "power_w": primary.get("power_w") if primary else None,
        "clock_mhz": primary.get("clock_mhz") if primary else None,
        "adapters": adapters,
    }


def _collect_cpu_metrics() -> dict:
    cpu_percent = psutil.cpu_percent(interval=0.1) if psutil else 0.0
    cpu_freq = psutil.cpu_freq() if psutil else None
    cpu_temperature_c, cpu_temperature_source = _collect_cpu_temperature()
    return {
        "model": platform.processor() or "Unknown CPU",
        "physical_cores": psutil.cpu_count(logical=False) if psutil else 0,
        "logical_cores": psutil.cpu_count(logical=True) if psutil else 0,
        "utilization_percent": _safe_round(cpu_percent),
        "frequency_mhz": _safe_round(cpu_freq.current) if cpu_freq else 0.0,
        "temperature_c": cpu_temperature_c,
        "temperature_source": cpu_temperature_source,
    }


def _collect_memory_metrics() -> dict:
    if not psutil:
        return {
            "total_gb": 0.0,
            "used_gb": 0.0,
            "available_gb": 0.0,
            "utilization_percent": 0.0,
            "speed_mhz": None,
        }

    virtual_memory = psutil.virtual_memory()
    return {
        "total_gb": _round_gb(virtual_memory.total),
        "used_gb": _round_gb(virtual_memory.total - virtual_memory.available),
        "available_gb": _round_gb(virtual_memory.available),
        "utilization_percent": _safe_round(virtual_memory.percent),
        "speed_mhz": _collect_memory_speed_mhz(),
    }


def _collect_storage_metrics() -> dict:
    disk_root = Path.cwd().anchor or str(Path.home().anchor) or "/"
    disk = _safe_disk_usage(disk_root)
    drives = []

    if psutil:
        seen_mountpoints = set()
        for partition in psutil.disk_partitions(all=False):
            if partition.mountpoint in seen_mountpoints:
                continue
            seen_mountpoints.add(partition.mountpoint)
            usage = _safe_disk_usage(partition.mountpoint)
            if usage is None:
                continue
            drives.append(
                {
                    "device": partition.device,
                    "mount": partition.mountpoint,
                    "filesystem": partition.fstype or "Unknown",
                    "total_gb": _round_gb(usage.total),
                    "used_gb": _round_gb(usage.used),
                    "free_gb": _round_gb(usage.free),
                    "utilization_percent": _safe_round(
                        (usage.used / usage.total) * 100 if usage.total else 0
                    ),
                }
            )

    if disk is None:
        disk = _safe_disk_usage("/")

    return {
        "mount": disk_root,
        "total_gb": _round_gb(disk.total) if disk else 0.0,
        "used_gb": _round_gb(disk.used) if disk else 0.0,
        "free_gb": _round_gb(disk.free) if disk else 0.0,
        "utilization_percent": _safe_round(
            (disk.used / disk.total) * 100 if disk and disk.total else 0
        ),
        "drives": drives,
    }


def _collect_network_metrics() -> dict:
    if not psutil:
        return {
            "interface": None,
            "speed_mbps": None,
            "bytes_sent_mb": 0.0,
            "bytes_recv_mb": 0.0,
            "upload_rate_mb_s": 0.0,
            "download_rate_mb_s": 0.0,
            "utilization_percent": None,
        }

    interface = _choose_active_interface()
    net = psutil.net_io_counters()
    speed_mbps = None
    if interface:
        interface_stats = psutil.net_if_stats().get(interface)
        if interface_stats:
            speed_mbps = interface_stats.speed or None

    current_time = time.monotonic()
    with _SAMPLE_LOCK:
        global _LAST_NETWORK_SAMPLE
        previous = _LAST_NETWORK_SAMPLE

    upload_rate_mb_s = 0.0
    download_rate_mb_s = 0.0
    utilization_percent = None
    if previous:
        elapsed = current_time - previous["time"]
        if elapsed > 0:
            upload_rate_mb_s = _safe_round(
                (net.bytes_sent - previous["network"].bytes_sent) / (1024**2) / elapsed
            )
            download_rate_mb_s = _safe_round(
                (net.bytes_recv - previous["network"].bytes_recv) / (1024**2) / elapsed
            )
            if speed_mbps:
                max_bytes_per_sec = (speed_mbps * 1_000_000) / 8
                total_bytes_per_sec = (
                    (net.bytes_sent - previous["network"].bytes_sent)
                    + (net.bytes_recv - previous["network"].bytes_recv)
                ) / elapsed
                utilization_percent = _safe_round(
                    (total_bytes_per_sec / max_bytes_per_sec) * 100
                )

    with _SAMPLE_LOCK:
        _LAST_NETWORK_SAMPLE = {"time": current_time, "network": net}

    return {
        "interface": interface,
        "speed_mbps": speed_mbps,
        "bytes_sent_mb": _safe_round((net.bytes_sent / (1024**2)) if net else 0),
        "bytes_recv_mb": _safe_round((net.bytes_recv / (1024**2)) if net else 0),
        "upload_rate_mb_s": upload_rate_mb_s,
        "download_rate_mb_s": download_rate_mb_s,
        "utilization_percent": utilization_percent,
    }


def _collect_io_metrics() -> dict:
    if not psutil:
        return {
            "read_bytes_mb": 0.0,
            "write_bytes_mb": 0.0,
            "read_rate_mb_s": 0.0,
            "write_rate_mb_s": 0.0,
            "read_iops": 0.0,
            "write_iops": 0.0,
        }

    io = psutil.disk_io_counters()
    current_time = time.monotonic()
    with _SAMPLE_LOCK:
        global _LAST_IO_SAMPLE
        previous = _LAST_IO_SAMPLE

    read_rate_mb_s = 0.0
    write_rate_mb_s = 0.0
    read_iops = 0.0
    write_iops = 0.0
    if previous:
        elapsed = current_time - previous["time"]
        if elapsed > 0:
            read_rate_mb_s = _safe_round(
                (io.read_bytes - previous["disk_io"].read_bytes) / (1024**2) / elapsed
            )
            write_rate_mb_s = _safe_round(
                (io.write_bytes - previous["disk_io"].write_bytes) / (1024**2) / elapsed
            )
            read_iops = _safe_round(
                (io.read_count - previous["disk_io"].read_count) / elapsed
            )
            write_iops = _safe_round(
                (io.write_count - previous["disk_io"].write_count) / elapsed
            )

    with _SAMPLE_LOCK:
        _LAST_IO_SAMPLE = {"time": current_time, "disk_io": io}

    return {
        "read_bytes_mb": _safe_round(io.read_bytes / (1024**2)),
        "write_bytes_mb": _safe_round(io.write_bytes / (1024**2)),
        "read_rate_mb_s": read_rate_mb_s,
        "write_rate_mb_s": write_rate_mb_s,
        "read_iops": read_iops,
        "write_iops": write_iops,
    }


def _collect_process_metrics() -> dict:
    if not psutil:
        return {"top_cpu": [], "top_memory": []}

    now = time.monotonic()
    cpu_count = psutil.cpu_count(logical=True) or 1
    current_samples = {}
    processes = []

    for proc in psutil.process_iter(
        ["pid", "name", "username", "memory_info", "status", "create_time"]
    ):
        try:
            with proc.oneshot():
                cpu_times = proc.cpu_times()
                total_cpu_time = (cpu_times.user or 0.0) + (cpu_times.system or 0.0)
                memory_info = proc.memory_info()
                rss_mb = _safe_round(memory_info.rss / (1024**2))

                previous = _PROCESS_SAMPLES.get(proc.pid)
                cpu_percent = 0.0
                if previous:
                    elapsed = now - previous["time"]
                    if elapsed > 0:
                        cpu_percent = _safe_round(
                            ((total_cpu_time - previous["cpu_time"]) / elapsed)
                            * 100
                            / cpu_count
                        )

                processes.append(
                    {
                        "pid": proc.pid,
                        "name": proc.info.get("name") or "Unknown",
                        "cpu_percent": max(cpu_percent, 0.0),
                        "memory_mb": rss_mb,
                        "username": proc.info.get("username") or "Unknown",
                        "status": proc.info.get("status") or "unknown",
                    }
                )
                current_samples[proc.pid] = {"time": now, "cpu_time": total_cpu_time}
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    with _SAMPLE_LOCK:
        _PROCESS_SAMPLES.clear()
        _PROCESS_SAMPLES.update(current_samples)

    top_cpu = sorted(processes, key=lambda item: item["cpu_percent"], reverse=True)[:5]
    top_memory = sorted(processes, key=lambda item: item["memory_mb"], reverse=True)[:5]
    return {"top_cpu": top_cpu, "top_memory": top_memory}


def _collect_system_metrics() -> dict:
    if psutil:
        boot_time = datetime.fromtimestamp(psutil.boot_time(), tz=UTC)
    else:
        boot_time = datetime.now(tz=UTC)

    uname = platform.uname()
    uptime = datetime.now(tz=UTC) - boot_time
    hardware = _collect_windows_hardware_info()
    return {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "hostname": socket.gethostname(),
        "os": f"{uname.system} {uname.release}",
        "kernel": uname.version,
        "architecture": platform.machine() or platform.architecture()[0],
        "python_version": platform.python_version(),
        "boot_time": boot_time.isoformat(),
        "boot_time_display": _format_boot_time(boot_time),
        "uptime_seconds": int(uptime.total_seconds()),
        "uptime_display": _format_uptime(uptime),
        **hardware,
    }


def collect_metrics() -> dict:
    cpu = _collect_cpu_metrics()
    gpu = _collect_gpu_metrics()
    memory = _collect_memory_metrics()
    storage = _collect_storage_metrics()
    network = _collect_network_metrics()
    io = _collect_io_metrics()
    processes = _collect_process_metrics()
    system = _collect_system_metrics()
    fans = _collect_fan_speeds()
    drive_health = _collect_windows_drive_health()
    power = _collect_power_metrics(cpu, gpu)
    efficiency_score = _collect_efficiency_score(cpu, memory, storage, gpu)
    return {
        "timestamp": system["timestamp"],
        "cpu": cpu,
        "gpu": gpu,
        "memory": memory,
        "storage": storage,
        "network": network,
        "io": io,
        "processes": processes,
        "system": system,
        "fans": fans,
        "drive_health": drive_health,
        "power": power,
        "efficiency_score": efficiency_score,
        "cpu_percent": cpu["utilization_percent"],
        "gpu_model": gpu["model"],
        "gpu_vram_total_gb": gpu["vram_total_gb"],
        "gpu_vram_used_gb": gpu["vram_used_gb"],
        "gpu_utilization_percent": gpu["utilization_percent"],
        "gpu_temperature_c": gpu["temperature_c"],
        "gpu_power_w": gpu["power_w"],
        "gpu_clock_mhz": gpu["clock_mhz"],
        "memory_percent": memory["utilization_percent"],
        "memory_used_gb": memory["used_gb"],
        "memory_total_gb": memory["total_gb"],
        "disk_used_gb": storage["used_gb"],
        "disk_total_gb": storage["total_gb"],
        "disk_percent": storage["utilization_percent"],
        "bytes_sent_mb": network["bytes_sent_mb"],
        "bytes_recv_mb": network["bytes_recv_mb"],
        "read_bytes_mb": io["read_bytes_mb"],
        "write_bytes_mb": io["write_bytes_mb"],
        "process_top_cpu": processes["top_cpu"],
        "process_top_memory": processes["top_memory"],
        "boot_time": system["boot_time"],
        "boot_time_display": system["boot_time_display"],
        "uptime_seconds": system["uptime_seconds"],
        "uptime_display": system["uptime_display"],
    }


def collect_inventory() -> list[dict]:
    cpu_name = platform.processor() or "Unknown CPU"
    hostname = socket.gethostname()
    uname = platform.uname()
    architecture = platform.machine() or platform.architecture()[0]
    python_version = platform.python_version()
    hardware = _collect_windows_hardware_info()
    inventory = [
        {"label": "Hostname", "value": hostname},
        {"label": "Operating system", "value": f"{uname.system} {uname.release}"},
        {"label": "Kernel / build", "value": uname.version},
        {"label": "Architecture", "value": architecture},
        {"label": "Processor", "value": cpu_name},
        {"label": "Python", "value": python_version},
        {
            "label": "Motherboard",
            "value": " / ".join(
                item
                for item in [
                    hardware["motherboard_manufacturer"],
                    hardware["motherboard_model"],
                ]
                if item
            )
            or "Unknown",
        },
        {
            "label": "BIOS",
            "value": hardware["bios_version"] or "Unknown",
        },
    ]

    if psutil:
        inventory.extend(
            [
                {
                    "label": "Physical cores",
                    "value": str(psutil.cpu_count(logical=False) or 0),
                },
                {
                    "label": "Logical cores",
                    "value": str(psutil.cpu_count(logical=True) or 0),
                },
                {
                    "label": "Installed memory",
                    "value": f"{_safe_round(psutil.virtual_memory().total / (1024**3))} GB",
                },
            ]
        )

    return inventory
