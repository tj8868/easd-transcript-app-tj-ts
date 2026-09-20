"""
EASD Meeting Minutes Desktop App Launcher (.pyw extension)
Windows natively associates .pyw files with pythonw.exe,
guaranteeing 0 console / command prompt windows.
"""
import os
import sys
import time

# Ensure current folder is in Python module path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import app

if __name__ == "__main__":
    # If server is already running, focus the application window and exit
    if app.is_server_already_running(8000):
        app.open_native_app_window("http://localhost:8000/", delay=0.1)
        time.sleep(0.5)
        sys.exit(0)

    import uvicorn
    port = app.find_available_port(8000)
    url = f"http://localhost:{port}/"
    app.open_native_app_window(url, delay=0.6)
    uvicorn.run(app.app, host="127.0.0.1", port=port, log_level="warning")
