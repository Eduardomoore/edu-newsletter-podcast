# Edu's Podcast — Automated Production Pipeline

Turns a written LatAm fintech research report into a finished, narrated podcast
episode. Runs weekly on a schedule with no manual steps.

**Listen:** [Edu's Podcast on Spotify](Shttps://open.spotify.com/episode/1xsat7IJeH4bBh2rY2w2fy?si=cakB_zbGQ1e61EGwMx9D0Q)
**Read:** [Edu's Newsletter on Substack](https://substack.com/@eduardomoore)

Built with the ElevenLabs API (Professional Voice Cloning + text-to-speech) and the
Anthropic API (script adaptation), orchestrated by GitHub Actions.

## What it does

Drop a report into `content/source_reports/`. The pipeline:

1. **Adapts the writing for the ear.** Written reports don't read aloud well — tables,
   footnotes, and long subordinate clauses all break in audio. A Claude API call
   rewrites the report into spoken register, splits it into chapters, and converts
   visual-only content (tables, charts) into spoken summaries.
2. **Narrates it.** Each chapter is chunked to a safe request size and sent to the
   ElevenLabs text-to-speech endpoint using a Professional Voice Clone, with tuned
   stability, similarity and style settings.
3. **Assembles the episode.** Chapter audio is stitched together with branded
   segments into a single MP3.
4. **Commits the result.** On GitHub Actions, the finished episode is pushed back to
   the repo automatically.

## Episode structure

`assemble_audio.py` builds each episode in this order, skipping anything not
configured:

| Segment | Source | When |
|---|---|---|
| Intro bumper | `assets/intro.wav` | Every episode |
| One-time opener | `assets/episode1_opener.mp3` | Only while `one_time_opener_asset` is set |
| About Me | `assets/about_me.mp3` | While `about_me_episodes_remaining > 0` |
| Chapters | generated per run | Every episode |
| Spoken close | `assets/outro_voice.mp3` | Every episode |
| Outro music | `assets/outro.wav` | Every episode |

The About Me counter decrements automatically after each pipeline run, so the
segment retires itself once new listeners have heard it a few times.

## Layout

```
.github/workflows/weekly_podcast.yml   scheduled run (Mondays 09:00 UTC)
src/script_cleanup.py                  report -> spoken script (Claude API)
src/tts_generate.py                    script -> chapter audio (ElevenLabs API)
src/assemble_audio.py                  chapters + segments -> episode MP3
src/pipeline.py                        orchestrates the three steps
assets/                                intro, outro, and recurring voice segments
content/source_reports/                drop new reports here
content/generated_scripts/             adapted scripts, one per episode
output/                                finished episodes
config.yaml                            voice ID, model, segment paths, tuning
```

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

`ffmpeg` is required by `pydub` for audio assembly:

- macOS: `brew install ffmpeg`
- Windows: download from ffmpeg.org and add to PATH

Python 3.13 users also need `pip install audioop-lts` — `audioop` was removed from
the standard library and `pydub` still depends on it.

## Running it

Set both keys in your shell (never commit them):

```bash
export ANTHROPIC_API_KEY="..."
export ELEVENLABS_API_KEY="..."
```

Full pipeline:

```bash
python src/pipeline.py
```

Individual steps, useful when iterating on voice settings without paying for a
fresh script generation:

```bash
python src/script_cleanup.py content/source_reports/REPORT.md content/generated_scripts/OUT.md
python src/tts_generate.py content/generated_scripts/OUT.md output/chunks/OUT
python src/assemble_audio.py output/chunks/OUT/manifest.txt EPISODE_NAME
```

## Weekly automation

Add `ANTHROPIC_API_KEY` and `ELEVENLABS_API_KEY` under
**Settings → Secrets and variables → Actions**, and set **Workflow permissions** to
*Read and write* so the job can commit its output back.

The workflow runs Mondays at 09:00 UTC and can be triggered manually from the
**Actions** tab. Each run picks up the newest unprocessed report, generates the
episode, and commits it.

## Notes from building this

A few things that weren't obvious going in:

- **Ten minutes of source audio produced a convincing Professional Voice Clone**,
  against documentation recommending thirty minutes to three hours.
- **Artifacts in the source recording carry into the clone.** Plosives and slurred
  articulation in the original sample showed up in every generation. Raising
  `stability` and lowering `style` reduced them; better mic technique fixed them at
  the root.
- **Written and spoken registers are genuinely different formats.** The script
  adaptation step matters more than expected — reading a report aloud verbatim
  sounds like reading a report aloud.

---

Built by [Eduardo Moore](https://www.linkedin.com/in/edumoore/).
