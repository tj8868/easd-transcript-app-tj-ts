"""
Proves the Generate button's backend call (process_ai_request -> summarize_text_gemini
/ local_llm_engine.generate_template_fill / summarize_text_openai_compatible) actually invokes
a model in every mode,
with the template's JSON schema passed to the model as context, and that a genuine
model-unavailable local case falls back honestly (visible warning, not silent).

No real network call and no real GGUF weights are used -- both the Gemini client and
llama_cpp are replaced with fakes so this runs anywhere, deterministically. That
satisfies "simulated API call" for the cloud path; the local path is proven the same
way since no model weights can be fetched in this environment either (see FIX_NOTES).

Run: python3 test_local_and_cloud_generate.py
"""
import sys
import types
import json
from unittest.mock import patch, MagicMock

import ai_providers
from template_engine import DEFAULT_TEMPLATES, get_template_json_schema

SAMPLE_TRANSCRIPT = (
    "[00:00] Speaker 1: Good morning, let's start the EASD quarterly review.\n"
    "[00:20] Speaker 2: Field team completed 340 household visits this quarter.\n"
    "[01:05] Speaker 1: Action item: Rahim to submit the Q4 budget by Friday."
)
SCHEMA = get_template_json_schema(DEFAULT_TEMPLATES[0])

FAKE_MODEL_JSON = {
    "summary": {
        "title": "EASD Quarterly Review Meeting",
        "bangla_transcript": "সভায় মাঠ পর্যায়ের কার্যক্রম পর্যালোচনা করা হয়।",
        "english_transcript": "The meeting reviewed field-level activities for the quarter.",
    }
}


# ---------------------------------------------------------------------------
# 1. CLOUD (Gemini) path -- simulated network call
# ---------------------------------------------------------------------------
def test_cloud_path_is_called():
    print("\n=== TEST 1: Cloud (Gemini) path ===")
    call_log = {"prompt_seen": None, "called": False}

    fake_response = MagicMock()
    fake_response.text = json.dumps(FAKE_MODEL_JSON)
    fake_response.candidates = [MagicMock(finish_reason="STOP")]

    fake_client = MagicMock()

    def fake_generate_content(model, contents, config=None):
        call_log["called"] = True
        call_log["prompt_seen"] = contents
        return fake_response

    fake_client.models.generate_content.side_effect = fake_generate_content

    import stt_pipeline
    with patch.object(stt_pipeline, "_gemini_client", return_value=fake_client):
        result = ai_providers.process_ai_request(
            provider="gemini",
            api_key="FAKE-SIMULATED-KEY",
            summarization_provider="gemini",
            summarization_model="gemini-3.8-flash",
            text_content=SAMPLE_TRANSCRIPT,
            template_schema=SCHEMA,
        )

    assert call_log["called"], "Gemini client.models.generate_content was never called"
    assert '"title"' in json.dumps(SCHEMA) or "fields" in SCHEMA, "sanity check on schema shape"
    assert '"key"' in call_log["prompt_seen"] or "JSON Schema" in call_log["prompt_seen"], \
        "the JSON schema must be present in the prompt sent to the model"
    assert result.get("summary", {}).get("title") == "EASD Quarterly Review Meeting"
    assert result.get("model", "").startswith("gemini")
    print("OK: Gemini client.models.generate_content() was called")
    print("OK: the template's JSON schema was included in the prompt sent to the model")
    print(f"OK: parsed result summary.title = {result['summary']['title']!r}")


# ---------------------------------------------------------------------------
# 2. LOCAL model path -- simulated llama.cpp (no real weights needed)
# ---------------------------------------------------------------------------
def test_local_path_is_called():
    print("\n=== TEST 2: Local (Qwen, on-device) path ===")
    call_log = {"messages_seen": None, "called": False}

    class FakeLlama:
        def __init__(self, model_path, n_ctx, n_threads, n_gpu_layers, verbose):
            call_log["init_args"] = dict(model_path=model_path, n_ctx=n_ctx, n_gpu_layers=n_gpu_layers)

        def create_chat_completion(self, messages, temperature, max_tokens, response_format=None):
            call_log["called"] = True
            call_log["messages_seen"] = messages
            return {"choices": [{"message": {"content": json.dumps(FAKE_MODEL_JSON)}}]}

    fake_llama_cpp = types.ModuleType("llama_cpp")
    fake_llama_cpp.Llama = FakeLlama

    import local_llm_engine
    local_llm_engine._llm_cache.clear()

    with patch.dict(sys.modules, {"llama_cpp": fake_llama_cpp}):
        with patch("os.path.isfile", return_value=True):  # pretend the .gguf file is present on disk
            result = ai_providers.process_ai_request(
                provider="gemini",  # STT provider irrelevant here, no audio in this call
                summarization_provider="local",
                text_content=SAMPLE_TRANSCRIPT,
                template_schema=SCHEMA,
            )

    assert call_log["called"], "llama_cpp.Llama.create_chat_completion was never called"
    system_msg = call_log["messages_seen"][0]["content"]
    assert "JSON Schema" in system_msg, "the JSON schema must be included in the local model's system prompt"
    user_msg = call_log["messages_seen"][1]["content"]
    assert SAMPLE_TRANSCRIPT.split("\n")[0] in user_msg, "the transcript must be passed to the local model"
    assert result.get("summary", {}).get("title") == "EASD Quarterly Review Meeting"
    assert result.get("model", "").startswith("local:")
    assert "warning" not in result or not result.get("warning"), \
        "a successful local-model run should not carry a fallback warning"
    print("OK: llama_cpp.Llama.create_chat_completion() was called (real inference call site exercised)")
    print("OK: the template's JSON schema was included in the local model's system prompt")
    print("OK: the transcript text reached the local model's user prompt")
    print(f"OK: parsed result summary.title = {result['summary']['title']!r}, model={result['model']!r}")


# ---------------------------------------------------------------------------
# 3. LOCAL model genuinely unavailable -> honest fallback, not silent
# ---------------------------------------------------------------------------
def test_local_unavailable_falls_back_honestly():
    print("\n=== TEST 3: Local model unavailable -> honest fallback ===")
    import local_llm_engine
    local_llm_engine._llm_cache.clear()

    # No llama_cpp importable AND no model file -> is_local_llm_available() is False
    real_import = __import__

    def blocking_import(name, *a, **k):
        if name == "llama_cpp":
            raise ImportError("simulated: llama-cpp-python not installed")
        return real_import(name, *a, **k)

    with patch("builtins.__import__", side_effect=blocking_import):
        result = ai_providers.process_ai_request(
            provider="gemini",
            summarization_provider="local",
            text_content=SAMPLE_TRANSCRIPT,
            template_schema=SCHEMA,
        )

    assert result.get("warning"), "must surface a warning when falling back, never a silent success"
    assert "Local model could not run" in result["warning"]
    assert result.get("summary"), "offline fallback should still fill what it can from the transcript"
    print(f"OK: honest warning surfaced -> {result['warning'][:120]}...")
    print("OK: fields still filled offline from real transcript text (no fabricated content)")


# ---------------------------------------------------------------------------
# 4-10. CUSTOM OpenAI-compatible provider (v8.5) -- OpenRouter / DeepSeek via a fake
# httpx transport (outermost network call); Ollama / LM Studio via a real local HTTP
# stub server on localhost (real sockets, real httpx). No live keys are used.
# ---------------------------------------------------------------------------
import httpx
import threading
import socket
import tempfile
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

LEAK_MARKERS = ("Traceback", "httpx.", "Exception", "Error:", "{\"error\"", "File \"")


def _completion(content):
    return {"id": "cmpl-1", "model": "fake", "choices": [{"index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": content}}], "usage": {"total_tokens": 42}}


def _patch_httpx_transport(handler):
    """Routes every httpx.Client created inside ai_providers through a MockTransport."""
    real_client = httpx.Client
    return patch("ai_providers.httpx.Client",
                 side_effect=lambda *a, **k: real_client(transport=httpx.MockTransport(handler),
                                                         **{kk: vv for kk, vv in k.items() if kk == "timeout"}))


def _run_custom(base_url, model, key, handler=None):
    import stt_pipeline
    never_gemini = MagicMock(side_effect=AssertionError("Gemini must not be called for the custom provider"))
    ctx = _patch_httpx_transport(handler) if handler else patch("builtins.id", side_effect=id)
    with ctx, patch.object(stt_pipeline, "_gemini_client", never_gemini):
        return ai_providers.process_ai_request(
            provider="openai_compatible", summarization_provider="openai_compatible",
            summarization_api_key=key, base_url=base_url, summarization_model=model,
            text_content=SAMPLE_TRANSCRIPT, template_schema=SCHEMA,
        )


def _cloud_case(label, base_url, model, key):
    print(f"\n=== {label}: {base_url} model={model} (fake transport, no live key) ===")
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_completion(json.dumps(FAKE_MODEL_JSON)))

    result = _run_custom(base_url, model, key, handler)
    assert seen["url"] == base_url.rstrip("/") + "/chat/completions", seen["url"]
    assert seen["auth"] == f"Bearer {key}"
    assert seen["body"]["model"] == model
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert "JSON Schema" in seen["body"]["messages"][0]["content"], "schema must be in the system prompt"
    assert SAMPLE_TRANSCRIPT.split("\n")[0] in seen["body"]["messages"][1]["content"]
    assert result["summary"]["title"] == "EASD Quarterly Review Meeting"
    assert result["model"] == f"openai_compatible:{model}" and not result.get("warning")
    print(f"OK: POST {seen['url']} with Bearer key, response_format=json_object, schema in system prompt")
    print(f"OK: template filled -> title={result['summary']['title']!r}, model={result['model']!r}")


def test_openrouter():
    _cloud_case("TEST 4: OpenRouter", "https://openrouter.ai/api/v1", "deepseek/deepseek-v4.1-flash", "sk-or-FAKE-0000")


def test_deepseek_direct():
    _cloud_case("TEST 5: DeepSeek direct", "https://api.deepseek.com/v1", "deepseek-chat", "sk-FAKE-DEEPSEEK-1111")


class _StubOpenAIServer:
    """Minimal OpenAI-compatible HTTP server (like Ollama / LM Studio) on a free localhost port."""

    def __init__(self, reject_response_format=False, plain_text_answer=False):
        self.requests = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, obj):
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                outer.requests.append(("GET", self.path, dict(self.headers), None))
                self._send(200, {"object": "list", "data": [{"id": "llama3.1"}, {"id": "qwen2.5-7b-instruct"}]})

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append(("POST", self.path, dict(self.headers), payload))
                if reject_response_format and "response_format" in payload:
                    return self._send(400, {"error": "'response_format.type' must be 'json_schema'"})
                content = json.dumps(FAKE_MODEL_JSON)
                if plain_text_answer:
                    content = "Sure! Here is the filled template:\n```json\n" + content + "\n```\nLet me know."
                self._send(200, _completion(content))

        self.httpd = HTTPServer(("127.0.0.1", 0), H)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()


def test_ollama_local():
    print("\n=== TEST 6: Ollama-style local server (real localhost HTTP stub, no real Ollama) ===")
    srv = _StubOpenAIServer()
    try:
        result = _run_custom(f"http://127.0.0.1:{srv.port}/v1", "llama3.1", "ollama")
    finally:
        srv.close()
    method, path, headers, payload = srv.requests[0]
    assert (method, path) == ("POST", "/v1/chat/completions")
    assert headers.get("Authorization") == "Bearer ollama"
    assert payload["response_format"] == {"type": "json_object"}
    assert result["summary"]["title"] == "EASD Quarterly Review Meeting" and not result.get("warning")
    print(f"OK: real HTTP POST to localhost:{srv.port}/v1/chat/completions, template filled")


def test_lmstudio_rejects_response_format():
    print("\n=== TEST 7: LM Studio-style server rejects response_format -> retry without it + JSON salvage ===")
    srv = _StubOpenAIServer(reject_response_format=True, plain_text_answer=True)
    try:
        result = _run_custom(f"http://127.0.0.1:{srv.port}/v1", "qwen2.5-7b-instruct", "")
    finally:
        srv.close()
    posts = [r for r in srv.requests if r[0] == "POST"]
    assert len(posts) == 2, f"expected exactly one retry, got {len(posts)} POSTs"
    assert "response_format" in posts[0][3] and "response_format" not in posts[1][3]
    assert "Authorization" not in posts[1][2], "no key configured -> no Authorization header"
    assert result["summary"]["title"] == "EASD Quarterly Review Meeting"
    assert result.get("response_format_fallback") is True and not result.get("warning")
    print("OK: 400 on response_format -> one retry without it -> JSON salvaged from a fenced prose answer")


def test_unreachable_base_url():
    print("\n=== TEST 8: Unreachable Base URL -> clear error, no Gemini fallback, no hang ===")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        dead_port = s.getsockname()[1]  # closed again -> nothing listening
    import time as _t
    t0 = _t.time()
    result = _run_custom(f"http://127.0.0.1:{dead_port}/v1", "llama3.1", "")
    elapsed = _t.time() - t0
    warning = result.get("warning", "")
    assert "Custom API could not fill the template" in warning and "could not connect" in warning, warning
    assert not any(m in warning for m in LEAK_MARKERS), f"internal detail leaked: {warning}"
    assert result.get("summary_source") == "offline_extraction"
    assert elapsed < 15, f"took {elapsed:.1f}s"
    print(f"OK: failed in {elapsed:.1f}s with: {warning[:140]}...")


def test_auth_error_is_plain_language():
    print("\n=== TEST 9: 401 from the endpoint -> plain-language warning, raw body only in the log ===")

    def handler(request):
        return httpx.Response(401, json={"error": {"message": "Invalid API key sk-or-SECRET", "code": 401}})

    result = _run_custom("https://openrouter.ai/api/v1", "deepseek/deepseek-v4.1-flash", "sk-or-bad", handler)
    warning = result["warning"]
    assert "rejected the API key" in warning and "sk-or-SECRET" not in warning, warning
    assert not any(m in warning for m in LEAK_MARKERS), warning
    print(f"OK: {warning[:120]}...")


def test_settings_persist_and_ping():
    print("\n=== TEST 10: custom endpoint settings persist across restart; /api/verify_key pings /models ===")
    from fastapi.testclient import TestClient
    import app as app_module
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.write(json.dumps({"gemini_api_key": "AIzaSyKEEP-THIS-KEY"}).encode())
    tmp.close()
    with patch.object(ai_providers, "SETTINGS_FILE", tmp.name), patch.object(ai_providers, "GEMINI_KEY_FILE", tmp.name + ".txt"):
        client = TestClient(app_module.app)
        r = client.post("/api/settings", json={"summarization_provider": "openai_compatible",
                                               "custom_api_base_url": "https://openrouter.ai/api/v1",
                                               "custom_api_key": "sk-or-FAKE-0000",
                                               "custom_api_model": "deepseek/deepseek-v4.1-flash"})
        assert r.status_code == 200
        on_disk = json.load(open(tmp.name))  # what a restarted app would load
        assert on_disk["custom_api_base_url"] == "https://openrouter.ai/api/v1"
        assert on_disk["custom_api_model"] == "deepseek/deepseek-v4.1-flash"
        assert on_disk["custom_api_key"] == "sk-or-FAKE-0000"
        assert on_disk["gemini_api_key"] == "AIzaSyKEEP-THIS-KEY", "saving one section must not wipe the Gemini key"
        assert client.get("/api/settings").json()["settings"]["custom_api_model"] == "deepseek/deepseek-v4.1-flash"
        print("OK: base URL / key / model persisted to api_settings.json; Gemini key untouched")

        srv = _StubOpenAIServer()
        try:
            v = client.post("/api/verify_key", json={"provider": "openai_compatible", "api_key": "ollama",
                                                     "base_url": f"http://127.0.0.1:{srv.port}/v1"}).json()
        finally:
            srv.close()
        assert v["valid"] and srv.requests[0][:2] == ("GET", "/v1/models"), (v, srv.requests)
        print(f"OK: /api/verify_key -> GET /v1/models -> {v['message']}")
    os.remove(tmp.name)


if __name__ == "__main__":
    test_cloud_path_is_called()
    test_local_path_is_called()
    test_local_unavailable_falls_back_honestly()
    test_openrouter()
    test_deepseek_direct()
    test_ollama_local()
    test_lmstudio_rejects_response_format()
    test_unreachable_base_url()
    test_auth_error_is_plain_language()
    test_settings_persist_and_ping()
    print("\n=== ALL TESTS PASSED: Generate triggers a real model call for Gemini, local and custom providers ===")
