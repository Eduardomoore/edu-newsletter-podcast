"""
assemble_audio.py

Stitches generated TTS chunks (in manifest order) together with intro/outro
bumpers into a single final episode MP3.

Play order:
  1. intro bumper
  2. one-time opener (only if one_time_opener_asset is set)
  3. About Me segment (while about_me_episodes_remaining > 0)
  4. chapter audio
  5. spoken outro
  6. outro music
"""

import os
import sys
import yaml
from pydub import AudioSegment


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def assemble(manifest_path: str, cfg: dict, episode_name: str):
    with open(manifest_path, "r", encoding="utf-8") as f:
        chunk_paths = [line.strip() for line in f if line.strip()]

    silence = AudioSegment.silent(duration=600)
    episode = AudioSegment.empty()

    intro_path = cfg["podcast"].get("intro_asset")
    if intro_path and os.path.exists(intro_path):
        episode += AudioSegment.from_file(intro_path)
        episode += AudioSegment.silent(duration=800)

    opener_path = cfg["podcast"].get("one_time_opener_asset")
    if opener_path and os.path.exists(opener_path):
        episode += AudioSegment.from_file(opener_path)
        episode += AudioSegment.silent(duration=800)
        print(f"Included one-time opener: {opener_path}")

    about_me_path = cfg["podcast"].get("about_me_asset")
    about_me_remaining = cfg["podcast"].get("about_me_episodes_remaining", 0)
    if about_me_path and os.path.exists(about_me_path) and about_me_remaining > 0:
        episode += AudioSegment.from_file(about_me_path)
        episode += AudioSegment.silent(duration=800)
        print(f"Included About Me segment ({about_me_remaining - 1} episode(s) remaining after this one)")

    for path in chunk_paths:
        episode += AudioSegment.from_file(path)
        episode += silence

    outro_voice_path = cfg["podcast"].get("outro_voice_asset")
    if outro_voice_path and os.path.exists(outro_voice_path):
        episode += AudioSegment.silent(duration=600)
        episode += AudioSegment.from_file(outro_voice_path)
        print(f"Included spoken outro: {outro_voice_path}")

    outro_path = cfg["podcast"].get("outro_asset")
    if outro_path and os.path.exists(outro_path):
        episode += AudioSegment.silent(duration=600)
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