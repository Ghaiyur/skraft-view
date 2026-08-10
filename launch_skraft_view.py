import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from dashboard.runtime_control import register_shutdown_callback

PROJECT_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
VENV_DIR = PROJECT_DIR / ".venv"
REQUIREMENTS_FILE = PROJECT_DIR / "requirements.txt"
NO_BROWSER = os.environ.get("SKRAFT_VIEW_NO_BROWSER") == "1"
BOOTSTRAPPED_FLAG = "SKRAFT_VIEW_BOOTSTRAPPED"
RUNNING_FROZEN = bool(getattr(sys, "frozen", False))
WINDOWS_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run_hidden(command: list[str], **kwargs):
    if os.name == "nt":
        kwargs.setdefault("creationflags", WINDOWS_NO_WINDOW)
    check = kwargs.pop("check", False)
    return subprocess.run(command, check=check, **kwargs)


def python_in_venv() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def running_inside_venv() -> bool:
    if RUNNING_FROZEN:
        return True

    current = Path(sys.executable).resolve()
    target = python_in_venv().resolve()
    return current == target


def ensure_virtualenv() -> None:
    if RUNNING_FROZEN:
        return

    if VENV_DIR.exists():
        return

    print("Creating local virtual environment...")
    run_hidden([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)


def ensure_dependencies() -> None:
    if RUNNING_FROZEN:
        return

    venv_python = python_in_venv()
    try:
        run_hidden(
            [str(venv_python), "-c", "import django, psutil"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        print("Installing project dependencies...")
        run_hidden(
            [str(venv_python), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)],
            check=True,
        )


def ensure_database() -> None:
    print("Applying database migrations...")
    if RUNNING_FROZEN:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "skraft_view.settings")
        import django
        from django.core.management import call_command

        django.setup()
        call_command("migrate", interactive=False, run_syncdb=True, verbosity=0)
        return

    python_executable = str(python_in_venv())
    run_hidden(
        [python_executable, "manage.py", "migrate", "--noinput"],
        cwd=PROJECT_DIR,
        check=True,
    )


def reserve_port() -> int:
    requested_port = os.environ.get("SKRAFT_VIEW_PORT")
    if requested_port:
        return int(requested_port)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def open_browser_when_ready(url: str) -> None:
    time.sleep(1.2)
    webbrowser.open(url)


def monitor_for_shutdown(httpd) -> None:
    # Auto-shutdown is intentionally disabled so the local server can recover
    # from temporary browser throttling or connection loss.
    while True:
        time.sleep(60)


def relaunch_inside_venv() -> None:
    if RUNNING_FROZEN:
        return

    if running_inside_venv():
        return

    if os.environ.get(BOOTSTRAPPED_FLAG) == "1":
        raise RuntimeError(
            "The launcher could not switch into the local virtual environment."
        )

    venv_python = python_in_venv()
    next_env = os.environ.copy()
    next_env[BOOTSTRAPPED_FLAG] = "1"
    result = run_hidden(
        [str(venv_python), str(PROJECT_DIR / "launch_skraft_view.py")],
        cwd=PROJECT_DIR,
        env=next_env,
        check=False,
    )
    raise SystemExit(result.returncode)


def run_server() -> None:
    ensure_virtualenv()
    ensure_dependencies()
    relaunch_inside_venv()
    ensure_database()

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "skraft_view.settings")
    sys.path.insert(0, str(PROJECT_DIR))

    from wsgiref.simple_server import make_server

    import django
    from django.contrib.staticfiles.handlers import StaticFilesHandler
    from django.core.wsgi import get_wsgi_application

    django.setup()

    port = reserve_port()
    url = f"http://127.0.0.1:{port}/monitor/"

    print(f"Starting skraft view at {url}")
    print("Close this window to stop the local app.")

    if not NO_BROWSER:
        threading.Thread(
            target=open_browser_when_ready, args=(url,), daemon=True
        ).start()

    app = StaticFilesHandler(get_wsgi_application())
    with make_server("127.0.0.1", port, app) as httpd:
        register_shutdown_callback(httpd.shutdown)
        httpd.serve_forever()


if __name__ == "__main__":
    try:
        run_server()
    except KeyboardInterrupt:
        print("\nskraft view stopped.")
    except Exception as exc:  # pragma: no cover
        print(f"\nUnable to launch skraft view: {exc}")
        if os.name == "nt" and sys.stdin.isatty():
            input("Press Enter to close...")
        raise
