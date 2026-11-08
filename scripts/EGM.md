# scripts

## Overview
Developer build helpers that compile `llama-server` from TheTom's TurboQuant llama.cpp fork (`feature/turboquant-kv-cache`) into the repo's `bin/` directory. The app uses that binary to run the local LLM (Gemma 4 E2B) with the turbo4 KV cache.

## Interface
- `build_llama_server.sh [vulkan|cuda|metal|cpu]` (Linux/macOS, default `vulkan`). Maps the backend to `-DGGML_VULKAN=ON`, `-DGGML_CUDA=ON`, `-DGGML_METAL=ON`, or no flag. Output: `bin/llama-server`.
- `build_llama_server.bat [vulkan|cuda|cpu]` (Windows, default `vulkan`). Output: `bin\llama-server.exe`.

## Invariants
- `bin/` is resolved relative to the script's parent directory (`HERE="$(dirname "$0")/.."` in the .sh, `%~dp0..` in the .bat), so the output always lands in `<repo>/bin` whatever the current directory.
- The .sh exits 1 on an unknown backend (`*) echo "unknown backend"`) and runs with `set -euo pipefail`. The .bat does not check the backend: any other value builds CPU-only. Each .bat step uses `|| exit /b 1`.
- Static build: `-DBUILD_SHARED_LIBS=OFF -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF`. Only the .sh adds `-DGGML_NATIVE=ON` and `-DCMAKE_BUILD_TYPE=Release`. The .bat uses `--config Release`.
- Requires `git` and `cmake` plus a C++ toolchain (.bat: Visual Studio Build Tools; for Vulkan, the LunarG Vulkan SDK).

## Side Effects
- Network: `git clone --depth 1` of `https://github.com/TheTom/llama-cpp-turboquant`.
- Disk: the .sh uses a `mktemp -d` work directory that a `trap ... EXIT` removes. The .bat uses `%TEMP%\easd_llama_build`, deletes it first if it exists, and leaves it in place afterwards.
- Creates `bin/` and overwrites `bin/llama-server` (or `bin\llama-server.exe`).

## Verification
- Run: `scripts/build_llama_server.sh cpu`, then check that `bin/llama-server` exists.
