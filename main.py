import os
import uuid
import subprocess
from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import FileResponse
from gtts import gTTS

app = FastAPI()

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

@app.post("/generate")
async def generate_horror_video(text: str = Form(...), video: UploadFile = None):
    # 1. Save uploaded video
    video_path = os.path.join(OUTPUT_DIR, f"{uuid.uuid4()}_video.mp4")
    with open(video_path, "wb") as f:
        f.write(await video.read())

    # 2. Generate narration with gTTS
    audio_path = os.path.join(OUTPUT_DIR, f"{uuid.uuid4()}_audio.mp3")
    tts = gTTS(text=text, lang="en")
    tts.save(audio_path)

    # 3. Add subtitles file (SRT)
    srt_path = os.path.join(OUTPUT_DIR, f"{uuid.uuid4()}.srt")
    with open(srt_path, "w") as f:
        f.write(f"1\n00:00:00,000 --> 00:00:10,000\n{text}\n")

    # 4. Merge video + audio + subtitles using ffmpeg
    output_path = os.path.join(OUTPUT_DIR, f"{uuid.uuid4()}_final.mp4")

    # FFmpeg command:
    cmd = [
        "ffmpeg", "-i", video_path, "-i", audio_path,
        "-vf", f"subtitles={srt_path}:force_style='Fontsize=24,PrimaryColour=&HFFFFFF&'",
        "-c:v", "libx264", "-c:a", "aac", "-shortest", "-y", output_path
    ]
    subprocess.run(cmd, check=True)

    return FileResponse(output_path, media_type="video/mp4", filename="horror_short.mp4")
