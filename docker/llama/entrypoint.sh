#!/usr/bin/env bash
# Starts llama-server with flags tuned for the machine it is running on.
#
# Nothing here is hard-coded for one PC. On every start the script reads the hardware (CPU model,
# physical/logical cores, RAM, GPUs llama.cpp can see) and the build. The first time it sees a given
# combination it benchmarks the model with llama-bench (about 2-5 minutes on a dual-core i3) to find:
#   -t   threads for generation        (fastest token generation)
#   -tb  threads for prompt reading    (fastest prompt processing)
#   -ngl GPU layers: 99 or 0           (whichever finishes a typical template fill sooner)
# and caches the answer in /models/.easd-llama-tune/. Move the models folder to a faster PC, or add a
# GPU, and the fingerprint changes, so it re-benchmarks and the new hardware gets used automatically.
#
# Context size and KV-cache type scale with RAM. Every value can be forced with an environment variable:
#   EASD_LLM_THREADS, EASD_LLM_BATCH_THREADS, EASD_LLM_NGL, EASD_LLM_CTX, EASD_LLM_KV_K, EASD_LLM_KV_V,
#   EASD_LLM_UBATCH, EASD_AUTOTUNE=0 (skip benchmarking), EASD_RETUNE=1 (benchmark again).
set -uo pipefail

MODEL_FILE="${EASD_LLM_MODEL_FILE:-gemma-4-E2B-it-Q4_0.gguf}"
MODEL_URL="${EASD_LLM_MODEL_URL:-https://huggingface.co/ggml-org/gemma-4-E2B-it-GGUF/resolve/main/gemma-4-E2B-it-Q4_0.gguf}"
MODEL="/models/$MODEL_FILE"
TUNE_DIR=/models/.easd-llama-tune
PORT="${EASD_LLM_PORT:-8080}"
log() { echo "[easd-llama] $*"; }

# ---------- model ----------
if [ ! -s "$MODEL" ]; then
  log "model $MODEL_FILE not found in /models - downloading (one time, ~2.8 GB)"
  curl -fL --retry 5 --retry-delay 5 -C - -o "$MODEL.part" "$MODEL_URL" && mv "$MODEL.part" "$MODEL" \
    || { log "model download failed"; exit 1; }
fi

# ---------- hardware ----------
LOGICAL=$(nproc)
PHYSICAL=$(lscpu -p=Core,Socket 2>/dev/null | grep -v '^#' | sort -u | wc -l)
[ "${PHYSICAL:-0}" -ge 1 ] || PHYSICAL=$LOGICAL
CPU_MODEL=$(lscpu | sed -n 's/^Model name:[[:space:]]*//p' | head -1)
MEM_MB=$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo)
if [ -r /sys/fs/cgroup/memory.max ] && grep -qE '^[0-9]+$' /sys/fs/cgroup/memory.max; then
  CG_MB=$(( $(cat /sys/fs/cgroup/memory.max) / 1048576 )); [ "$CG_MB" -lt "$MEM_MB" ] && MEM_MB=$CG_MB
fi
GPUS=$(llama-server --list-devices 2>&1 | grep -E '^[[:space:]]+(Vulkan|CUDA|SYCL)[0-9]+:' | sed 's/^[[:space:]]*//')
BUILD=$(cat /opt/llama/BUILD_COMMIT 2>/dev/null || echo unknown)
HELP=$(llama-server --help 2>&1)
has_flag() { grep -q -- "$1" <<<"$HELP"; }
log "CPU: $CPU_MODEL | ${PHYSICAL} cores / ${LOGICAL} threads | RAM ${MEM_MB} MB | build $BUILD"
log "GPUs visible to llama.cpp: ${GPUS:-none}"

# ---------- benchmark (cached per hardware fingerprint) ----------
FP=$(printf '%s|%s|%s|%s|%s|%s' "$CPU_MODEL" "$LOGICAL" "$PHYSICAL" "$GPUS" "$BUILD" "$MODEL_FILE" | md5sum | cut -c1-12)
TUNE_FILE="$TUNE_DIR/$FP.env"
mkdir -p "$TUNE_DIR"
if [ "${EASD_RETUNE:-0}" = 1 ]; then rm -f "$TUNE_FILE"; fi

if [ ! -s "$TUNE_FILE" ] && [ "${EASD_AUTOTUNE:-1}" != 0 ]; then
  THREADS_LIST=$(printf '%s\n' "$PHYSICAL" "$LOGICAL" | sort -un | paste -sd,)
  NGL_LIST=0; [ -n "$GPUS" ] && NGL_LIST="0,99"
  log "first start on this hardware: benchmarking threads={$THREADS_LIST} gpu_layers={$NGL_LIST} (a few minutes)..."
  if llama-bench -m "$MODEL" -t "$THREADS_LIST" -ngl "$NGL_LIST" -fa 1 -p 256 -n 48 -r 2 -o csv \
       > "$TUNE_DIR/$FP.bench.csv" 2> "$TUNE_DIR/$FP.bench.log"; then
    # Score = seconds for a typical template fill: ~6000 prompt tokens read + ~1500 tokens written.
    python3 - "$TUNE_DIR/$FP.bench.csv" > "$TUNE_FILE" <<'PY' || rm -f "$TUNE_FILE"
import csv, sys
rows = list(csv.DictReader(open(sys.argv[1])))
best = {}
for r in rows:
    ngl, t, ts = int(r["n_gpu_layers"]), int(r["n_threads"]), float(r["avg_ts"])
    kind = "pp" if int(r["n_prompt"]) > 0 else "tg"
    cur = best.setdefault(ngl, {}).get(kind)
    if cur is None or ts > cur[1]:
        best[ngl][kind] = (t, ts)
score = {n: 6000 / b["pp"][1] + 1500 / b["tg"][1] for n, b in best.items() if "pp" in b and "tg" in b}
n = min(score, key=score.get)
b = best[n]
print(f"TUNED_NGL={n}\nTUNED_THREADS={b['tg'][0]}\nTUNED_BATCH_THREADS={b['pp'][0]}")
print(f"TUNED_PP={b['pp'][1]:.1f}\nTUNED_TG={b['tg'][1]:.1f}\nTUNED_FILL_SEC={score[n]:.0f}")
for k, v in sorted(score.items()):
    print(f"# gpu_layers={k}: prompt {best[k]['pp'][1]:.1f} tok/s, generate {best[k]['tg'][1]:.1f} tok/s, "
          f"typical fill ~{v:.0f}s", file=sys.stderr)
PY
    [ -s "$TUNE_FILE" ] && log "benchmark saved to $TUNE_FILE" || log "could not read benchmark output - using defaults"
  else
    log "benchmark failed (see $TUNE_DIR/$FP.bench.log) - using defaults"
  fi
fi
TUNED_NGL=0; TUNED_THREADS=$PHYSICAL; TUNED_BATCH_THREADS=$LOGICAL
# shellcheck disable=SC1090
[ -s "$TUNE_FILE" ] && . "$TUNE_FILE" && log "tuned: prompt ${TUNED_PP:-?} tok/s, generate ${TUNED_TG:-?} tok/s, typical fill ~${TUNED_FILL_SEC:-?}s"

# ---------- flags ----------
THREADS="${EASD_LLM_THREADS:-$TUNED_THREADS}"
BATCH_THREADS="${EASD_LLM_BATCH_THREADS:-$TUNED_BATCH_THREADS}"
NGL="${EASD_LLM_NGL:-$TUNED_NGL}"
# Context grows with RAM: 10k fits one meeting transcript plus the template prompt on an 8 GB PC.
if   [ "$MEM_MB" -le 10240 ]; then DEF_CTX=10240
elif [ "$MEM_MB" -le 20480 ]; then DEF_CTX=16384
else DEF_CTX=32768; fi
CTX="${EASD_LLM_CTX:-$DEF_CTX}"
# KV cache: TurboQuant turbo3/turbo4 saves the most memory on small PCs; q8_0 is near-lossless when RAM is plentiful.
if grep -q turbo3 <<<"$HELP" && [ "$MEM_MB" -lt 12288 ]; then DEF_K=turbo3; DEF_V=turbo4; else DEF_K=q8_0; DEF_V=q8_0; fi
KV_K="${EASD_LLM_KV_K:-$DEF_K}"; KV_V="${EASD_LLM_KV_V:-$DEF_V}"
DEF_UB=512; [ "$NGL" != 0 ] && DEF_UB=1024
UBATCH="${EASD_LLM_UBATCH:-$DEF_UB}"

ARGS=(-m "$MODEL" --host 0.0.0.0 --port "$PORT" -c "$CTX" -np 1 -t "$THREADS" -tb "$BATCH_THREADS"
      -ngl "$NGL" -fa on -ctk "$KV_K" -ctv "$KV_V" -b 2048 -ub "$UBATCH" --jinja)
has_flag --no-webui && ARGS+=(--no-webui)
# The template-fill system prompt is long and identical between requests: reuse its cached KV.
has_flag --cache-reuse && ARGS+=(--cache-reuse 256)
# With RAM to spare, keep the model pinned so the OS never pages it out mid-request.
[ "$MEM_MB" -ge 16384 ] && has_flag --mlock && ARGS+=(--mlock)

log "starting: threads=$THREADS batch_threads=$BATCH_THREADS gpu_layers=$NGL ctx=$CTX kv=$KV_K/$KV_V ubatch=$UBATCH"
exec llama-server "${ARGS[@]}"
