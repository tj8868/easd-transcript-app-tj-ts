"""
Reusable fixtures for Whisper hallucination / sanitizer tests.

Each entry is a real-world-shaped Whisper output. When a new hallucinated script or
pattern shows up in app_service.log, add a sample here (and, if it is a new script,
a row to local_whisper_engine._HALLUCINATION_SCRIPTS) - every test that imports these
fixtures picks it up automatically.

Fields:
    name      short id used in test output
    text      raw segment text as Whisper produced it
    language  target language passed to sanitize_whisper_text()
    expect    "empty"      -> the whole segment must be dropped
              "keep"       -> text must come back unchanged
              ("contains", s)  -> result must contain s
              ("absent", s)    -> result must NOT contain s
"""

# Foreign-script garbage observed interleaved with English speech on local Whisper
# (small/medium, CPU) - these must be stripped when the target language is English.
INDIC_HALLUCINATIONS_ON_ENGLISH = [
    {"name": "devanagari_pure", "language": "en",
     "text": "आज की बैठक में हम बजट पर चर्चा करेंगे", "expect": "empty"},
    {"name": "devanagari_mixed_with_english", "language": "en",
     "text": "We reviewed the budget. आज की बैठक में", "expect": ("absent", "बैठक")},
    {"name": "telugu_pure", "language": "en",
     "text": "ఈ సమావేశంలో మేము బడ్జెట్ గురించి మాట్లాడాము", "expect": "empty"},
    {"name": "kannada_pure", "language": "en",
     "text": "ಈ ಸಭೆಯಲ್ಲಿ ನಾವು ಬಜೆಟ್ ಬಗ್ಗೆ ಚರ್ಚಿಸಿದೆವು", "expect": "empty"},
    {"name": "telugu_kannada_mixed_mostly_garbage", "language": "en",
     "text": "ok ఈ సమావేశం ಸಭೆಯಲ್ಲಿ ನಾವು", "expect": "empty"},
    {"name": "tamil_pure", "language": "en",
     "text": "இந்த கூட்டத்தில் நாங்கள் பேசினோம்", "expect": "empty"},
    {"name": "malayalam_pure", "language": "en",
     "text": "ഈ യോഗത്തിൽ ഞങ്ങൾ ചർച്ച ചെയ്തു", "expect": "empty"},
    {"name": "gujarati_pure", "language": "en",
     "text": "આ બેઠકમાં અમે ચર્ચા કરી", "expect": "empty"},
    {"name": "gurmukhi_pure", "language": "en",
     "text": "ਇਸ ਮੀਟਿੰਗ ਵਿੱਚ ਅਸੀਂ ਚਰਚਾ ਕੀਤੀ", "expect": "empty"},
]

# Foreign-script garbage inside a Bangla segment must go, Bangla must stay.
INDIC_HALLUCINATIONS_ON_BANGLA = [
    {"name": "bangla_with_devanagari_tail", "language": "bn",
     "text": "আজকের সভায় বাজেট নিয়ে আলোচনা হয়েছে। नमस्ते",
     "expect": ("contains", "আজকের সভায় বাজেট নিয়ে আলোচনা হয়েছে।")},
    {"name": "bangla_with_telugu_tail", "language": "bn",
     "text": "আজকের সভায় বাজেট নিয়ে আলোচনা হয়েছে। ఈ",
     "expect": ("absent", "ఈ")},
]

# Genuine speech that must survive untouched (guards against over-stripping).
MUST_KEEP = [
    {"name": "english_sentence", "language": "en",
     "text": "We reviewed the quarterly action items and project milestones.", "expect": "keep"},
    {"name": "bangla_sentence_with_danda", "language": "bn",
     "text": "ড. শামীম তালুকদার আজকের মিটিং পরিচালনা করবেন।", "expect": "keep"},
    {"name": "bangla_in_english_chunk_code_switch", "language": "en",
     "text": "The budget ঠিক আছে, let's move on.", "expect": "keep"},
    {"name": "hindi_when_target_is_hindi", "language": "hi",
     "text": "आज की बैठक में हम बजट पर चर्चा करेंगे", "expect": "keep"},
    {"name": "telugu_when_target_is_telugu", "language": "te",
     "text": "ఈ సమావేశంలో మేము బడ్జెట్ గురించి మాట్లాడాము", "expect": "keep"},
]

ALL_SANITIZER_CASES = INDIC_HALLUCINATIONS_ON_ENGLISH + INDIC_HALLUCINATIONS_ON_BANGLA + MUST_KEEP


def check_sanitizer_case(sanitize, case):
    """Runs one fixture through ``sanitize(text, language=...)``. Returns (ok, result)."""
    out = sanitize(case["text"], language=case["language"])
    exp = case["expect"]
    if exp == "empty":
        return out == "", out
    if exp == "keep":
        return out == case["text"], out
    kind, needle = exp
    if kind == "contains":
        return needle in out, out
    if kind == "absent":
        return needle not in out and out != "", out
    raise ValueError(f"unknown expectation {exp!r}")


# Whisper language-detector probability distributions (model.detect_language output)
# observed / reconstructed for the misdetection bug. Used to test language resolution.
DETECTOR_DISTRIBUTIONS = [
    # Pure English speech with a noisy background: Bengali only ~12% -> v8.3 forced "bn".
    {"name": "english_noisy_bn_12pct", "expect": "en", "expect_ambiguous": False,
     "probs": [("en", 0.71), ("bn", 0.12), ("hi", 0.06), ("te", 0.03), ("kn", 0.02), ("ta", 0.02)]},
    # English with Hindi on top-2 and Bengali at 6% -> v8.3 forced "bn" via the hi+5% rule.
    {"name": "english_hi_second", "expect": "en", "expect_ambiguous": False,
     "probs": [("en", 0.80), ("hi", 0.09), ("bn", 0.06), ("ur", 0.02)]},
    # Genuine Bangla that Whisper ranks as Hindi with Bengali close behind -> bn.
    {"name": "bangla_misranked_as_hindi", "expect": "bn", "expect_ambiguous": False,
     "probs": [("hi", 0.41), ("bn", 0.37), ("ne", 0.08), ("en", 0.05)]},
    # Hindi top with Bengali far behind -> stays hi (no low-floor override).
    {"name": "hindi_clear", "expect": "hi", "expect_ambiguous": False,
     "probs": [("hi", 0.78), ("bn", 0.11), ("ur", 0.05), ("en", 0.03)]},
    # Clear Bangla.
    {"name": "bangla_clear", "expect": "bn", "expect_ambiguous": False,
     "probs": [("bn", 0.88), ("as", 0.04), ("hi", 0.03), ("en", 0.02)]},
    # Code-switched Bangla/English chunk -> bn with en as the second candidate.
    {"name": "code_switched_bn_en", "expect": "bn", "expect_ambiguous": True,
     "probs": [("bn", 0.52), ("en", 0.38), ("hi", 0.05)]},
]
