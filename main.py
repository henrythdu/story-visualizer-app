from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import os
import json
import shutil
from typing import Optional
import uuid
import asyncio
from datetime import datetime, timedelta

from services.story_processor import process_story, video_storage, cleanup_old_videos
from models.story import StoryAnalysisState
from config.settings import Settings

app = FastAPI(title="Story Visualizer Web")
settings = Settings()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Background task for cleaning up old videos
async def cleanup_task():
    """Periodically clean up old videos from storage"""
    while True:
        try:
            cleanup_old_videos()
        except Exception as e:
            print(f"Error during video cleanup: {e}")
        # Wait 10 minutes before next cleanup
        await asyncio.sleep(600)

@app.on_event("startup")
async def startup_event():
    """Start background tasks when the app starts"""
    # Start the cleanup task
    asyncio.create_task(cleanup_task())

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/process")
async def process_story_api(
    story_text: str = Form(...),
    image_model: str = Form("gemini")
):
    """
    Process a story and generate visualization
    """
    try:
        # Process the story
        result = await process_story(story_text, image_model)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/video/{video_id}")
async def stream_video(video_id: str):
    """
    Stream a generated video by ID
    """
    if video_id in video_storage:
        video_info = video_storage[video_id]
        return Response(content=video_info['data'], media_type="video/mp4")
    else:
        raise HTTPException(status_code=404, detail="Video not found")

# Serve generated files
@app.get("/output/{file_type}/{file_name}")
async def serve_generated_file(file_type: str, file_name: str):
    """Serve generated images, audio, or video files"""
    file_path = f"./output/{file_type}/{file_name}"
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return {"error": "File not found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)