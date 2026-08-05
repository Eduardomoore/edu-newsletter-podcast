"""
tts_generate.py

Takes a chaptered podcast script and generates narrated audio for each
chapter using the ElevenLabs Text-to-Speech API, in the user's cloned voice.

Chapters are split on "## Chapter:" headers (produced by script_cleanup.py).
Long chapters are further split into safe request-size chunks.
"""

import os
import re
import sys
import time
import yaml
import requests


ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def split_into_chapters(script_text: str):
    """Split script into (title, body) tuples based on '## Chapter:' headers."""
    pattern = re.compile(r"^##\s*Chapter:\s*(.+)$", re.MULTILINE)
    matches = list(pattern.finditer(script_text))

    if not matches:
        return [("Full Episode", script_text.strip())]

    chapters = []
    for i, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(script_text)
        body = script_text[start:end].strip()
        if body:
            chapters.append((title, body))
    return chapters


def chunk_text(text: str, limit: int):
    """Split text into chunks under `limit` characters, breaking on sentence ends."""
    if len(text) <= limit:
        return [text]

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, current = [], ""
    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= limit:
            current = f"{current} {sentence}".strip()
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


def generate_audio_chunk(text: str, api_key: str, cfg: dict, out_path: str, retries: int = 3):
    url = ELEVENLABS_TTS_URL.format(voice_id=cfg["elevenlabs"]["voice_id"])
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": cfg["elevenlabs"]["model_id"],
        "voice_settings": {
            "stability": cfg["elevenlabs"]["stability"],
            "similarity_boost": cfg["elevenlabs"]["similarity_boost"],
            "style": cfg["elevenlabs"].get("style", 0.0),
            "use_speaker_boost": cfg["elevenlabs"].get("use_speaker_boost", True),
        },
    }

    for attempt in range(1, retries + 1):
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        if response.status_code == 200:
            with open(out_path, "wb") as f:
                f.write(response.content)
            return
        print(f"  Attempt {attempt} failed ({response.status_code}): {response.text[:200]}")
        time.sleep(2 * attempt)

    raise RuntimeError(f"Failed to generate audio for chunk after {retries} attempts")


def main():
    if len(sys.argv) < 3:
        print("Usage: python tts_generate.py <script.md> <output_dir> [config.yaml]")
        sys.exit(1)

    script_path, output_dir = sys.argv[1], sys.argv[2]
    config_path = sys.argv[3] if len(sys.argv) > 3 else "config.yaml"

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        print("ERROR: ELEVENLABS_API_KEY environment variable not set.")
        sys.exit(1)

    cfg = load_config(config_path)
    os.makedirs(output_dir, exist_ok=True)

    with open(script_path, "r", encoding="utf-8") as f:
        script_text = f.read()

    chapters = split_into_chapters(script_text)
    limit = cfg["elevenlabs"].get("chunk_char_limit", 2500)

    manifest = []
    for chap_idx, (title, body) in enumerate(chapters, start=1):
        chunks = chunk_text(body, limit)
        for chunk_idx, chunk in enumerate(chunks, start=1):
            filename = f"chap{chap_idx:02d}_{chunk_idx:02d}.mp3"
            out_path = os.path.join(output_dir, filename)
            print(f"Generating: Chapter {chap_idx} ('{title}') chunk {chunk_idx}/{len(chunks)}")
            generate_audio_chunk(chunk, api_key, cfg, out_path)
            manifest.append(out_path)

    manifest_path = os.path.join(output_dir, "manifest.txt")
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write("\n".join(manifest))

    print(f"Done. {len(manifest)} audio chunks generated. Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
