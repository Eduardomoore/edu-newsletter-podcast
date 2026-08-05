"""
assemble_audio.py

Stitches generated TTS chunks (in manifest order) together with intro/outro
bumpers into a single final episode MP3. Adds a short silence between
chapters for natural pacing.
"""

import os
import sys
import yaml
from pydub import AudioSegment


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def assemble(manifest_path: str, cfg: dict, episode_name: str):
    audio_dir = os.path.dirname(manifest_path)

    with open(manifest_path, "r", encoding="utf-8") as f:
        chunk_paths = [line.strip() for line in f if line.strip()]

    silence = AudioSegment.silent(duration=600)  # 0.6s between chunks
    episode = AudioSegment.empty()

    intro_path = cfg["podcast"].get("intro_asset")
    if intro_path and os.path.exists(intro_path):
        episode += AudioSegment.from_file(intro_path)
        episode += AudioSegment.silent(duration=800)

    for path in chunk_paths:
        episode += AudioSegment.from_file(path)
        episode += silence

    outro_path = cfg["podcast"].get("outro_asset")
    if outro_path and os.path.exists(outro_path):
        episode += AudioSegment.silent(duration=400)
        episode += AudioSegment.from_file(outro_path)

    output_dir = cfg["podcast"].get("output_dir", "output")
    os.makedirs(output_dir, exist_ok=True)
    final_path = os.path.join(output_dir, f"{episode_name}.mp3")

    episode.export(final_path, format="mp3", bitrate="192k")
    print(f"Final episode assembled: {final_path}")
    return final_path


def main():
    if len(sys.argv) < 3:
        print("Usage: python assemble_audio.py <manifest.txt> <episode_name> [config.yaml]")
        sys.exit(1)

    manifest_path, episode_name = sys.argv[1], sys.argv[2]
    config_path = sys.argv[3] if len(sys.argv) > 3 else "config.yaml"

    cfg = load_config(config_path)
    assemble(manifest_path, cfg, episode_name)


if __name__ == "__main__":
    main()
