import streamlit as st
import sys
import subprocess
import json
import shutil
from pathlib import Path

st.set_page_config(page_title="Yap | Auto-Editor", layout="wide")

st.markdown(Path("style.txt").read_text(), unsafe_allow_html=True)

BASE = Path("outputs")
PREVIEW = BASE / "previews"
VERTICAL = BASE / "vertical"

def get_value(obj, *keys, default=None):
    for key in keys:
        if key in obj and obj[key] is not None:
            return obj[key]
    return default

def generate_clips(video_path, candidates):
    PREVIEW.mkdir(parents=True, exist_ok=True)
    VERTICAL.mkdir(parents=True, exist_ok=True)

    for i, clip in enumerate(candidates, 1):
        start = float(get_value(clip, "start", "start_time", default=0))
        end = float(get_value(clip, "end", "end_time", default=0))
        duration = end - start

        if duration <= 0:
            continue

        raw = PREVIEW / f"clip_{i}.mp4"
        portrait = VERTICAL / f"clip_{i}_9x16.mp4"

        subprocess.run([
            "ffmpeg", "-y", "-ss", str(start), "-i", str(video_path),
            "-t", str(duration), "-c:v", "libx264", "-preset", "fast",
            "-crf", "23", "-c:a", "aac", str(raw)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        subprocess.run([
            "ffmpeg", "-y", "-i", str(raw),
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", str(portrait)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

st.title("Yap Auto-Editor")
st.caption("Find, review and prepare short-form content from founder video sessions.")
st.divider()

uploaded = st.file_uploader("Upload a video session", type=["mp4", "mov", "m4v"])

if uploaded:
    st.caption(f"Selected: {uploaded.name}")

    if st.button("Analyze session", type="primary"):
        st.session_state.pop("analysis_done", None)
        BASE.mkdir(exist_ok=True)

        video_path = BASE / uploaded.name
        video_path.write_bytes(uploaded.getbuffer())

        with st.status("Analyzing video...", expanded=True) as status:
            st.write("Transcribing audio...")
            st.write("Discovering potential moments...")

            result = subprocess.run([
                sys.executable, "-m", "yap_demo.cli",
                str(video_path), "--out", str(BASE),
                "--model", "gpt-4o", "--language", "en"
            ], capture_output=True, text=True)

            if result.returncode != 0:
                status.update(label="Analysis failed", state="error")
                st.error(result.stderr or result.stdout)
                st.stop()

            st.write("Validating and ranking candidates...")
            top3_path = BASE / "top3.json"

            if not top3_path.exists():
                st.error("top3.json was not generated.")
                st.stop()

            candidates = json.loads(top3_path.read_text())

            if isinstance(candidates, dict):
                candidates = candidates.get("selected", candidates.get("candidates", candidates.get("clips", [])))

            st.write("Rendering video previews...")
            generate_clips(video_path, candidates)

            status.update(label="Analysis complete", state="complete")

        st.session_state["analysis_done"] = True
        st.rerun()

# Results are displayed ONLY after a successful analysis
if st.session_state.get("analysis_done"):
    top3_path = BASE / "top3.json"
    report_path = BASE / "report.md"

    candidates = json.loads(top3_path.read_text())
    if isinstance(candidates, dict):
        candidates = candidates.get("selected", candidates.get("candidates", candidates.get("clips", [])))

    st.divider()
    st.subheader("Selected moments")
    st.caption("Ranked candidates identified from your session.")

    cols = st.columns(3, gap="medium")

    for i, clip in enumerate(candidates[:3]):
        title = get_value(clip, "topic", "title", "hook", default=f"Clip {i+1}")
        reason = get_value(clip, "reason", "explanation", default="")
        start = float(get_value(clip, "start", "start_time", default=0))
        end = float(get_value(clip, "end", "end_time", default=0))
        score = get_value(clip, "score", default=None)

        portrait = VERTICAL / f"clip_{i+1}_9x16.mp4"

        with cols[i]:
            with st.container(border=True):
                st.markdown(f"### {i+1:02d} · {title}")
                st.caption(f"{start:.1f}s – {end:.1f}s · {end-start:.1f} sec")

                if portrait.exists():
                    st.video(portrait.read_bytes())

                if score is not None:
                    st.metric("Selection score", f"{score}/5")

                st.markdown(
                    f'<div style="height:110px;overflow:auto;padding-top:8px;">{reason}</div>',
                    unsafe_allow_html=True
                )

                st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

                if portrait.exists():
                    st.download_button(
                        "Download clip",
                        data=portrait.read_bytes(),
                        file_name=portrait.name,
                        mime="video/mp4",
                        key=f"download_{i}",
                        use_container_width=True
                    )

    if report_path.exists():
        with st.expander("View full analysis report"):
            st.markdown(report_path.read_text())

    st.divider()
    st.caption("Yap Auto-Editor · Prototype")

