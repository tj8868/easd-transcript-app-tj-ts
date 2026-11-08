#!/usr/bin/env bash
# Build llama-server from TheTom's TurboQuant llama.cpp fork into bin/.
# The app starts it hidden in the background and runs the local LLM (Gemma 4 E2B, Q4_0)
# with the TurboQuant KV cache (-ctk turbo3 -ctv turbo4).
#
#   Usage:  scripts/build_llama_server.sh [auto|vulkan|cuda|metal|cpu]   (default: auto)
#
#   auto   = one build that runs on any device:
#            - macOS: Metal (Apple GPU).
#            - Linux: backends are built as plug-in libraries (GGML_BACKEND_DL). At start-up
#              llama-server loads the ones this machine can run and puts the model on the best
#              GPU it finds: CUDA (NVIDIA), else Vulkan (Intel Iris Xe / Arc / Core Ultra, AMD,
#              NVIDIA), else the fastest CPU variant for this processor.
#              Vulkan is included when glslc + libvulkan-dev are installed:
#                sudo apt install cmake g++ git libvulkan-dev glslc mesa-vulkan-drivers
#              CUDA is included when nvcc (CUDA toolkit) is installed.
#   vulkan / cuda / metal / cpu = force a single backend.
#
# Build alone: on an 8 GB PC a parallel download/build next to other work can run out of memory.
set -euo pipefail
GPU="${1:-auto}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

have() { command -v "$1" >/dev/null 2>&1; }
vulkan_ok() { have glslc && { [ -e /usr/include/vulkan/vulkan.h ] || [ -n "${VULKAN_SDK:-}" ]; }; }

COMMON="-DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF"
DYNAMIC=0
case "$GPU" in
  auto)
    if [ "$(uname -s)" = "Darwin" ]; then
      ARGS="-DGGML_METAL=ON -DGGML_NATIVE=ON -DBUILD_SHARED_LIBS=OFF"; GPU="auto (metal)"
    else
      DYNAMIC=1
      ARGS="-DBUILD_SHARED_LIBS=ON -DGGML_BACKEND_DL=ON -DGGML_CPU_ALL_VARIANTS=ON -DGGML_NATIVE=OFF"
      ARGS="$ARGS -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON -DCMAKE_INSTALL_RPATH=\$ORIGIN"
      INCLUDED="cpu"
      if vulkan_ok; then ARGS="$ARGS -DGGML_VULKAN=ON"; INCLUDED="$INCLUDED+vulkan"
      else echo "NOTE: glslc / Vulkan headers not found - building without Vulkan (see the apt line above)."; fi
      if have nvcc; then ARGS="$ARGS -DGGML_CUDA=ON"; INCLUDED="$INCLUDED+cuda"; fi
      GPU="auto ($INCLUDED)"
    fi ;;
  vulkan) ARGS="-DGGML_VULKAN=ON -DGGML_NATIVE=ON -DBUILD_SHARED_LIBS=OFF" ;;
  cuda)   ARGS="-DGGML_CUDA=ON -DGGML_NATIVE=ON -DBUILD_SHARED_LIBS=OFF" ;;
  metal)  ARGS="-DGGML_METAL=ON -DGGML_NATIVE=ON -DBUILD_SHARED_LIBS=OFF" ;;
  cpu)    ARGS="-DGGML_NATIVE=ON -DBUILD_SHARED_LIBS=OFF" ;;
  *) echo "unknown backend: $GPU (use auto|vulkan|cuda|metal|cpu)"; exit 1 ;;
esac

echo "Building llama-server: $GPU"
git clone --depth 1 -b feature/turboquant-kv-cache https://github.com/TheTom/llama-cpp-turboquant "$WORK/src"
# shellcheck disable=SC2086
cmake -S "$WORK/src" -B "$WORK/build" $COMMON $ARGS
# Two jobs at most: a full -j build of the Vulkan/CUDA backends can exhaust RAM on an 8 GB PC.
cmake --build "$WORK/build" --target llama-server -j"${JOBS:-2}"

mkdir -p "$HERE/bin"
if [ "$DYNAMIC" = 1 ]; then
  # Remove libraries from an earlier build so stale backends are not loaded.
  rm -f "$HERE"/bin/libggml*.so* "$HERE"/bin/libllama*.so* "$HERE"/bin/libmtmd*.so*
  cp -a "$WORK"/build/bin/*.so* "$HERE/bin/" 2>/dev/null || true
  find "$WORK/build" -name 'lib*.so*' -exec cp -a {} "$HERE/bin/" \;
fi
cp "$WORK/build/bin/llama-server" "$HERE/bin/llama-server"
echo "Done: $HERE/bin/llama-server [$GPU]. The app starts it automatically on next launch."
echo "Check which device it picked in llama_server.log (look for 'Vulkan', 'CUDA', 'Metal' or 'CPU')."
