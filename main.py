from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncio
from datetime import datetime, timedelta
import uuid
from contextlib import asynccontextmanager
import io

# Import the video creation function
from services.create_video import create_video

# In-memory storage for video data
video_storage = {}

# Cleanup old videos periodically
async def cleanup_videos():
    while True:
        try:
            current_time = datetime.now()
            expired_keys = []
            for video_id, video_info in video_storage.items():
                if current_time - video_info['timestamp'] > timedelta(hours=1):
                    expired_keys.append(video_id)
            
            for key in expired_keys:
                del video_storage[key]
                
        except Exception as e:
            print(f"Error during video cleanup: {e}")
        
        await asyncio.sleep(600)  # Run every 10 minutes

# Start background task using lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the cleanup task
    cleanup_task = asyncio.create_task(cleanup_videos())
    yield
    # Clean up tasks on shutdown
    cleanup_task.cancel()

# Create FastAPI app with lifespan
app = FastAPI(title="Story Visualizer Web", lifespan=lifespan)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/process")
async def process_story(story_text: str = Form(...)):
    try:
        # Create video from story using your function
        video_clip = create_video(story_text)
        
        # Generate video data in memory
        video_buffer = io.BytesIO()
        video_clip.write_videofile(
            video_buffer,
            codec='libx264',
            fps=24,
            threads=4,
            logger=None
        )
        video_data = video_buffer.getvalue()
        
        # Store video with a unique ID
        video_id = str(uuid.uuid4())
        video_storage[video_id] = {
            'data': video_data,
            'timestamp': datetime.now()
        }
        
        # Clean up the clip
        video_clip.close()
        
        return {"video_id": video_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/video/{video_id}")
async def stream_video(video_id: str):
    if video_id in video_storage:
        video_info = video_storage[video_id]
        return Response(
            content=video_info['data'], 
            media_type="video/mp4",
            headers={
                "Content-Disposition": "inline; filename=story_visualization.mp4"
            }
        )
    else:
        raise HTTPException(status_code=404, detail="Video not found")