from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

SYSTEM_PROMPT = """You are an editorial moment-discovery assistant for personality-led founder videos.
Identify moments that make compelling standalone short-form clips, without inventing or rewriting what the speaker said.
Prioritize: a strong opening hook; a complete thought/story; specific insight, tension, emotion, surprising detail or useful lesson; context sufficient to stand alone; substance over generic engagement bait.
Avoid: repeated topics, incomplete thoughts, vague statements, promotional filler, moments dependent on missing context, and adjacent candidates that cover the same story.
Only use the supplied transcript text and timestamps. Do not hallucinate quotes or events.
Return JSON only, matching the requested schema."""


def transcript_windows(segments: list[dict[str, Any]], max_words: int = 1800) -> list[list[dict[str, Any]]]:
    windows: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    words = 0
    for seg in segments:
        n = len(seg["text"].split())
        if current and words + n > max_words:
            windows.append(current)
            current, words = [], 0
        current.append(seg)
        words += n
    if current:
        windows.append(current)
    return windows


def discover_candidates(segments: list[dict[str, Any]], model: str = "gpt-4o-mini") -> list[dict[str, Any]]:
    client = OpenAI()
    candidates: list[dict[str, Any]] = []
    for wi, window in enumerate(transcript_windows(segments), start=1):
        payload = [{"start": s["start"], "end": s["end"], "text": s["text"]} for s in window]
        prompt = f"""Find up to 8 potential short-form moments in this transcript window.
Each candidate must be 30 to 90 seconds long. Use timestamps from the transcript and prefer boundaries aligned to spoken segments.
Return JSON object with a 'candidates' array. Each candidate must contain:
- start (number, seconds from full video)
- end (number, seconds from full video)
- hook (short description of how the clip opens; not fabricated dialogue)
- reason (why this is worth clipping)
- excerpt (verbatim text drawn from the transcript)
- scores: hook, substance, coherence, standalone (each integer 1-5)
- topic (short label)
Do not create candidates that cannot fit 30-90 seconds. Do not score a clip highly just because it is sensational.
Transcript window {wi}:
{json.dumps(payload, ensure_ascii=False)}"""
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        parsed = json.loads(response.choices[0].message.content or "{}")
        candidates.extend(parsed.get("candidates", []))
    return candidates


def score_candidate(candidate: dict[str, Any]) -> float:
    scores = candidate.get("scores", {})
    # Equal-weighted rubric; simple and transparent for this demo.
    keys = ["hook", "substance", "coherence", "standalone"]
    values = [float(scores.get(k, 0)) for k in keys]
    return round(sum(values) / len(values), 2)


def validate_and_rank(candidates: list[dict[str, Any]], segments: list[dict[str, Any]], top_n: int = 3) -> list[dict[str, Any]]:
    valid: list[dict[str, Any]] = []
    source_start = segments[0]["start"] if segments else 0
    source_end = segments[-1]["end"] if segments else 0
    for c in candidates:
        try:
            start, end = float(c["start"]), float(c["end"])
        except (KeyError, ValueError, TypeError):
            continue
        duration = end - start
        if end <= start or start < source_start or end > source_end:
            continue

        # Expand short discovery anchors into contextual, transcript-aligned clips.
        if duration < 30:
            midpoint = (start + end) / 2
            target_duration = 45
            expanded_start = max(source_start, midpoint - target_duration / 2)
            expanded_end = min(source_end, midpoint + target_duration / 2)

            # Snap to transcript segment boundaries.
            start_segment = min(segments, key=lambda s: abs(s["start"] - expanded_start))
            end_segment = min(segments, key=lambda s: abs(s["end"] - expanded_end))
            start = start_segment["start"]
            end = end_segment["end"]
            duration = end - start

        if duration < 30 or duration > 90:
            continue
        # Keep candidates with meaningful transcript support inside their proposed boundaries.
        supporting = [s for s in segments if s["end"] > start and s["start"] < end]
        text = " ".join(s["text"] for s in supporting).strip()
        if len(text.split()) < 25:
            continue
        c = dict(c)
        c["start"] = round(start, 2)
        c["end"] = round(end, 2)
        c["duration"] = round(duration, 2)
        c["score"] = score_candidate(c)
        c["supporting_transcript"] = text
        valid.append(c)
    valid.sort(key=lambda c: (c["score"], len(c.get("reason", ""))), reverse=True)
    selected: list[dict[str, Any]] = []
    for c in valid:
        # Reject candidates whose time ranges substantially overlap selected candidates.
        overlap = any(min(c["end"], s["end"]) - max(c["start"], s["start"]) > 0.35 * min(c["duration"], s["duration"]) for s in selected)
        if not overlap:
            selected.append(c)
        if len(selected) == top_n:
            break
    return selected
