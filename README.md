# Yap Auto-Editor Demo

Take-home prototype for PRD 5: turn a ~20-minute founder video into **exactly 3 ranked, timestamped short-form moment candidates**, with explanations and transcript evidence.

## Scope

- Transcribe video into timestamped segments (OpenAI Whisper API).
- Discover candidate moments using an LLM over transcript windows.
- Score candidates on hook, substance, coherence and standalone value.
- Deterministically validate 30–90s boundaries and transcript coverage.
- Reject substantially overlapping candidates.
- Export raw candidates, top-3 JSON and a readable report.

No UI, video rendering, publishing, Notion integration or scheduling is included.

## Requirements

- Python 3.10+
- FFmpeg and FFprobe
- OpenAI API key

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
export OPENAI_API_KEY="..."
```

## Run

```bash
yap-demo /path/to/video.mp4 --out results
```

Optional language hint:

```bash
yap-demo /path/to/video.mp4 --language en --out results
```

## Outputs

- `transcript.json`: timestamped transcript
- `candidates_raw.json`: LLM-proposed candidates
- `top3.json`: exactly three selected candidates (fails instead of inventing candidates if fewer than three pass validation)
- `report.md`: human-readable review report

## Selection rubric

Equal-weighted 1–5 scores: hook, substance, coherence, standalone value. Ranking is deliberately simple and transparent for the prototype. Overlap rejection is deterministic. Candidate quality still requires human review.

## Known limitations

- LLM timestamps are proposals; validation checks duration, source bounds, transcript support and overlap, but does not yet snap timestamps to word-level boundaries or inspect video frames.
- No caption/rendering, visual scoring, silence detection, multilingual benchmark, or editor-retention measurement.
- A long transcript may produce several candidate batches; this prototype deduplicates by time overlap only.
