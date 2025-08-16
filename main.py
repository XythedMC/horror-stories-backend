import os, subprocess, uuid, re, math, shlex
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List
import tempfile
import pathlib

app = FastAPI(title="Horror Shorts Processor", version="1.0.0")

def run(cmd: str):
    proc = subprocess.run(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed:\n{cmd}\n\nSTDERR:\n{proc.stderr[:1000]}")
    return proc.stdout

def ffprobe_duration(path: str) -> float:
    cmd = f'ffprobe -v error -select_streams a:0 -show_entries stream=duration -of default=nw=1:nk=1 "{path}"'
    out = run(cmd).strip()
    try:
        return float(out)
    except:
        # Fallback to file duration (any stream)
        cmd2 = f'ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "{path}"'
        out2 = run(cmd2).strip()
        return float(out2)

def sanitize_filename(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9 _-]+", "", name).strip()
    return name or "video"

def chunk_text_words(text: str, n_chunks: int) -> List[str]:
    words = text.split()
    if not words: return [""]
    chunks = []
    base = math.ceil(len(words) / max(1, n_chunks))
    for i in range(0, len(words), base):
        chunks.append(" ".join(words[i:i+base]))
    return chunks

def srt_time(ms: int) -> str:
    h = ms // 3600000
    ms -= h*3600000
    m = ms // 60000
    ms -= m*60000
    s = ms // 1000
    ms -= s*1000
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def write_srt(text: str, dur_sec: float, srt_path: str):
    # Target ~3s per cue, min 1 cue, max ~12 cues
    target = 3.0
    n = max(1, min(12, int(round(dur_sec / target)) or 1))
    chunks = chunk_text_words(text, n)
    total_ms = int(max(1000, dur_sec * 1000))
    slice_ms = total_ms // len(chunks)

    lines = []
    start = 0
    for i, chunk in enumerate(chunks, start=1):
        end = total_ms if i == len(chunks) else start + slice_ms
        lines.append(f"{i}\n{srt_time(start)} --> {srt_time(end)}\n{chunk}\n")
        start = end
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

@app.post("/process")
async def process(
    story: str = Form(..., description="PG-13 horror micro-story (<= 50–80 words)"),
    audio: UploadFile = File(..., description="MP3 narration"),
    video: UploadFile = File(..., description="MP4 background clip"),
    title: str = Form("Horror Short", description="Optional title")
):
    # temp working dir
    work = tempfile.mkdtemp(prefix="horror_")
    try:
        safe_title = sanitize_filename(title)
        audio_path = os.path.join(work, "narration.mp3")
        video_path = os.path.join(work, "clip.mp4")
        srt_path   = os.path.join(work, "story.srt")
        v_portrait = os.path.join(work, "portrait.mp4")
        out_path   = os.path.join(work, f"{safe_title}.mp4")

        # save uploads
        with open(audio_path, "wb") as f:
            f.write(await audio.read())
        with open(video_path, "wb") as f:
            f.write(await video.read())

        # duration from audio
        dur = max(1.5, ffprobe_duration(audio_path))

        # write SRT
        # Keep it PG-13: trim excessive length just-in-case
        story_clean = story.strip().replace("\r", " ")
        if len(story_clean) > 600:
            story_clean = story_clean[:600] + "…"
        write_srt(story_clean, dur, srt_path)

        # 1) portraitize 1080x1920 with pad (keep AR)
        run(f'ffmpeg -y -i "{video_path}" -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2" -an -c:v libx264 -preset veryfast -crf 18 "{v_portrait}"')

        # 2) burn subtitles + add narration (requires libass; Debian ffmpeg includes it)
        # tweak font size/outline for visibility
        sub_style = "FontName=DejaVu Sans,Fontsize=36,PrimaryColour=&H00FFFFFF&,OutlineColour=&H00000000&,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=48"
        run(
            f'ffmpeg -y -i "{v_portrait}" -i "{audio_path}" '
            f'-vf "subtitles={srt_path}:force_style=\'{sub_style}\'" '
            f'-shortest -c:v libx264 -preset veryfast -crf 18 -c:a aac -b:a 192k "{out_path}"'
        )

        # stream result back
        filename = pathlib.Path(out_path).name
        return FileResponse(out_path, media_type="video/mp4", filename=filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
