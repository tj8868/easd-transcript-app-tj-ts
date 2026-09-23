"""
Local, on-device LLM for filling the template JSON schema from a transcript --
no network call, runs on a phone-class CPU.

Why this exists
----------------
Previously "local" summarization meant `deep_semantic_synthesis`: pure regex/
keyword extraction, not a model at all. That's a fine last-resort fallback,
but it isn't what most people mean by "local model". This module adds a real
small instruction-tuned LLM (Qwen2.5-Instruct, GGUF, via llama.cpp) as the
actual local model, so the "Local Model" choice on the Generate button runs
real inference, with the template's JSON schema given to the model as
context exactly the way the cloud prompt does.

Model choice
------------
Qwen2.5-1.5B-Instruct (GGUF, Q4_K_M, ~1.0 GB) is the default: small enough
for a phone or an old laptop CPU, and Qwen2.5 was specifically trained to be
good at following structured/JSON output instructions. Qwen2.5-0.5B-Instruct
(~0.4 GB) is offered as an even-lighter fallback for very weak hardware via
EASD_LOCAL_LLM_MODEL=qwen2.5-0.5b. Gemma-2-2b-it is listed as an alternative
if the org prefers Google's model family.

Getting the weights onto the machine
-------------------------------------
This module does NOT bundle model weights (they're gigabytes and licensed
separately). On first use it tries to download the configured model from
Hugging Face straight into models/. If the machine has no internet access at
that moment (e.g. air-gapped office PCs), download it once on any machine
that does and copy the .gguf file into the app's models/ folder -- the exact
expected filename is printed in the error raised by ensure_model_ready().

Call flow
---------
    from local_llm_engine import generate_template_fill
    result = generate_template_fill(transcript, template_schema, org_context, custom_skills)

`generate_template_fill` raises `LocalLLMUnavailable` if llama-cpp-python
isn't installed or no model file is present -- callers (ai_providers.process_ai_request)
catch this and fall back to the regex-based deep_semantic_synthesis, logging
*why* the real model didn't run so that's visible instead of silently swapped.
"""
import os
import time
import threading
from typing import Any, Dict, Optional

from diag_logging import get_logger

log = get_logger("local_llm")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.environ.get("EASD_LOCAL_LLM_DIR") or os.path.join(BASE_DIR, "models")

# repo_id / filename on Hugging Face, + a human size for the log/error messages.
# All are Apache-2.0 / Gemma-license instruction-tuned models with small quantized GGUF builds.
SUPPORTED_MODELS: Dict[str, Dict[str, str]] = {
    "qwen2.5-1.5b": {
        "repo_id": "Qwen/Qwen2.5-1.5B-Instruct-GGUF",
        "filename": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "size": "~1.0 GB",
        "note": "Default. Good JSON-following quality, still fine on a phone/old laptop CPU."
    },
    "qwen2.5-0.5b": {
        "repo_id": "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
        "filename": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "size": "~0.4 GB",
        "note": "For very weak/low-RAM devices. Lower quality template fills."
    },
    "gemma-2-2b": {
        "repo_id": "google/gemma-2-2b-it-GGUF",
        "filename": "gemma-2-2b-it-Q4_K_M.gguf",
        "size": "~1.6 GB",
        "note": "Alternative if you prefer Google's model family. Needs a bit more RAM."
    },
}
DEFAULT_MODEL_KEY = os.environ.get("EASD_LOCAL_LLM_MODEL", "qwen2.5-1.5b")

_llm_cache: Dict[str, Any] = {}
_cache_lock = threading.Lock()


class LocalLLMUnavailable(Exception):
    """Raised when the local model can't run: dependency missing or weights not on disk."""
    pass


def get_model_path(model_key: Optional[str] = None) -> str:
    key = model_key or DEFAULT_MODEL_KEY
    info = SUPPORTED_MODELS.get(key, SUPPORTED_MODELS[DEFAULT_MODEL_KEY])
    return os.path.join(MODEL_DIR, info["filename"])


def is_local_llm_available(model_key: Optional[str] = None) -> bool:
    try:
        import llama_cpp  # noqa: F401
    except ImportError:
        return False
    return os.path.isfile(get_model_path(model_key))


def ensure_model_downloaded(model_key: Optional[str] = None) -> str:
    """
    Best-effort download of the configured model into MODEL_DIR. Returns the
    local path on success. Raises LocalLLMUnavailable with clear manual-install
    instructions if the download can't happen (no internet, huggingface_hub not
    installed, etc.) -- this is expected on machines without outbound internet;
    the model file can be copied in manually instead.
    """
    key = model_key or DEFAULT_MODEL_KEY
    info = SUPPORTED_MODELS.get(key, SUPPORTED_MODELS[DEFAULT_MODEL_KEY])
    dest_path = get_model_path(key)
    os.makedirs(MODEL_DIR, exist_ok=True)

    if os.path.isfile(dest_path):
        return dest_path

    log.info("Local LLM weights not found at %s -- attempting download (%s, %s)...",
              dest_path, info["repo_id"], info["size"])
    try:
        from huggingface_hub import hf_hub_download
        t0 = time.time()
        downloaded = hf_hub_download(repo_id=info["repo_id"], filename=info["filename"], local_dir=MODEL_DIR)
        if downloaded != dest_path and os.path.isfile(downloaded):
            try:
                os.replace(downloaded, dest_path)
            except Exception:
                dest_path = downloaded
        log.info("Downloaded local LLM weights to %s in %.1fs", dest_path, time.time() - t0)
        return dest_path
    except Exception as e:
        msg = (
            f"Could not auto-download the local model ({type(e).__name__}: {e}). "
            f"Place '{info['filename']}' ({info['size']}) manually in '{MODEL_DIR}' -- "
            f"download it from https://huggingface.co/{info['repo_id']} on any machine with "
            f"internet access and copy the file over."
        )
        log.warning(msg)
        raise LocalLLMUnavailable(msg) from e


def _load_model(model_key: Optional[str] = None):
    key = model_key or DEFAULT_MODEL_KEY
    with _cache_lock:
        if key in _llm_cache:
            return _llm_cache[key]

        try:
            from llama_cpp import Llama
        except ImportError as e:
            raise LocalLLMUnavailable(
                "llama-cpp-python is not installed. Run: pip install llama-cpp-python"
            ) from e

        path = get_model_path(key)
        if not os.path.isfile(path):
            path = ensure_model_downloaded(key)  # raises LocalLLMUnavailable if it can't get the weights

        n_threads = max(1, (os.cpu_count() or 4) - 1)
        log.info("Loading local LLM '%s' from %s (n_threads=%d, CPU-only)...", key, path, n_threads)
        t0 = time.time()
        llm = Llama(
            model_path=path,
            n_ctx=8192,          # enough for a full meeting transcript + schema + output
            n_threads=n_threads,
            n_gpu_layers=0,      # CPU-only by default so this runs on phones/weak hardware;
                                 # set EASD_LOCAL_LLM_GPU_LAYERS to offload layers if a GPU is present.
            verbose=False
        )
        gpu_layers = int(os.environ.get("EASD_LOCAL_LLM_GPU_LAYERS", "0") or "0")
        if gpu_layers:
            llm = Llama(model_path=path, n_ctx=8192, n_threads=n_threads, n_gpu_layers=gpu_layers, verbose=False)
        log.info("Local LLM '%s' loaded in %.1fs", key, time.time() - t0)
        _llm_cache[key] = llm
        return llm


def generate_template_fill(
    transcript: str,
    template_schema: Optional[Dict[str, Any]] = None,
    org_context: str = "",
    custom_skills: str = "",
    model_key: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.2
) -> Dict[str, Any]:
    """
    Runs the transcript + the template's JSON schema (as context, via the same
    system prompt the cloud path uses) through the local model and returns the
    same normalized {"summary": {...}, ...} shape summarize_text_gemini returns.

    Raises LocalLLMUnavailable if the model can't be loaded/run at all -- the
    caller should catch that and fall back further (e.g. to deep_semantic_synthesis).
    """
    # Lazy imports to avoid a circular import (ai_providers imports this module).
    from ai_providers import build_template_system_prompt, process_extracted_payload, extract_and_repair_json

    key = model_key or DEFAULT_MODEL_KEY
    llm = _load_model(key)  # raises LocalLLMUnavailable on failure

    system_prompt = build_template_system_prompt(template_schema, org_context=org_context, custom_skills=custom_skills)
    system_prompt += (
        "\n\nYou are running as a small on-device model with limited context. Be concise but complete: "
        "keep 'bangla_transcript' and 'english_transcript' to at most ~350 words each so the whole JSON fits."
    )
    user_prompt = f"Transcript:\n\n{transcript}\n\nReturn only the JSON object, nothing else."

    log.info("[local_llm:%s] generating template fill: transcript_chars=%d, max_tokens=%d",
              key, len(transcript or ""), max_tokens)
    t0 = time.time()
    try:
        resp = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}  # llama.cpp grammar-constrains valid JSON when supported
        )
        raw_text = (resp.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
    except Exception as e:
        log.error("[local_llm:%s] inference FAILED after %.1fs: %s: %s", key, time.time() - t0, type(e).__name__, e)
        raise LocalLLMUnavailable(f"Local model inference failed: {type(e).__name__}: {e}") from e

    elapsed = time.time() - t0
    parsed = extract_and_repair_json(raw_text) if raw_text else None
    log.info("[local_llm:%s] done in %.1fs, chars_out=%d, parsed=%s", key, elapsed, len(raw_text), bool(parsed))

    if not (parsed and isinstance(parsed, dict)):
        raise LocalLLMUnavailable(
            f"Local model returned unparseable JSON ({len(raw_text)} chars, first 200: {raw_text[:200]!r})"
        )

    out = process_extracted_payload(
        raw_text, fallback_content=transcript, custom_skills=custom_skills,
        org_context=org_context, template_schema=template_schema
    )
    out["model"] = f"local:{key}"
    out["local_llm_elapsed_sec"] = round(elapsed, 1)
    return out
