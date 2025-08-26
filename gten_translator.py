#!/usr/bin/env python3
"""
GTEN Translator — Proprietary (GTEN Technologies)
File: gten_translator.py
Purpose: Spanish -> English aligned TTS + SRT with proprietary license enforcement.
Author: Subir Sutradhar (Senior Operations Engineer)
"""

import os
import sys
import time
import shutil
import tempfile
from datetime import datetime
from colorama import Fore, Style, init

# Third-party libraries (install via pip if missing)
# pip install -U openai-whisper gTTS pydub colorama pyfiglet
try:
    import whisper
    from gtts import gTTS
    from pydub import AudioSegment
    from pyfiglet import Figlet
except Exception as e:
    print("Missing dependency: " + str(e))
    print("Install required packages: pip install -U openai-whisper gTTS pydub colorama pyfiglet")
    sys.exit(1)

init(autoreset=True)

# ----------------------------
# Strict Proprietary License
# ----------------------------
GTEN_PROPRIETARY_LICENSE = f"""GTEN Technologies — Proprietary License
Copyright (c) {datetime.now().year} GTEN Technologies. All Rights Reserved.

This software (the "Software"), including all source code, documentation,
examples, and associated files, is the confidential and proprietary property
of GTEN Technologies (the "Company").

PERMITTED USE:
  - The Software may be used internally by authorized employees or contractors
    of GTEN Technologies, subject to any internal policies and agreements.

PROHIBITED ACTIONS (without express prior written permission from GTEN Technologies):
  - Copying, reproducing, sublicensing, distributing, or making the Software
    available to any third party.
  - Publishing, uploading, or otherwise making public any portion of the
    Software or its outputs (including derived works) outside GTEN Technologies.
  - Modifying, merging, reverse-engineering, decompiling, or creating derivative
    works for external distribution.
  - Use for commercial, academic, or public services outside explicit Company
    approval.

DISCLAIMER:
  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
  IMPLIED. THE COMPANY SHALL NOT BE LIABLE FOR ANY DAMAGES ARISING FROM THE USE
  OR INABILITY TO USE THE SOFTWARE. UNAUTHORIZED USE OR DISTRIBUTION MAY RESULT
  IN CIVIL OR CRIMINAL LIABILITY.

If you are not an authorized representative of GTEN Technologies, stop now and
notify the software owner. All rights reserved.
"""

def write_license_file():
    """Write proprietary license to LICENSE (overwrites existing)."""
    with open("LICENSE", "w", encoding="utf-8") as f:
        f.write(GTEN_PROPRIETARY_LICENSE)
    print(Fore.GREEN + "✔ LICENSE written to ./LICENSE")

def show_license_on_console():
    """Print license in console."""
    print(Fore.MAGENTA + Style.BRIGHT + "\n=== GTEN Proprietary License ===\n")
    print(Fore.WHITE + GTEN_PROPRIETARY_LICENSE)
    print(Fore.MAGENTA + Style.BRIGHT + "=== End License ===\n")

# ----------------------------
# UI 
# ----------------------------
def banner():
    """Show GTEN Translator banner"""
    f = Figlet(font="slant")
    print(Fore.RED + Style.BRIGHT + f.renderText("GTEN Translator"))
    print(Fore.CYAN + Style.BRIGHT + "Author: Subir Sutradhar | Version 1.0 | Spanish → English\n")

# ----------------------------
# Utility checks
# ----------------------------
def check_ffmpeg():
    if shutil.which("ffmpeg") is None:
        print(Fore.RED + "FFmpeg not found on PATH. pydub requires ffmpeg.")
        print("Install FFmpeg and ensure it's available in your PATH.")
        sys.exit(1)

def safe_remove(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

# ----------------------------
# Time formatting helper for SRT
# ----------------------------
def ms_to_srt_timestamp(ms: int) -> str:
    hours = ms // 3600000
    minutes = (ms % 3600000) // 60000
    seconds = (ms % 60000) // 1000
    milliseconds = ms % 1000
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

# ----------------------------
# Core translation function
# ----------------------------
def spanish_to_english_aligned_with_subs():
    check_ffmpeg()

    input_mp3 = input("🎵 Enter the path to your Spanish MP3 file: ").strip().strip('"').strip("'")
    if not input_mp3:
        print(Fore.RED + "No input path provided. Exiting.")
        return
    if not os.path.isfile(input_mp3):
        print(Fore.RED + f"File not found: {input_mp3}")
        return

    output_mp3 = "english_aligned_output.mp3"
    output_srt = "english_subtitles.srt"

    print(Fore.YELLOW + "🔄 Loading Whisper model (medium). This may take a while...")
    model = whisper.load_model("medium")

    try:
        print(Fore.YELLOW + "🎙️ Transcribing + translating (Whisper) ...")
        result = model.transcribe(input_mp3, language="es", task="translate", verbose=False)
    except Exception as e:
        print(Fore.RED + "Whisper transcription failed: " + str(e))
        return

    try:
        original_audio = AudioSegment.from_file(input_mp3)
    except Exception as e:
        print(Fore.RED + "Failed to load input audio: " + str(e))
        return

    # Create silent track same length as original
    final_audio = AudioSegment.silent(duration=len(original_audio))

    srt_lines = []
    temp_dir = tempfile.mkdtemp(prefix="gten_tts_")
    created_temp_files = []

    print(Fore.GREEN + f"Transcription produced {len(result.get('segments', []))} segments (approx).")

    try:
        for i, seg in enumerate(result.get("segments", [])):
            start_ms = int(seg.get("start", 0) * 1000)
            end_ms = int(seg.get("end", 0) * 1000)
            english_text = seg.get("text", "").strip()
            if not english_text:
                continue

            print(Fore.CYAN + f"[Segment {i+1}] {seg.get('start'):.2f}s - {seg.get('end'):.2f}s -> {english_text}")

            # Generate TTS with gTTS
            segment_file = os.path.join(temp_dir, f"segment_{i}.mp3")
            try:
                tts = gTTS(text=english_text, lang="en")
                tts.save(segment_file)
                created_temp_files.append(segment_file)
            except Exception as e:
                print(Fore.RED + f"gTTS failed for segment {i}: {e}. Skipping.")
                continue

            try:
                seg_audio = AudioSegment.from_file(segment_file)
            except Exception as e:
                print(Fore.RED + f"Failed to load generated TTS segment {segment_file}: {e}")
                continue

            # Align segment duration
            target_duration = max(1, end_ms - start_ms)
            if len(seg_audio) > target_duration:
                seg_audio = seg_audio[:target_duration]
            elif len(seg_audio) < target_duration:
                seg_audio += AudioSegment.silent(duration=(target_duration - len(seg_audio)))

            # Overlay onto final_audio at correct position
            final_audio = final_audio.overlay(seg_audio, position=start_ms)

            # Add SRT entry
            start_srt = ms_to_srt_timestamp(start_ms)
            end_srt = ms_to_srt_timestamp(end_ms)
            srt_lines.append(f"{len(srt_lines)+1}\n{start_srt} --> {end_srt}\n{english_text}\n")

        # Export results
        print(Fore.YELLOW + f"Exporting final aligned English audio to: {output_mp3}")
        final_audio.export(output_mp3, format="mp3")

        print(Fore.YELLOW + f"Writing subtitles to: {output_srt}")
        with open(output_srt, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_lines))

        print(Fore.GREEN + f"\n✅ Done! Saved audio: {output_mp3}")
        print(Fore.GREEN + f"✅ Subtitles: {output_srt}")

    finally:
        # Cleanup
        for p in created_temp_files:
            safe_remove(p)
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass

# ----------------------------
# Main entry
# ----------------------------
def main():
    banner()
    write_license_file()
    show_license_on_console()

    print(Fore.YELLOW + "To continue, you must confirm you are authorized to run this GTEN proprietary software.")
    answer = input("Type 'I AGREE' to continue (case-sensitive): ").strip()
    if answer != "I AGREE":
        print(Fore.RED + "Authorization not provided. Exiting.")
        sys.exit(1)

    spanish_to_english_aligned_with_subs()

if __name__ == "__main__":
    main()

# Cheers
