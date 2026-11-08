Gemini 3.5 Transcribe is Google's model for converting speech to text in multiple languages, available through Agent Platform. Based on Gemini's audio understanding capabilities, it provides low-latency, accurate transcription with utterance-based language detection, speaker diarization, word-level timestamps, [Smart transcription](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-5-transcribe#transcription-modes), and custom vocabulary speech biasing.

Gemini 3.5 Transcribe serves as the primary audio transcription workhorse, bridging the gap between deep-reasoning multi-modal models and highly optimized speech-to-text workflows.

To get started, view the [introductory notebook for
Gemini 3.5 Transcribe](https://github.com/GoogleCloudPlatform/generative-ai/blob/main/audio/speech/getting-started/gemini_3_5_transcribe.ipynb).

It supports two primary methods of operation:

- **Streaming (Live) transcription:** Streams audio and receives transcription results incrementally, in real time, using the `gemini-3.5-transcribe-live` model.
- **Synchronous transcription:** Transcribes complete, prerecorded audio files in a single request using the `gemini-3.5-transcribe` model.

## Feature support and limitations

Gemini 3.5 Transcribe supports the following features across its two endpoints:

| Feature | Live Streaming (`gemini-3.5-transcribe-live`) | Audio File Processing (`gemini-3.5-transcribe`) | Launch Stage | Notes / Limitations |
|---|---|---|---|---|
| **Language Auto-detection** | Supported (85+ languages) | Supported (85+ languages) | Supported | Includes mid-session code-mixing. |
| **Utterance-level Timestamps** | Supported | Not Supported | Supported |   |
| **Word-level Timestamps** | Not Supported | Supported | Experimental | Degrades transcription accuracy. |
| **Custom Vocabulary Biasing** | Supported (up to 1000 terms) | Supported (up to 1000 terms) | Supported | Customers typically see best results with up to 100 terms. |
| **Smart Dictation \& Formatting** | Supported (with manual endpointing) | Supported | Experimental | Includes filler word removal and intent-aware alphanumeric formatting. For live streaming, use with [manual endpointing](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-5-transcribe#smart-live-manual-endpointing). |
| **Speaker Diarization** | Not Supported | Supported (up to 8 speakers) | Experimental | Attribution for 3+ speakers is Experimental. |
| **Max Audio Duration** | Up to 10 minutes | Up to 15 minutes | Supported | File processing is limited to 15 minutes when features like diarization or timestamps are enabled. |

## Live streaming transcription

The `BidiGenerateContent (Live) API` stays open while you stream small chunks of audio to the model and receive transcription results incrementally, as they become available. This is used for near real-time captioning or transcribing microphone input.

To try streaming transcription without writing any code, open
`gemini-3.5-transcribe-live` on the Gemini Live API page of
Agent Studio, then record or upload audio and
watch the transcript stream back.

[Try Gemini 3.5 Transcribe in Agent Studio](https://console.cloud.google.com/agent-platform/studio/multimodal-live?model=gemini-3.5-transcribe-live)

To transcribe streaming audio, build a `LiveConnectConfig` and set the response_modalities to \["TEXT"\] alongside your input_audio_transcription configuration.

    import asyncio
    from google import genai
    from google.genai import types

    client = genai.Client(enterprise=True, project=PROJECT_ID, location=LOCATION)

    config = types.LiveConnectConfig(
        response_modalities=["TEXT"],
        input_audio_transcription=types.AudioTranscriptionConfig(
            language_codes=["it-IT", "en-US"],
        ),
    )

    async def streaming_main(audio_file, config):
        # Connect to the Live API session
        async with client.aio.live.connect(model="gemini-3.5-transcribe-live", config=config) as session:
            # In a complete implementation, you would chunk the audio and send via:
            # await session.send_realtime_input(audio=types.Blob(data=data, mime_type="audio/pcm;rate=16000"))
            # await session.send_realtime_input(audio_stream_end=True)

            async for message in session.receive():
                if message.server_content:
                    server_content = message.server_content

                    # Track the active interim segment
                    interim = server_content.interim_input_transcription
                    if interim and interim.text:
                        print(f"Interim: {interim.text}")

                    # Save final transcript and clear the interim
                    final = server_content.input_transcription
                    if final and final.text:
                        print(f"Final: {final.text}")

> [!NOTE]
> **Note:** When establishing a Live API connection, clients must wait to receive the `setup_complete` message from the server before streaming audio data. Sending audio requests before `setup_complete` is received can cause the session to cancel unexpectedly and may result in empty transcriptions, particularly on short audio clips.

## Synchronous transcription

You can use the standard `generate_content` method to transcribe complete audio files that have already been recorded. Configure the parameters by building an `AudioTranscriptionConfig` inside `GenerateContentConfig`.

### Word-level timestamps

Setting `word_timestamp=True` returns word-level timing. The response's `audio_transcription.words` list contains each recognized word along with its `start_offset` and `end_offset`.

    from google import genai
    from google.genai import types

    # Initialize the client for Vertex AI / Agent Platform
    client = genai.Client(enterprise=True, project=PROJECT_ID, location=LOCATION)

    with open("input.wav", "rb") as f:
        audio_bytes = f.read()

    response = client.models.generate_content(
        model="gemini-3.5-transcribe",
        contents=[
            types.Part.from_bytes(
                data=audio_bytes,
                mime_type="audio/wav",
            ),
        ],
        config=types.GenerateContentConfig(
            audio_transcription_config=types.AudioTranscriptionConfig(
                word_timestamp=True,
            ),
        ),
    )

    parts = getattr(response, "parts", []) or []
    if parts and (audio_tx := getattr(parts[0], "audio_transcription", None)):
        for w in getattr(audio_tx, "words", []) or []:
            print(f"[{w.start_offset} - {w.end_offset}] {w.word}")

    if text := "".join(p.text for p in parts if getattr(p, "text", None)):
        print(f"**{text}**")

### Speaker diarization and custom vocabulary

Setting diarization=True asks the model to identify and label individual speakers. You can also supply a custom_vocabulary field with a list of phrases that bias Gemini 3.5 Transcribe toward recognizing specific terms. The model generally follows custom vocabulary instructions more reliably when a language is also specified using language_codes.

    response = client.models.generate_content(
        model="gemini-3.5-transcribe",
        contents=[
            types.Part.from_uri(
                file_uri="gs://cloud-samples-data/generative-ai/audio/coffee_order.wav",
                mime_type="audio/wav",
            ),
        ],
        config=types.GenerateContentConfig(
            audio_transcription_config=types.AudioTranscriptionConfig(
                diarization=True,
                language_codes=["en-US"],
                custom_vocabulary=["oatmilk", "oz"],
            ),
        ),
    )

    parts = getattr(response, "parts", []) or []
    for p in parts:
        audio_tx = getattr(p, "audio_transcription", None)
        speaker = getattr(audio_tx, "speaker_label", "UNKNOWN") if audio_tx else "UNKNOWN"
        text = getattr(p, "text", "") or (getattr(audio_tx, "text", "") if audio_tx else "")

        if text:
            print(f"**{speaker}**: {text}")

## Transcription modes

Gemini 3.5 Transcribe supports two transcription modes through the `mode` parameter in `AudioTranscriptionConfig`:

- **`VERBATIM` (default):** Returns an exact word-for-word transcript of everything spoken, preserving raw filler words ("um", "uh", "like", "you know"), repetitions, pauses, and false starts.
- **`SMART` (Smart transcription):** Optimizes the transcript for reading by applying intelligent post-processing:
  - **Disfluency removal:** Strips conversational filler words, stuttering, and false starts.
  - **Inline self-corrections:** Resolves spoken corrections directly (for example, *"Let's meet on Tuesday, actually no, Wednesday at two"* becomes *"Let's meet on Wednesday at 2:00 PM"*).
  - **Automatic structured formatting:** Automatically structures spoken thoughts into paragraphs, numbered lists, bullet points, formatted dates, currencies, and numbers.
  - **Grammatical cleanup:** Applies natural punctuation, sentence casing, and flow.

| Spoken audio | `VERBATIM` output | `SMART` (Smart transcription) output |
|---|---|---|
| "Um, so for the meeting, I think we should, uh, invite Alice and, wait no, Bob and Carol." | "Um so for the meeting I think we should uh invite Alice and wait no Bob and Carol." | "For the meeting, I think we should invite Bob and Carol." |
| "First item review budget second item finalize timeline third item send recap" | "first item review budget second item finalize timeline third item send recap" | "1. Review budget 2. Finalize timeline 3. Send recap" |

### Synchronous transcription with `SMART` mode

    response = client.models.generate_content(
        model="gemini-3.5-transcribe",
        contents=[
            types.Part.from_bytes(
                data=audio_bytes,
                mime_type="audio/wav",
            ),
        ],
        config=types.GenerateContentConfig(
            audio_transcription_config=types.AudioTranscriptionConfig(
                mode="SMART",
            ),
        ),
    )

### Live transcription with `SMART` mode and manual endpointing

When using `SMART` mode with live streaming transcription (`gemini-3.5-transcribe-live`), you should use **manual endpointing** (manual Voice Activity Detection) instead of automatic VAD. Because `SMART` mode applies utterance-level post-processing---such as resolving inline self-corrections and structuring lists or paragraphs---automatic VAD may prematurely split a user's thought during natural pauses.

To configure manual endpointing, disable `automatic_activity_detection` in `RealtimeInputConfig` and explicitly mark the beginning and end of the user's speech turn using `activity_start` and `activity_end`:

    config = types.LiveConnectConfig(
        response_modalities=["TEXT"],
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                disabled=True,
            ),
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(
            mode="SMART",
        ),
    )

    async with client.aio.live.connect(
        model="gemini-3.5-transcribe-live", config=config
    ) as session:
        # Signal start of speech turn
        await session.send_realtime_input(activity_start=types.ActivityStart())

        # Stream audio chunks...
        await session.send_realtime_input(
            audio=types.Blob(data=audio_bytes, mime_type="audio/pcm;rate=16000")
        )

        # Signal end of speech turn so SMART mode can process the complete utterance
        await session.send_realtime_input(activity_end=types.ActivityEnd())

> [!NOTE]
> **Note:** Smart transcription (`SMART`) is incompatible with `word_timestamp` and `diarization`. If you need word-level timestamps or speaker diarization, use `VERBATIM` mode.

## Language support

The following languages and BCP-47 language codes are supported for Gemini 3.5 Transcribe:

| Language | BCP-47 Code | Readiness | Language | BCP-47 Code | Readiness |
|---|---|---|---|---|---|
| Afrikaans | `af-ZA` | Experimental | Japanese | `ja-JP` | Supported |
| Amharic | `am-ET` | Experimental | Javanese | `jv-ID` | Experimental |
| Arabic (Egypt) | `ar-EG` | Experimental | Kabuverdianu | `kea-CV` | Experimental |
| Armenian | `hy-AM` | Experimental | Kannada | `kn-IN` | Experimental |
| Assamese | `as-IN` | Experimental | Kazakh | `kk-KZ` | Experimental |
| Azerbaijani | `az-AZ` | Experimental | Korean | `ko-KR` | Supported |
| Belarusian | `be-BY` | Experimental | Kyrgyz | `ky-KG` | Experimental |
| Bengali (Bangladesh) | `bn-BD` | Experimental | Latvian | `lv-LV` | Experimental |
| Bengali (India) | `bn-IN` | Experimental | Lingala | `ln-CD` | Experimental |
| Bosnian | `bs-BA` | Experimental | Lithuanian | `lt-LT` | Experimental |
| Bulgarian | `bg-BG` | Experimental | Macedonian | `mk-MK` | Experimental |
| Bulgarian (Aromanian) | `rup-BG` | Experimental | Malay | `ms-MY` | Experimental |
| Burmese | `my-MM` | Experimental | Malayalam | `ml-IN` | Experimental |
| Cantonese (Traditional) | `yue-Hant-HK` | Experimental | Maltese | `mt-MT` | Experimental |
| Catalan | `ca-ES` | Supported | Mandarin Chinese (Simplified) | `cmn-Hans-CN` | Supported |
| Cebuano | `ceb` | Experimental | Marathi | `mr-IN` | Experimental |
| Central Khmer | `km-KH` | Experimental | Mongolian | `mn-MN` | Experimental |
| Croatian | `hr-HR` | Supported | Nepali | `ne-NP` | Experimental |
| Czech | `cs-CZ` | Experimental | Norwegian | `nb-NO` | Experimental |
| Danish | `da-DK` | Supported | Oriya | `or-IN` | Experimental |
| Dutch | `nl-NL` | Supported | Polish | `pl-PL` | Supported |
| English (Australia) | `en-AU` | Supported | Portuguese (Brazil) | `pt-BR` | Supported |
| English (Great Britain) | `en-GB` | Supported | Portuguese (Portugal) | `pt-PT` | Supported |
| English (India) | `en-IN` | Supported | Punjabi | `pa-IN` | Experimental |
| English (United States) | `en-US` | Supported | Punjabi (Gurmukhi script) | `pa-Guru-IN` | Experimental |
| Estonian | `et-EE` | Experimental | Romanian | `ro-RO` | Supported |
| Farsi | `fa-IR` | Experimental | Russian | `ru-RU` | Supported |
| Filipino | `fil-PH` | Experimental | Serbian | `sr-RS` | Experimental |
| Finnish | `fi-FI` | Supported | Sindhi (Arabic script) | `sd-Arab-IN` | Experimental |
| French | `fr-FR` | Supported | Slovak | `sk-SK` | Experimental |
| French (Canada) | `fr-CA` | Supported | Slovenian | `sl-SI` | Experimental |
| Galician | `gl-ES` | Experimental | Spanish (Latin America) | `es-419` | Experimental |
| Georgian | `ka-GE` | Experimental | Spanish (Spain) | `es-ES` | Supported |
| German | `de-DE` | Supported | Spanish (United States) | `es-US` | Supported |
| Greek | `el-GR` | Supported | Swahili (Kenya) | `sw-KE` | Experimental |
| Gujarati | `gu-IN` | Experimental | Swedish | `sv-SE` | Supported |
| Hausa | `ha-NG` | Experimental | Tajik | `tg-TJ` | Experimental |
| Hebrew | `he-IL` | Experimental | Telugu | `te-IN` | Experimental |
| Hindi | `hi-IN` | Supported | Thai | `th-TH` | Experimental |
| Hungarian | `hu-HU` | Experimental | Turkish | `tr-TR` | Supported |
| Icelandic | `is-IS` | Experimental | Ukrainian | `uk-UA` | Supported |
| Indonesian | `id-ID` | Experimental | Uzbek | `uz-UZ` | Experimental |
| Italian | `it-IT` | Supported | Vietnamese | `vi-VN` | Supported |

## Regional availability

Gemini 3.5 Transcribe is available in the following Google Cloud locations:

| Endpoint | Google Cloud Location | Launch Readiness |
|---|---|---|
| `gemini-3.5-transcribe` | `global` | Supported |
| `gemini-3.5-transcribe` | `us` | Supported |
| `gemini-3.5-transcribe` | `eu` | Supported |
| `gemini-3.5-transcribe-live` | `global` | Supported |
| `gemini-3.5-transcribe-live` | `us` | Supported |
| `gemini-3.5-transcribe-live` | `eu` | Supported |

## Best practices

- **Provide clean audio:** Ensure audio recordings have clear voice separation and avoid severe clipping.
- **Provide language hints when known:** If you know the audio language in advance, specify `language_codes` to maximize accuracy.
- **Target custom vocabulary:** Include only distinct domain terms, brand names, or proper nouns in `custom_vocabulary` rather than common everyday words.
- **Use manual endpointing with `SMART` mode in live transcription:** Disable automatic VAD (`automatic_activity_detection`) and explicitly send `activity_start` and `activity_end` signals so the model can apply disfluency removal, self-corrections, and formatting across complete utterances.


[Try in Agent Studio](https://console.cloud.google.com/agent-platform/studio/multimodal-live?model=gemini-3.5-transcribe-live-preview)


[Pricing](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing)

| Model ID | `['gemini-3.5-transcribe', 'gemini-3.5-transcribe-live']` ||
| Modalities | Text Output only Image Not supported Audio Input only Video Not supported ||
| Capabilities | - [Thinking](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/thinking) Not supported - [System instructions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/prompts/system-instruction-introduction) Not supported - [Interactions API](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/interactions) Preview feature Not supported - [Gemini Live API](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/live-api) Supported - [Structured output](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/control-generated-output) Not supported - [Context caching](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/context-cache/context-cache-overview) Not supported - [Count Tokens](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/get-token-count) Not supported - [RAG Engine](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/rag-engine/rag-overview) Not supported - [Chat completions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/migrate/openai/overview) Not supported - [Tuning](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/tune-models) Not supported - [URL context](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/url-context) Not supported - [Agentic video understanding](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/video-understanding#agentic-video-processing) Preview feature Not supported ||
| Tools | - [Grounding](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/grounding/overview) Not supported - [Code execution](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/tools/code-execution) Not supported - [Function calling](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/tools/function-calling) Not supported - [Computer use](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/computer-use) Preview feature Not supported ||
| Consumption options | - [Provisioned Throughput](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/provisioned-throughput) Not supported - [Batch inference](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/batch-inference) Not supported - [Pay-as-you-go](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/deploy/consumption-options) Standard PayGo Supported - [Fixed quota](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/quotas) Not supported ||
| Supported regions | **[Model availability](https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/locations)** | - Global: `global` |
| Supported regions |
|---|---|---|
| **[ML processing](https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/data-residency)** | - United States: `Multi-region` - Europe: `Multi-region` |
