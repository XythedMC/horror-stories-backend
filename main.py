from fastapi import FastAPI, UploadFile, Form
import subprocess
from gtts import gTTS
import uuid
import os

app = FastAPI()

@app.post("/generate")
async def generate(text: str = Form(...), video: UploadFile = None):
    # Save uploaded video
    video_path = f"/tmp/{uuid.uuid4()}.mp4"
    with open(video_path, "wb") as f:
        f.write(await video.read())

    # Generate audio with gTTS
    audio_path = f"/tmp/{uuid.uuid4()}.mp3"
    tts = gTTS(text=text, lang="en")
    tts.save(audio_path)

    # Merge video + audio
    output_path = f"/tmp/{uuid.uuid4()}.mp4"
    subprocess.run([
        "ffmpeg", "-i", video_path, "-i", audio_path,
        "-c:v", "copy", "-c:a", "aac", "-shortest", output_path,
        "-y"
    ])

    # Return file
    return {"file_path": output_path}
