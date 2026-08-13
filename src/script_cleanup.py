"""
script_cleanup.py

Takes a written report (markdown/text) and converts it into a natural,
spoken-language podcast script using the Anthropic API.

Handles:
- Grammar/register cleanup (written -> spoken)
- Removing visual-only elements (tables, screenshots, footnotes)
- Adding verbal signposting ("Now let's talk about...")
- Chaptering for easier TTS chunking downstream
"""

import os
import sys
import anthropic


SYSTEM_PROMPT = """You are a professional podcast script editor. You convert written \
business reports into natural, spoken-language podcast scripts.

Rules:
- Start the script with a section headed exactly "## Welcome" containing 2-4 sentences: \
welcome listeners to Edu's Podcast, then preview 2-4 of the sharpest, most specific facts \
or claims from this episode (real numbers, names, and stakes -- not vague topic labels like \
"today we discuss the market"). This section is spoken on its own, before anything else, so \
it must stand alone and make sense with zero prior context.
- Write for the EAR, not the eye. Short sentences. Natural spoken rhythm.
- Remove anything that only works visually: tables, chart references, footnote \
markers, "see below", image captions.
- If a table or chart is referenced, summarize its key takeaway in one spoken \
sentence instead of describing its structure.
- Add natural verbal transitions between sections ("Now, let's turn to...", \
"Here's where it gets interesting...", "So what does this mean in practice?").
- Fix any grammar or awkward phrasing from the source, but preserve all factual \
content, numbers, and claims exactly as given. Never invent or alter data.
- Keep the host's voice: direct, sharp, operator-minded, LatAm fintech focus.
- After the "## Welcome" section, break the rest of the script into clearly marked \
chapters using "## Chapter: <title>" headers, so it can be chunked for text-to-speech \
generation.
- Do not include any preamble, sign-off instructions, or meta-commentary — \
output ONLY the finished spoken script.
"""


def clean_report_to_script(report_text: str, api_key: str, model: str, max_tokens: int) -> str:
    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Convert this report into a spoken podcast script:\n\n{report_text}",
            }
        ],
    )

    # Concatenate all text blocks in the response
    return "".join(block.text for block in message.content if block.type == "text")


def main():
    if len(sys.argv) < 3:
        print("Usage: python script_cleanup.py <input_report.md> <output_script.md>")
        sys.exit(1)

    input_path, output_path = sys.argv[1], sys.argv[2]

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        report_text = f.read()

    script = clean_report_to_script(
        report_text,
        api_key=api_key,
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        max_tokens=int(os.environ.get("ANTHROPIC_MAX_TOKENS", "4096")),
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(script)

    print(f"Script written to {output_path}")


if __name__ == "__main__":
    main()
