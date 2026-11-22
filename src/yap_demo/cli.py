from __future__ import annotations

import argparse
import json
from pathlib import Path

from .transcribe import transcribe_video
from .select import discover_candidates, validate_and_rank


def write_report(selected: list[dict], outdir: Path) -> None:
    md = ["# Yap Auto-Editor Demo: Top 3 Moments", "", "_Automated selections; editorial judgment remains necessary._", ""]
    for i, c in enumerate(selected, start=1):
        md += [f"## {i}. {c.get('topic', 'Candidate')}", "", f"**Time:** {c['start']:.2f}s – {c['end']:.2f}s ({c['duration']:.2f}s)",
               f"**Score:** {c['score']}/5", "", f"**Hook:** {c.get('hook', '')}", "", f"**Why selected:** {c.get('reason', '')}", "",
               "**Transcript excerpt:**", "", c.get("supporting_transcript", c.get("excerpt", "")), ""]
    (outdir / "report.md").write_text("\n".join(md), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover, rank and validate exactly 3 short-form moments.")
    parser.add_argument("video", type=Path, help="Input video file")
    parser.add_argument("--out", type=Path, default=Path("yap_output"), help="Output folder")
    parser.add_argument("--model", default="gpt-4o-mini", help="LLM model used for moment discovery")
    parser.add_argument("--language", default=None, help="Optional transcription language code (e.g. en). Leave blank for auto-detection.")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    transcript_path = args.out / "transcript.json"
    transcript = transcribe_video(args.video, transcript_path, args.language)
    raw = discover_candidates(transcript["segments"], args.model)
    (args.out / "candidates_raw.json").write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    selected = validate_and_rank(raw, transcript["segments"], top_n=3)
    if len(selected) != 3:
        raise SystemExit(f"Pipeline found only {len(selected)} valid non-overlapping candidates. Inspect candidates_raw.json; do not fabricate missing clips.")
    result = {"source": str(args.video), "transcript_file": str(transcript_path), "selection_model": args.model, "selected": selected}
    (args.out / "top3.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    write_report(selected, args.out)
    print(f"\nDone. Exactly 3 candidates saved in {args.out.resolve()}\n- transcript.json\n- candidates_raw.json\n- top3.json\n- report.md")

if __name__ == "__main__":
    main()
