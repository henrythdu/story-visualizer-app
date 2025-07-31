from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncio
from datetime import datetime, timedelta
import uuid
from contextlib import asynccontextmanager
import io
import json

# Import the video creation function
from services.create_video import create_video

# Function to write video file in a separate thread
def write_video_file(video_clip, filename):
    video_clip.write_videofile(
        filename,
        codec='libx264',
        fps=24,
        threads=4,
        logger=None
    )

# In-memory storage for video data
video_storage = {}

# In-memory storage for logs
log_storage = {}

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
                # Also clean up logs
                if key in log_storage:
                    del log_storage[key]
                
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

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/process")
async def process_story(story_text: str = Form(...), api_key: str = Form(None)):
    # Generate a unique ID for this processing session
    process_id = str(uuid.uuid4())
    
    # Initialize log storage for this process
    log_storage[process_id] = []
    
    # Add initial log message for debugging
    log_storage[process_id].append("Process initialized. Starting story processing...")
    print(f"[DEBUG] Process {process_id} initialized")  # Debug
    # Force flush to ensure immediate delivery
    import sys
    sys.stdout.flush()
    sys.stderr.flush()
    
    # Return the process ID immediately so frontend can start streaming logs
    # Process the video in background
    asyncio.create_task(process_video_async(story_text, process_id, api_key))
    
    return {"process_id": process_id}

async def process_video_async(story_text: str, process_id: str, api_key: str = None):
    print(f"[DEBUG] Starting process_video_async for process_id: {process_id}")  # Debug
    # Force flush to ensure immediate delivery
    import sys
    sys.stdout.flush()
    sys.stderr.flush()
    # Add initial log message
    if process_id in log_storage:
        log_storage[process_id].append("Starting story processing...")
        print("[DEBUG] Added initial log message")  # Debug
        # Force flush to ensure immediate delivery
        sys.stdout.flush()
        sys.stderr.flush()
    
    # Small delay to ensure streaming connection is established
    await asyncio.sleep(0.01)
    
    try:
        print("[DEBUG] Calling create_video function")  # Debug
        # Create video from story using your function
        # Use the async version to allow event loop to continue
        from services.create_video import create_video_async
        video_clip = await create_video_async(story_text, process_id, log_storage, api_key)
        print("[DEBUG] Finished create_video function")  # Debug
        
        # Generate video data in memory using a temporary approach
        import tempfile
        import os
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmpfile:
            temp_filename = tmpfile.name
            
        # Write video to temporary file (run in thread to avoid blocking)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, write_video_file, video_clip, temp_filename)
        
        # Read the video data from the temporary file
        with open(temp_filename, 'rb') as f:
            video_data = f.read()
        
        # Clean up the temporary file
        os.unlink(temp_filename)
        
        # Debug: Check the size of video_data
        print(f"Video data size: {len(video_data)} bytes")
        
        # Store video with a unique ID
        video_id = str(uuid.uuid4())
        video_storage[video_id] = {
            'data': video_data,
            'timestamp': datetime.now(),
            'process_id': process_id  # Link video to process
        }
        
        # Add a completion message to logs
        if process_id in log_storage:
            log_storage[process_id].append("Video processing completed successfully!")
            log_storage[process_id].append(f"Video ID: {video_id}")
            # Force flush to ensure immediate delivery
            import sys
            sys.stdout.flush()
            sys.stderr.flush()
        
        # Clean up the clip
        video_clip.close()
        
    except Exception as e:
        print(f"Error in process_video_async: {e}")
        import traceback
        traceback.print_exc()
        # Add error message to logs
        if process_id in log_storage:
            log_storage[process_id].append(f"Error during processing: {str(e)}")


@app.get("/api/video/{video_id}")
async def stream_video(video_id: str):
    if video_id in video_storage:
        video_info = video_storage[video_id]
        print(f"Streaming video {video_id} with size: {len(video_info['data'])} bytes")
        return Response(
            content=video_info['data'], 
            media_type="video/mp4",
            headers={
                "Content-Disposition": "inline; filename=story_visualization.mp4"
            }
        )
    else:
        raise HTTPException(status_code=404, detail="Video not found")

@app.get("/api/video/by_process/{process_id}")
async def get_video_by_process(process_id: str):
    # Look for a video associated with this process ID
    for video_id, video_info in video_storage.items():
        if video_info.get('process_id') == process_id:
            return {"video_id": video_id}
    
    # If no video found, return 404
    raise HTTPException(status_code=404, detail="Video not ready or not found")

@app.get("/api/logs/{process_id}")
async def stream_logs(process_id: str):
    async def log_generator():
        print(f"[DEBUG] Starting log stream for process_id: {process_id}")  # Debug
        # Force flush to ensure immediate delivery
        import sys
        sys.stdout.flush()
        sys.stderr.flush()
        sent_logs = 0
        # Send all existing logs first
        if process_id in log_storage:
            logs = log_storage[process_id]
            print(f"[DEBUG] Found {len(logs)} existing logs")  # Debug
            # Force flush to ensure immediate delivery
            sys.stdout.flush()
            sys.stderr.flush()
            for i in range(len(logs)):
                yield f"data: {json.dumps({'message': logs[i]})}\n\n"
                print(f"[DEBUG] Sent log: {logs[i]}")  # Debug
                # Force flush to ensure immediate delivery
                sys.stdout.flush()
                sys.stderr.flush()
            sent_logs = len(logs)
        
        # Then continue sending new logs as they appear
        while True:
            if process_id in log_storage:
                logs = log_storage[process_id]
                # Send new logs
                if len(logs) > sent_logs:
                    print(f"[DEBUG] Found {len(logs) - sent_logs} new logs")  # Debug
                    # Force flush to ensure immediate delivery
                    sys.stdout.flush()
                    sys.stderr.flush()
                    for i in range(sent_logs, len(logs)):
                        yield f"data: {json.dumps({'message': logs[i]})}\n\n"
                        print(f"[DEBUG] Sent new log: {logs[i]}")  # Debug
                        # Force flush to ensure immediate delivery
                        sys.stdout.flush()
                        sys.stderr.flush()
                    sent_logs = len(logs)
            # Reduce delay for more responsive updates
            await asyncio.sleep(0.01)  # Check for new logs every 0.01 seconds (increased frequency)
    
    return StreamingResponse(log_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)