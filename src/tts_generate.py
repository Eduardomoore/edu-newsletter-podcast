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


def extract_welcome(script_text: str):
    """Pull an optional leading '## Welcome' section out of the script.

    script_cleanup.py writes this section when present -- a short, per-episode
    "Welcome to Edu's Podcast, in today's edition..." line that previews what
    the episode covers. It has to be regenerated every episode (unlike the
    other bumpers) because its content depends on the article. Returns
    (welcome_text_or_None, script_text_with_welcome_section_removed).
    """
    pattern = re.compile(r"^##\s*Welcome\s*$", re.MULTILINE)
    match = pattern.search(script_text)
    if not match:
        return None, script_text

    rest = script_text[match.end():]
    next_header = re.search(r"^##\s", rest, re.MULTILINE)
    if next_header:
        welcome_text = rest[:next_header.start()].strip()
        remaining = script_text[:match.start()] + rest[next_header.start():]
    else:
        welcome_text = rest.strip()
        remaining = script_text[:match.start()]
    return (welcome_text or None), remaining


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


def generate_audio_chunk(text: str, api_key: str, cfg: dict, out_path: str, retries: int = 3,
                          previous_text: str = None, next_text: str = None):
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
        # Text normalization "on" (vs "auto") makes ElevenLabs apply its
        # normalizer deterministically instead of deciding per-request whether
        # to run it -- one source of the "sometimes" behavior you're seeing.
        "apply_text_normalization": cfg["elevenlabs"].get("apply_text_normalization", "on"),
    }

    # Request Stitching: tells the model what came immediately before/after
    # this chunk so it doesn't have to guess the prosody at the seam. This is
    # the main fix for periods occasionally landing as comma-length pauses --
    # without it, every chunk is synthesized as if it were a standalone
    # sentence with no sense of where it sits in the paragraph.
    if previous_text:
        payload["previous_text"] = previous_text[-500:]
    if next_text:
        payload["next_text"] = next_text[:500]

    # Optional: pin a seed so that once a take sounds right, re-running the
    # same chunk (e.g. to fix one bad line) reproduces it rather than
    # re-rolling the dice. ElevenLabs notes this is "best effort," not a hard
    # guarantee, but it noticeably cuts down on run-to-run variance.
    seed = cfg["elevenlabs"].get("seed")
    if seed is not None:
        payload["seed"] = seed

    for attempt in range(1, retries + 1):
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        if response.status_code == 200:
            with open(out_path, "wb") as f:
                f.write(response.content)
            return
        print(f"  Attempt {attempt} failed ({response.status_code}): {response.text[:200]}")
        time.sleep(2 * attempt)

    raise RuntimeError(f"Failed to generate audio for chunk after {retries} attempts")


def ensure_static_asset(text: str, api_key: str, cfg: dict, out_path: str):
    """Generate a one-off narration line only if it doesn't already exist.

    Used for recurring bumper lines (like the About Me intro) that stay the
    same every episode -- so they get narrated once and reused, instead of
    re-billing ElevenLabs for the same ten words every week.
    """
    if os.path.exists(out_path):
        print(f"Static asset already exists, skipping: {out_path}")
        return
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    print(f"Generating static asset (first time only): {out_path}")
    generate_audio_chunk(text, api_key, cfg, out_path)


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

    # Per-episode welcome/summary line, if script_cleanup.py generated one
    welcome_text, script_text = extract_welcome(script_text)
    if welcome_text:
        welcome_path = os.path.join(output_dir, "welcome.mp3")
        print("Generating: Welcome / episode summary")
        generate_audio_chunk(welcome_text, api_key, cfg, welcome_path, next_text=script_text[:500])

    # Recurring "before we get into it, a word about who's talking to you"
    # line -- narrated once, then reused every episode. Edit the wording in
    # config.yaml's podcast.about_me_intro_text; delete the cached mp3 at
    # podcast.about_me_intro_asset to force a re-narration.
    about_me_intro_text = cfg.get("podcast", {}).get("about_me_intro_text")
    about_me_intro_path = cfg.get("podcast", {}).get("about_me_intro_asset")
    if about_me_intro_text and about_me_intro_path:
        ensure_static_asset(about_me_intro_text, api_key, cfg, about_me_intro_path)

    chapters = split_into_chapters(script_text)
    limit = cfg["elevenlabs"].get("chunk_char_limit", 900)

    # Flatten every chapter's chunks into one ordered list first, so each
    # chunk can be given the real chunk immediately before and after it as
    # previous_text/next_text -- including across chapter boundaries. This is
    # what keeps a period from occasionally reading as a comma-length pause:
    # each request now knows it isn't the start or end of the world.
    flat = []  # (chap_idx, chunk_idx, title, text)
    for chap_idx, (title, body) in enumerate(chapters, start=1):
        chunks = chunk_text(body, limit)
        for chunk_idx, chunk in enumerate(chunks, start=1):
            flat.append((chap_idx, chunk_idx, title, chunk))

    manifest = []
    for i, (chap_idx, chunk_idx, title, chunk) in enumerate(flat):
        filename = f"chap{chap_idx:02d}_{chunk_idx:02d}.mp3"
        out_path = os.path.join(output_dir, filename)
        if os.path.exists(out_path):
            print(f"Skipping (already generated): {out_path}")
        else:
            prev_text = flat[i - 1][3] if i > 0 else None
            next_text = flat[i + 1][3] if i + 1 < len(flat) else None
            print(f"Generating: Chapter {chap_idx} ('{title}') chunk {chunk_idx}")
            generate_audio_chunk(chunk, api_key, cfg, out_path, previous_text=prev_text, next_text=next_text)
        manifest.append(out_path)

    manifest_path = os.path.join(output_dir, "manifest.txt")
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write("\n".join(manifest))

    print(f"Done. {len(manifest)} audio chunks generated. Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
