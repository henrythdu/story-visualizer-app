import operator
import json
import os
import io
import time
import re
from typing import List, Dict, Optional
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from PIL import Image, ImageDraw
import numpy as np
from scipy.io.wavfile import write

# For video generation
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

from models.story import StoryAnalysisState
from config.settings import Settings

settings = Settings()

# In-memory storage for video data (in a production app, you might use Redis or similar)
# Each entry contains: {'data': bytes, 'timestamp': datetime}
video_storage = {}

def cleanup_old_videos():
    """
    Remove videos older than 1 hour from storage to prevent memory issues
    """
    current_time = datetime.now()
    expired_keys = []
    
    for video_id, video_info in video_storage.items():
        if current_time - video_info['timestamp'] > timedelta(hours=1):
            expired_keys.append(video_id)
    
    for key in expired_keys:
        del video_storage[key]
        
    if expired_keys:
        print(f"Cleaned up {len(expired_keys)} old videos from storage")

def generate_mock_image(scene_num: int, output_path: str):
    """
    Generate a mock image for testing when no API key is available
    """
    try:
        # Create a simple colored image with text
        image = Image.new('RGB', (640, 480), color='lightblue')
        draw = ImageDraw.Draw(image)
        draw.text((10, 10), f"Scene {scene_num} Visualization", fill='black')
        draw.text((10, 30), "Mock Image Generated", fill='black')
        image.save(output_path)
        return True
    except Exception as e:
        print(f"Error generating mock image for scene {scene_num}: {e}")
        return False

def generate_mock_audio(scene_text: str, output_path: str):
    """
    Generate mock audio for testing when no TTS is available
    """
    try:
        # Create a simple tone based on text length
        sample_rate = 44100
        # Duration based on text length (1 second per 100 characters, min 0.5s, max 5s)
        duration = min(5.0, max(0.5, len(scene_text) / 100.0))
        frequency = 440.0  # A4 note

        # Generate the audio samples
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio_data = np.sin(2 * np.pi * frequency * t)

        # Write the WAV file
        write(output_path, sample_rate, audio_data.astype(np.float32))
        return True
    except Exception as e:
        print(f"Error generating mock audio: {e}")
        return False

def create_final_video(state: StoryAnalysisState) -> bytes:
    """
    Create a final video from the generated images and audio, returning video data in memory.
    """
    log = state.get("processing_log", [])
    scenes = state.get("scenes", [])
    scene_clips = []
    
    print("Starting video creation process...")
    log.append("Starting video creation process...")
    
    # Clean up old videos before creating a new one
    cleanup_old_videos()

    if isinstance(scenes, list):
        for scene in scenes:
            scene_num = scene.get('scene_number', 'Unknown')
            image_path = scene.get('image_url')
            audio_path = scene.get('audio_url')

            print(f"\nProcessing Scene {scene_num}...")
            log.append(f"Processing Scene {scene_num}...")
            
            # Validate file paths
            if not image_path:
                print(f"  Warning: No image path provided for scene {scene_num}. Skipping scene.")
                log.append(f"  Warning: No image path provided for scene {scene_num}. Skipping scene.")
                continue
                
            if not audio_path:
                print(f"  Warning: No audio path provided for scene {scene_num}. Skipping scene.")
                log.append(f"  Warning: No audio path provided for scene {scene_num}. Skipping scene.")
                continue
                
            # Adjust paths for local file access
            local_image_path = image_path.lstrip('/')
            local_audio_path = audio_path.lstrip('/')
            
            # Check if files exist
            if not os.path.exists(local_image_path):
                print(f"  Warning: Image file not found for scene {scene_num} at {local_image_path}. Skipping scene.")
                log.append(f"  Warning: Image file not found for scene {scene_num} at {local_image_path}. Skipping scene.")
                continue
            if not os.path.exists(local_audio_path):
                print(f"  Warning: Audio file not found for scene {scene_num} at {local_audio_path}. Skipping scene.")
                log.append(f"  Warning: Audio file not found for scene {scene_num} at {local_audio_path}. Skipping scene.")
                continue

            try:
                audio_clip = AudioFileClip(local_audio_path)
                scene_duration = audio_clip.duration
                if scene_duration <= 0:
                     print(f"  Warning: Audio duration is zero or negative for scene {scene_num}. Skipping scene.")
                     log.append(f"  Warning: Audio duration is zero or negative for scene {scene_num}. Skipping scene.")
                     audio_clip.close()
                     continue
                print(f"  Audio Duration: {scene_duration:.2f} seconds")
                log.append(f"  Audio Duration: {scene_duration:.2f} seconds")

                img_clip = ImageClip(local_image_path).set_duration(scene_duration)
                video_clip = img_clip.set_audio(audio_clip)
                scene_clips.append(video_clip)
                print(f"  Successfully created video clip for scene {scene_num}.")
                log.append(f"  Successfully created video clip for scene {scene_num}.")

            except Exception as e:
                print(f"  Error processing scene {scene_num}: {e}")
                log.append(f"  Error processing scene {scene_num}: {e}")
                # Close clips if there was an error
                if 'audio_clip' in locals():
                    audio_clip.close()

    if scene_clips:
        print(f"\nConcatenating {len(scene_clips)} scene clips...")
        log.append(f"Concatenating {len(scene_clips)} scene clips...")
        try:
            final_clip = concatenate_videoclips(scene_clips, method="compose")
            print("Generating video data in memory...")
            log.append("Generating video data in memory...")
          
            # Create video data in memory instead of saving to file
            from io import BytesIO
            video_buffer = BytesIO()
            
            final_clip.write_videofile(
                video_buffer,
                codec='libx264',
                fps=24,
                threads=4,
                logger=None
            )
            
            video_data = video_buffer.getvalue()
            print("Final video generated successfully in memory!")
            log.append("Final video generated successfully in memory!")
            final_clip.close()
            
            # Close all scene clips
            for clip in scene_clips:
                if hasattr(clip, 'close'):
                    clip.close()
            
            return video_data

        except Exception as e:
            print(f"Error during concatenation or generating final video: {e}")
            log.append(f"Error during concatenation or generating final video: {e}")
            # Close the final clip if it was created
            if 'final_clip' in locals() and hasattr(final_clip, 'close'):
                final_clip.close()
    else:
        print("No valid scene clips were created. Final video cannot be generated.")
        log.append("No valid scene clips were created. Final video cannot be generated.")
    
    # Cleanup
    print("Cleaning up...")
    log.append("Cleaning up...")
    for clip in scene_clips:
         if hasattr(clip, 'close'):
             clip.close()

    return b""

async def process_story(story_text: str, image_model: str = "gemini", 
                       api_key: Optional[str] = None, 
                       api_url: Optional[str] = None, 
                       api_model: Optional[str] = None) -> StoryAnalysisState:
    """
    Process a story through all steps and return the results.
    """
    # Initialize state with mock data for testing
    initial_state = {
        "story_text": story_text,
        "characters": {},
        "scenes": [
            {
                "scene_number": 1,
                "scene_text": "Once upon a time...",
                "summary": "Beginning of the story",
                "setting": "A magical forest",
                "characters_present": [],
                "tone": "mysterious",
                "image_url": None,
                "audio_url": None
            }
        ],
        "overall_style": None,
        "processing_log": []
    }
    
    log = initial_state["processing_log"]
    
    # Generate mock images and audio for testing
    output_dir = settings.IMAGE_OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    
    audio_output_dir = settings.AUDIO_OUTPUT_DIR
    os.makedirs(audio_output_dir, exist_ok=True)
    
    scenes = initial_state["scenes"]
    updated_scenes = []
    
    for scene in scenes:
        scene_num = scene.get('scene_number', 'N/A')
        scene_text = scene.get('scene_text', '')
        
        # Generate mock image
        image_filename = f"scene_{scene_num}_image.png"
        image_path = os.path.join(output_dir, image_filename)
        if generate_mock_image(scene_num, image_path):
            scene['image_url'] = f"/output/images/{image_filename}"
            log.append(f"Generated mock image for scene {scene_num}")
        else:
            scene['image_url'] = None
            log.append(f"Failed to generate mock image for scene {scene_num}")
        
        # Generate mock audio
        audio_filename = f"scene_{scene_num}_audio.wav"
        audio_path = os.path.join(audio_output_dir, audio_filename)
        if generate_mock_audio(scene_text, audio_path):
            scene['audio_url'] = f"/output/audio/{audio_filename}"
            log.append(f"Generated mock audio for scene {scene_num}")
        else:
            scene['audio_url'] = None
            log.append(f"Failed to generate mock audio for scene {scene_num}")
        
        updated_scenes.append(scene)
    
    initial_state["scenes"] = updated_scenes
    
    # Create final video in memory
    video_data = create_final_video(initial_state)
    if video_data:
        # Store video data with a unique ID and timestamp
        video_id = str(uuid.uuid4())
        video_storage[video_id] = {
            'data': video_data,
            'timestamp': datetime.now()
        }
        initial_state["video_id"] = video_id
        # Remove video_url since we're not saving to file anymore
        if "video_url" in initial_state:
            del initial_state["video_url"]
    
    return initial_state