import os
import sys

# Ensure project root is in sys.path when running pytest
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Shared fixtures modules (e.g. whisper_hallucination_fixtures.py) live next to the tests.
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

# The app rejects unknown Host headers (DNS-rebinding guard). Starlette's TestClient sends
# "Host: testserver", so allow that name for the test suite only. Must run before `import app`.
_hosts = {h for h in os.environ.get("EASD_ALLOWED_HOSTS", "").split(",") if h}
os.environ["EASD_ALLOWED_HOSTS"] = ",".join(sorted(_hosts | {"testserver"}))
# Don't start llama-server from the app's startup hook during tests.
os.environ.setdefault("EASD_LOCAL_LLM_PRELOAD", "0")
# Keep Bangla/English switching off unless a test turns it on (test_code_switch.py), so results
# don't depend on whether this PC has models/whisper-small.en installed.
os.environ.setdefault("EASD_CODE_SWITCH", "0")
