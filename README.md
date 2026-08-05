# Edu's Newsletter Podcast — Automated Pipeline

Turns Edu's Newsletter LatAm fintech reports into a weekly narrated podcast episode,
using Claude (Anthropic API) for script cleanup and ElevenLabs (Professional Voice
Clone) for narration in Edu's own voice.

## How it works

1. Drop a new report (`.md` or `.txt`) into `content/source_reports/`.
2. `src/pipeline.py` picks up the newest unprocessed report.
3. **Claude API** rewrites the written report into a natural spoken script, chaptered,
   with visual-only content (tables, screenshots) converted into spoken summaries.
4. **ElevenLabs API** narrates each chapter in Edu's cloned voice.
5. Chapters are stitched together with intro/outro bumpers into one final MP3.
6. On GitHub Actions, this runs automatically every Monday and commits the new
   episode back to the repo.

## Local setup (run once)

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

You'll also need `ffmpeg` installed locally (required by `pydub` for audio assembly):
- Mac: `brew install ffmpeg`
- Windows: download from ffmpeg.org and add to PATH

## Environment variables (local run)

Set these in your terminal session (do NOT commit them to any file):

```bash
export ANTHROPIC_API_KEY="your-anthropic-key"
export ELEVENLABS_API_KEY="your-elevenlabs-key"
```

On Windows (PowerShell):
```powershell
$env:ANTHROPIC_API_KEY="your-anthropic-key"
$env:ELEVENLABS_API_KEY="your-elevenlabs-key"
```

## Running the full pipeline locally

```bash
python src/pipeline.py
```

This will:
- Find the newest unprocessed file in `content/source_reports/`
- Write a cleaned script to `content/generated_scripts/`
- Generate narrated audio chunks to `output/chunks/<episode_name>/`
- Assemble the final episode to `output/<episode_name>.mp3`
- Mark the source report as processed (won't be re-run next time)

## Running steps individually (useful for testing)

```bash
# Just the script cleanup (Claude)
python src/script_cleanup.py content/source_reports/latam_fintech_h1_2026.md content/generated_scripts/episode_test.md

# Just the TTS generation (ElevenLabs) — requires a script file
python src/tts_generate.py content/generated_scripts/episode_test.md output/chunks/episode_test

# Just the final assembly
python src/assemble_audio.py output/chunks/episode_test/manifest.txt episode_test
```

## GitHub Actions setup (for real weekly automation)

1. Push this repo to GitHub.
2. Go to **Settings → Secrets and variables → Actions → New repository secret**.
3. Add two secrets:
   - `ANTHROPIC_API_KEY`
   - `ELEVENLABS_API_KEY`
4. The workflow in `.github/workflows/weekly_podcast.yml` runs automatically every
   Monday at 09:00 UTC, or can be triggered manually from the **Actions** tab
   ("Run workflow" button).
5. Each run picks up any new file dropped into `content/source_reports/`, generates
   the episode, and commits the result back to the repo automatically.

## Config

All tunable settings (voice ID, model, chunk size, intro/outro paths) live in
`config.yaml`.

## Adding intro/outro bumpers

Drop `intro.mp3` and `outro.mp3` into `assets/` — `assemble_audio.py` will
automatically include them if present, or skip gracefully if not.

---

Built by Eduardo Moore as part of exploring agentic content pipelines with the
ElevenLabs API.
