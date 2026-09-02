import os
import sys
import subprocess
import tempfile
from media_processor import (
    find_ffmpeg_binary,
    process_uploaded_media,
    convert_media_to_speech_audio,
    normalize_audio_chunk_for_stt,
    extract_text_from_docx_bytes,
    parse_subtitle_file
)

def run_tests():
    print("=" * 60)
    print("Testing Universal Media & Format Support (including HEVC & iPhone formats)")
    print("=" * 60)
    
    ffmpeg_bin = find_ffmpeg_binary()
    print(f"FFmpeg binary found: {ffmpeg_bin}")
    assert ffmpeg_bin is not None, "FFmpeg binary must be available!"

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Test 1: Generate and test HEVC / H.265 video
        print("\n--- Test 1: HEVC / H.265 Video Audio Extraction ---")
        hevc_path = os.path.join(tmp_dir, "meeting_sample_hevc.mp4")
        cmd_hevc = [
            ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=24",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
            "-c:v", "libx265",
            "-c:a", "aac",
            hevc_path
        ]
        subprocess.run(cmd_hevc, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        with open(hevc_path, "rb") as f:
            hevc_bytes = f.read()
            
        res_hevc = process_uploaded_media(hevc_bytes, "sample_meeting_h265.hevc", "video/mp4")
        print(f"HEVC Detected Format: {res_hevc['format_detected']}")
        print(f"HEVC Result Type: {res_hevc['type']}")
        print(f"HEVC Audio MIME: {res_hevc['mime_type']}")
        print(f"Extracted Audio Size: {len(res_hevc['audio_bytes'])} bytes")
        assert res_hevc["type"] in ["audio_single", "audio_chunks"]
        assert res_hevc["audio_bytes"] is not None and len(res_hevc["audio_bytes"]) > 0
        print("[PASSED] HEVC / H.265 Audio Extraction Passed!")

        # Test 2: Apple QuickTime MOV Video
        print("\n--- Test 2: Apple / iPhone QuickTime MOV Video ---")
        mov_path = os.path.join(tmp_dir, "iphone_meeting.mov")
        cmd_mov = [
            ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=24",
            "-f", "lavfi", "-i", "sine=frequency=600:duration=2",
            "-c:v", "libx264",
            "-c:a", "aac",
            mov_path
        ]
        subprocess.run(cmd_mov, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        with open(mov_path, "rb") as f:
            mov_bytes = f.read()
            
        res_mov = process_uploaded_media(mov_bytes, "IMG_8821.MOV", "video/quicktime")
        print(f"iPhone MOV Detected Format: {res_mov['format_detected']}")
        assert res_mov["audio_bytes"] is not None and len(res_mov["audio_bytes"]) > 0
        print("[PASSED] iPhone MOV Video Passed!")

        # Test 3: Apple iPhone Voice Memos (M4A / AAC)
        print("\n--- Test 3: Apple iPhone Voice Memo (M4A / AAC) ---")
        m4a_path = os.path.join(tmp_dir, "voice_memo.m4a")
        cmd_m4a = [
            ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "sine=frequency=400:duration=2",
            "-c:a", "aac",
            m4a_path
        ]
        subprocess.run(cmd_m4a, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        with open(m4a_path, "rb") as f:
            m4a_bytes = f.read()
            
        res_m4a = process_uploaded_media(m4a_bytes, "Voice_Memo_01.M4A", "audio/x-m4a")
        print(f"iPhone M4A Result: {res_m4a['format_detected']}, size={len(res_m4a['audio_bytes'])} bytes")
        assert len(res_m4a["audio_bytes"]) > 0
        print("[PASSED] iPhone Voice Memo M4A Passed!")

        # Test 4: Apple CAF Audio
        print("\n--- Test 4: Apple CoreAudio CAF ---")
        caf_path = os.path.join(tmp_dir, "meeting_audio.caf")
        cmd_caf = [
            ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "sine=frequency=750:duration=2",
            caf_path
        ]
        subprocess.run(cmd_caf, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        with open(caf_path, "rb") as f:
            caf_bytes = f.read()
            
        res_caf = process_uploaded_media(caf_bytes, "audio_clip.caf", "audio/x-caf")
        print(f"CAF Result: {res_caf['format_detected']}, size={len(res_caf['audio_bytes'])} bytes")
        assert len(res_caf["audio_bytes"]) > 0
        print("[PASSED] Apple CAF Audio Passed!")

        # Test 5: Live Recording Chunk Normalization
        print("\n--- Test 5: Live Recording Audio Chunk Normalization ---")
        norm_bytes, norm_mime = normalize_audio_chunk_for_stt(m4a_bytes, mime_type="audio/mp4")
        print(f"Normalized chunk MIME: {norm_mime}, bytes: {len(norm_bytes) if norm_bytes else 0}")
        assert norm_bytes is not None and len(norm_bytes) > 0
        assert norm_mime == "audio/mp3"
        print("[PASSED] Chunk Normalization for STT Passed!")

        # Test 6: MKV Video Container
        print("\n--- Test 6: MKV Video Container ---")
        mkv_path = os.path.join(tmp_dir, "meeting_sample.mkv")
        cmd_mkv = [
            ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=24",
            "-f", "lavfi", "-i", "sine=frequency=880:duration=2",
            "-c:v", "libx264",
            "-c:a", "libopus",
            mkv_path
        ]
        subprocess.run(cmd_mkv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        with open(mkv_path, "rb") as f:
            mkv_bytes = f.read()
            
        res_mkv = process_uploaded_media(mkv_bytes, "meeting_sample.mkv", "video/x-matroska")
        print(f"MKV Result: {res_mkv['format_detected']}, size={len(res_mkv['audio_bytes'])} bytes")
        assert len(res_mkv["audio_bytes"]) > 0
        print("[PASSED] MKV Container Audio Extraction Passed!")

        # Test 7: Subtitle / Transcript (SRT / VTT)
        print("\n--- Test 7: Subtitle / Caption parsing (SRT / VTT) ---")
        sample_srt = """1
00:00:01,000 --> 00:00:04,000
Welcome to EASD weekly strategic review meeting.

2
00:00:05,000 --> 00:00:09,500
Dr. Shamim discussed non-communicable disease program milestones.
"""
        res_srt = process_uploaded_media(sample_srt.encode("utf-8"), "meeting_captions.srt", "text/plain")
        assert "Welcome to EASD" in res_srt["text"]
        print("[PASSED] Subtitle Parser Passed!")

        # Test 8: DOCX Document
        print("\n--- Test 8: Word Document (DOCX) Text Extraction ---")
        template_file = os.path.join(os.path.dirname(__file__), "EASD Meeting minutes - Template-DDMonthYY.docx")
        if os.path.exists(template_file):
            with open(template_file, "rb") as f:
                docx_bytes = f.read()
            res_docx = process_uploaded_media(docx_bytes, "Template.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            print(f"DOCX Extracted length: {len(res_docx['text'])} chars")
            assert len(res_docx["text"]) > 10
            print("[PASSED] DOCX Document Extraction Passed!")

    print("\n" + "=" * 60)
    print("ALL UNIVERSAL MEDIA FORMAT & RECORDING TESTS PASSED (100%)!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
