"""
pipeline.py

Orchestrates the full weekly pipeline:
  1. Pick the newest report in content/source_reports/ that hasn't been processed
  2. Clean it into a spoken script (Claude API)
  3. Generate narrated audio per chapter (ElevenLabs API, cloned voice)
  4. Assemble into a final episode MP3 with intro/outro (and About Me, if active)

Designed to be run manually or via the weekly GitHub Actions workflow.
"""

import os
import sys
import glob
import datetime
import yaml

sys.path.insert(0, os.path.dirname(__file__))

from script_cleanup import clean_report_to_script  # noqa: E402
from tts_generate import load_config as load_tts_config, split_into_chapters, chunk_text, generate_audio_chunk  # noqa: E402
from assemble_audio import assemble  # noqa: E402


PROCESSED_LOG = "content/source_reports/.processed.txt"


def get_processed_set():
    if not os.path.exists(PROCESSED_LOG):
        return set()
    with open(PROCESSED_LOG, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def mark_processed(filename: str):
    with open(PROCESSED_LOG, "a", encoding="utf-8") as f:
        f.write(filename + "\n")


def find_next_report(source_dir: str):
    processed = get_processed_set()
    candidates = sorted(
        glob.glob(os.path.join(source_dir, "*.md")) + glob.glob(os.path.join(source_dir, "*.txt"))
    )
    for path in candidates:
        if os.path.basename(path) not in processed:
            return path
    return None


def main():
    config_path = "config.yaml"
    cfg = load_tts_config(config_path)

    source_dir = cfg["paths"]["source_dir"]
    report_path = find_next_report(source_dir)

    if not report_path:
        print("No new reports to process. Add a .md/.txt file to content/source_reports/.")
        return

    print(f"Processing report: {report_path}")

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY")
    if not anthropic_key or not elevenlabs_key:
        print("ERROR: ANTHROPIC_API_KEY and ELEVENLABS_API_KEY must both be set.")
        sys.exit(1)

    with open(report_path, "r", encoding="utf-8") as f:
        report_text = f.read()

    # Step 1: clean into spoken script
    print("Step 1/3: Cleaning report into spoken script...")
    script = clean_report_to_script(
        report_text,
        api_key=anthropic_key,
        model=cfg["anthropic"]["model"],
        max_tokens=cfg["anthropic"]["max_tokens"],
    )

    date_tag = datetime.date.today().isoformat()
    episode_name = f"episode_{date_tag}"
    scripts_dir = "content/generated_scripts"
    os.makedirs(scripts_dir, exist_ok=True)
    script_path = os.path.join(scripts_dir, f"{episode_name}.md")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)
    print(f"  Script saved: {script_path}")

    # Step 2: generate TTS chunks
    print("Step 2/3: Generating narrated audio (ElevenLabs)...")
    audio_chunks_dir = os.path.join("output", "chunks", episode_name)
    os.makedirs(audio_chunks_dir, exist_ok=True)

    chapters = split_into_chapters(script)
    limit = cfg["elevenlabs"].get("chunk_char_limit", 2500)
    manifest = []
    for chap_idx, (title, body) in enumerate(chapters, start=1):
        for chunk_idx, chunk in enumerate(chunk_text(body, limit), start=1):
            filename = f"chap{chap_idx:02d}_{chunk_idx:02d}.mp3"
            out_path = os.path.join(audio_chunks_dir, filename)
            print(f"  Chapter {chap_idx} ('{title}') chunk {chunk_idx}...")
            generate_audio_chunk(chunk, elevenlabs_key, cfg, out_path)
            manifest.append(out_path)

    manifest_path = os.path.join(audio_chunks_dir, "manifest.txt")
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write("\n".join(manifest))

    # Step 3: assemble final episode
    print("Step 3/3: Assembling final episode...")
    final_path = assemble(manifest_path, cfg, episode_name)

    # Decrement the About Me segment counter, if active
    remaining = cfg["podcast"].get("about_me_episodes_remaining", 0)
    if remaining > 0:
        cfg["podcast"]["about_me_episodes_remaining"] = remaining - 1
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f, default_flow_style=False, sort_keys=False)
        print(f"About Me segment countdown updated: {remaining - 1} episode(s) remaining.")

    mark_processed(os.path.basename(report_path))
    print(f"\nDone! Episode ready: {final_path}")


if __name__ == "__main__":
    main()