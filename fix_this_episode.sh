#!/usr/bin/env bash
# One-time patch for episode_2026-08-13, which was generated before the
# Welcome opener / About Me intro feature existed. Re-running the full
# pipeline would re-narrate every chapter (cost + time for no benefit, since
# that audio already sounds right). This script instead:
#   1. Prepends a "## Welcome" section to the already-generated script
#   2. Runs tts_generate.py, which now SKIPS any chap*.mp3 that already
#      exists on disk, and only narrates what's new: welcome.mp3, plus the
#      About Me intro line (narrated once, reused every future episode)
#   3. Re-assembles the final MP3 with everything in the right order
#
# For every episode from now on, this step isn't needed at all -- run_episode.sh
# / pipeline.py will include the Welcome section automatically, since it's now
# baked into script_cleanup.py's instructions to Claude.
#
# BEFORE RUNNING: copy config.yaml, src/tts_generate.py, src/pipeline.py,
# src/assemble_audio.py, and src/script_cleanup.py into place first (all five
# from this batch), overwriting the existing files at those paths.

set -euo pipefail

if [ ! -f "config.yaml" ] || [ ! -d "src" ]; then
  echo "Run this from the root of your edu-newsletter-podcast clone." >&2
  exit 1
fi

: "${ELEVENLABS_API_KEY:?Set it first: export ELEVENLABS_API_KEY=...}"

SCRIPT_PATH="content/generated_scripts/episode_2026-08-13.md"
if [ ! -f "$SCRIPT_PATH" ]; then
  echo "Can't find $SCRIPT_PATH -- adjust the date in this script if your episode used a different name." >&2
  exit 1
fi

# 1. Prepend the Welcome section (idempotent -- safe to run more than once)
python3 - "$SCRIPT_PATH" << 'PYEOF'
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

welcome = """## Welcome
Welcome to Edu's Podcast. In today's edition: Brazil just tightened the rules on stablecoins, and volume grew right through it anyway. We'll get into why trade settlement and dollarization are quietly carrying the real growth, what Resolution 561 actually closes versus what it leaves alone, and why Wall Street, Circle, BNY, Samsung, is racing to build the exact same rails Brazil just started regulating.

"""

if content.lstrip().startswith("## Welcome"):
    print("Welcome section already present -- leaving the script as-is.")
else:
    with open(path, "w", encoding="utf-8") as f:
        f.write(welcome + content)
    print(f"Prepended Welcome section to {path}")
PYEOF

# 2. Re-run TTS generation. Existing chap*.mp3 files are skipped; only
#    welcome.mp3 and (first time only) assets/about_me_intro.mp3 get narrated.
python src/tts_generate.py "$SCRIPT_PATH" output/chunks/episode_2026-08-13

# 3. Re-assemble the episode with the new segments in place
python src/assemble_audio.py output/chunks/episode_2026-08-13/manifest.txt episode_2026-08-13

echo ""
echo "Updated episode: output/episode_2026-08-13.mp3"
echo "Give it a listen, then commit + push:"
echo ""
echo "  git add config.yaml src/tts_generate.py src/pipeline.py src/assemble_audio.py src/script_cleanup.py \\"
echo "          content/generated_scripts/episode_2026-08-13.md \\"
echo "          assets/about_me_intro.mp3 \\"
echo "          output/episode_2026-08-13.mp3 output/chunks/episode_2026-08-13"
echo "  git commit -m 'Add Welcome opener and About Me intro line to pipeline'"
echo "  git push"
