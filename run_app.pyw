"""
eCommunicator / EASD Meeting Minutes - the one launcher for every platform.

  Windows : double-click run_app.pyw (.pyw opens with pythonw, so no console window)
  Linux   : python3 run_app.pyw          macOS: python3 run_app.pyw
  Options : console     keep the terminal open and show the log (troubleshooting)
            shortcut    create a desktop shortcut for this computer, then exit

It always re-starts itself inside the project's own .venv (or venv) when one exists,
then starts the local server and opens the app window (or focuses it if already running).
"""
import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WINDOWS = os.name == "nt"
ARGS = [a.lower().lstrip("-") for a in sys.argv[1:]]


def _venv_python() -> str:
    """The project's virtual-env interpreter (pythonw on Windows unless 'console'), or ''."""
    for venv in (".venv", "venv"):
        if WINDOWS:
            names = ["python.exe"] if "console" in ARGS else ["pythonw.exe", "python.exe"]
            candidates = [os.path.join(BASE_DIR, venv, "Scripts", n) for n in names]
        else:
            candidates = [os.path.join(BASE_DIR, venv, "bin", "python")]
        for c in candidates:
            if os.path.isfile(c):
                return c
    return ""


def _create_shortcut(python: str) -> None:
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    launcher = os.path.abspath(__file__)
    icon = os.path.join(BASE_DIR, "static", "favicon.ico" if WINDOWS else "favicon.png")
    if WINDOWS:
        ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{desktop}\\eCommunicator.lnk');"
              f"$s.TargetPath='{python}';$s.Arguments='\"{launcher}\"';$s.WorkingDirectory='{BASE_DIR}';"
              f"$s.IconLocation='{icon}';$s.Save()")
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
        path = os.path.join(desktop, "eCommunicator.lnk")
    elif sys.platform == "darwin":
        path = os.path.join(desktop, "eCommunicator.command")
        with open(path, "w") as f:
            f.write(f'#!/bin/sh\ncd "{BASE_DIR}" && exec "{python}" "{launcher}"\n')
        os.chmod(path, 0o755)
    else:
        path = os.path.join(desktop, "eCommunicator.desktop")
        with open(path, "w") as f:
            f.write("[Desktop Entry]\nType=Application\nName=eCommunicator\nTerminal=false\n"
                    f'Exec="{python}" "{launcher}"\nPath={BASE_DIR}\nIcon={icon}\n')
        os.chmod(path, 0o755)
    print(f"Desktop shortcut created: {path}")


# 1. Hand off to the project's virtual environment if we were started with another Python.
# (sys.prefix, not the executable path: on Linux/macOS a venv's python is a symlink to the system one.)
venv_py = _venv_python()
in_venv = os.path.normcase(os.path.realpath(sys.prefix)).startswith(os.path.normcase(os.path.realpath(BASE_DIR)))
if venv_py and not in_venv and os.environ.get("EASD_LAUNCHER_HANDOFF") != "1":
    env = dict(os.environ, EASD_LAUNCHER_HANDOFF="1")
    cmd = [venv_py, os.path.abspath(__file__)] + sys.argv[1:]
    if "console" in ARGS or "shortcut" in ARGS:
        sys.exit(subprocess.call(cmd, cwd=BASE_DIR, env=env))
    subprocess.Popen(cmd, cwd=BASE_DIR, env=env)
    sys.exit(0)

if "shortcut" in ARGS:
    _create_shortcut(venv_py or sys.executable)
    sys.exit(0)

# 2. Under pythonw there is no console: send output to the log file.
LOG = os.path.join(BASE_DIR, "app_service.log")
for name in ("stdout", "stderr"):
    if getattr(sys, name) is None:
        try:
            setattr(sys, name, open(LOG, "a", encoding="utf-8", buffering=1))
        except Exception:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))

os.chdir(BASE_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

if __name__ == "__main__":
    try:
        import app
        import uvicorn
        if app.is_server_already_running(8000):  # already open: just bring the window up
            t = app.open_native_app_window("http://localhost:8000/", delay=0.1)
            if t:
                t.join(timeout=2.0)
            sys.exit(0)
        port = app.find_available_port(8000)
        if os.getenv("NO_BROWSER") != "true":
            app.open_native_app_window(f"http://localhost:{port}/", delay=0.1)
        uvicorn.run(app.app, host="127.0.0.1", port=port, log_level="info" if "console" in ARGS else "warning")
    except Exception as e:
        import traceback
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"\n[FATAL Launcher Error] {e}\n")
            traceback.print_exc(file=f)
        if "console" in ARGS:
            traceback.print_exc()
            input("Press Enter to close...")
        sys.exit(1)
