# Gemini Prompt — v8.7 Speedup + v8.8 Action Bar Fix

**Model:** Gemini 3.8 Flash
**Reasoning effort:** High
*(This is a multi-file change with an exact code block that must be inserted correctly and exact CSS values that must match across two files — low/medium effort risks skipped steps or unwanted "simplification.")*

---

## Prompt (copy everything below into Gemini)

```
You are editing a real codebase called easd-transcript-app-tj-ts.
Repo: https://github.com/tj8868/easd-transcript-app-tj-ts

I need you to make TWO separate, small, careful changes. Do them ONE AT A TIME.
Do not refactor anything else. Do not rename variables. Do not "improve" code
outside of what I ask for below. Only touch the exact files I name.

=====================================================
TASK 1 of 2: Speed up audio transcription (backend only)
=====================================================

File to edit: ai_providers.py

Context: This file currently transcribes audio chunks ONE AT A TIME in a loop
(probably a "for chunk in audio_chunks:" loop). This is slow. I want you to
change it so all chunks are transcribed AT THE SAME TIME (in parallel),
instead of one after another.

Step 1: Find the function that loops over audio_chunks and calls a
transcription function on each one. Tell me the exact function name and
show me the current code before changing anything.

Step 2: Add this new function to ai_providers.py, near the function you found:

```python
import asyncio

MAX_CONCURRENT_CHUNKS = 5

async def transcribe_chunks_parallel(
    audio_chunks: list[bytes],
    provider: str,
    api_key: str,
    base_url: str,
    model_name: str,
    mime_type: str,
) -> list[str]:
    """Transcribe all audio chunks at the same time instead of one by one."""

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHUNKS)

    async def transcribe_one(index: int, chunk: bytes) -> tuple[int, str]:
        async with semaphore:
            text = await asyncio.to_thread(
                transcribe_single_chunk,   # REPLACE this with the real
                                            # per-chunk function name you found
                                            # in Step 1
                media_bytes=chunk,
                provider=provider,
                api_key=api_key,
                base_url=base_url,
                model_name=model_name,
                mime_type=mime_type,
            )
            return index, text

    tasks = [transcribe_one(i, chunk) for i, chunk in enumerate(audio_chunks)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    ordered = [None] * len(audio_chunks)
    for r in results:
        if isinstance(r, Exception):
            print(f"[transcribe_chunks_parallel] chunk failed: {r}")
            continue
        index, text = r
        ordered[index] = text

    return [t or "" for t in ordered]
```

Step 3: Replace the OLD sequential for-loop with a call to this new function
instead. Keep all the same input variables (provider, api_key, base_url,
model_name, mime_type) — just pass them into transcribe_chunks_parallel
instead of looping manually.

Step 4: IMPORTANT — check if the function that calls this loop is already
"async def" or a normal "def". Tell me which one it is.
- If it is already "async def": use "await transcribe_chunks_parallel(...)"
- If it is a normal "def" (not async): use "asyncio.run(transcribe_chunks_parallel(...))"
Do not guess — check the code and tell me which case it is before finishing.

Step 5: Show me the full final version of the changed function so I can review it.

Do NOT touch any frontend files in this task. Only ai_providers.py.

=====================================================
TASK 2 of 2: Fix the floating action bar (frontend only)
=====================================================

Only do this AFTER Task 1 is done and I confirm it's good.

Folder to search: frontend/src

Step 1: Search the frontend code for the text "Generate Prescription" to find
the file that renders the bottom bar with the buttons "Start New", "AI Audit",
and "Generate Prescription". Tell me the exact file name you found.

Step 2: In that file (or its CSS/style file), find the CSS rule for this bar.
It is probably using these properties right now:
    position: fixed;
    left: 0;
    right: 0;
    width: 100%;
Show me the current CSS before changing it.

Step 3: DELETE the "left: 0; right: 0; width: 100%;" lines completely.

Step 4: ADD these new lines in their place:

```css
position: fixed;
bottom: 24px;
left: 50%;
transform: translateX(-50%);
width: min(calc(100% - 32px), 720px);
max-width: 100%;
box-sizing: border-box;
border-radius: 20px;
background: #fff;
box-shadow: 0 8px 24px rgba(0,0,0,0.12);
padding: 16px 20px;
z-index: 50;
```

Step 5: Find the CSS for the main card (the box that has the text
"Record consultation sound fragments..."). Find its "max-width" value.
Tell me what number it is (for example "720px").

Step 6: If that number is NOT 720px, go back to Step 4's code and replace
"720px" with the real number you found in Step 5, so the bar and the card
are the same width.

Step 7: Find the parent container that holds the whole scrollable page
content (the div that wraps everything, including the card). Add this CSS
to that container:

```css
padding-bottom: 100px;
```

This stops the floating bar from covering content when you scroll to the bottom.

Step 8: Show me the full final CSS you changed, and tell me the file paths
you edited.

=====================================================
RULES FOR BOTH TASKS
=====================================================
- Only change the exact files named above.
- Do not touch any other file.
- Do not rename functions or variables that already exist.
- If you are not sure which function or file is the right one, STOP and ask
  me instead of guessing.
- After each task, show me a summary: file name, what changed, and why.
```
