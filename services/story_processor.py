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

# Google GenAI for image generation
try:
    from google import genai
    from google.genai import types
    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    GOOGLE_GENAI_AVAILABLE = False
    genai = None
    types = None

# FastRTC for TTS
try:
    from fastrtc import get_tts_model
    FASTRTC_AVAILABLE = True
except ImportError:
    FASTRTC_AVAILABLE = False
    get_tts_model = None

from models.story import StoryAnalysisState
from config.settings import Settings

settings = Settings()

# In-memory storage for video data (in a production app, you might use Redis or similar)
# Each entry contains: {'data': bytes, 'timestamp': datetime}
video_storage = {}

# Global variables for models
llm = None
genai_client = None
tts_model = None

def initialize_models(api_key: Optional[str] = None, api_url: Optional[str] = None, api_model: Optional[str] = None):
    """
    Initialize the models with provided API configuration
    """
    global llm, genai_client, tts_model
    
    # Use provided API key or fallback to settings
    google_api_key = api_key or settings.GOOGLE_API_KEY or settings.IMAGE_API_KEY
    image_model = api_model or settings.IMAGE_API_MODEL or "gemini-2.0-flash-exp-image-generation"
    
    # Initialize Google GenAI for image generation
    if google_api_key and GOOGLE_GENAI_AVAILABLE:
        try:
            os.environ["GOOGLE_API_KEY"] = google_api_key
            genai_client = genai.Client()
            print(f"Google GenAI Image Generation client initialized with model: {image_model}")
        except Exception as e:
            print(f"Error initializing Google GenAI Image Generation client: {e}")
            genai_client = None
    else:
        genai_client = None
        if not google_api_key:
            print("⚠️ Google API key not provided. Using mock image generation.")
        if not GOOGLE_GENAI_AVAILABLE:
            print("⚠️ Google GenAI library not available. Using mock image generation.")
    
    # Initialize FastRTC TTS model
    if FASTRTC_AVAILABLE:
        try:
            tts_model = get_tts_model
            print("FastRTC TTS model initialized")
        except Exception as e:
            print(f"Error initializing FastRTC TTS model: {e}")
            tts_model = None
    else:
        tts_model = None
        print("⚠️ FastRTC library not available. Using mock audio generation.")

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

def generate_image_with_genai(prompt: str, output_path: str, model_name: str = "gemini-2.0-flash-exp-image-generation") -> bool:
    """
    Generate an image using Google GenAI API
    """
    if not genai_client:
        return False
    
    try:
        # Call the Google GenAI API for image generation
        response = genai_client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=['Text', 'Image'],
            )
        )
        time.sleep(1)  # Rate limiting
        
        # Process the response to find and save the image
        if response.candidates and hasattr(response.candidates[0], 'content') and hasattr(response.candidates[0].content, 'parts'):
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and hasattr(part.inline_data, 'data'):
                    print("Image data received from GenAI API.")
                    image_data = part.inline_data.data
                    try:
                        image = Image.open(io.BytesIO(image_data))
                        image.save(output_path)
                        print(f"Saved image to: {output_path}")
                        return True
                    except Exception as img_err:
                        print(f"Error processing/saving image data: {img_err}")
                        return False
        
        print("No valid image data found in API response.")
        return False
    except Exception as e:
        print(f"Error during image generation API call: {e}")
        return False

def generate_mock_image(scene_description: str, scene_num: int, output_path: str):
    """
    Generate a mock image based on scene description for testing when no API key is available
    """
    try:
        # Create a simple colored image with text based on scene description
        image = Image.new('RGB', (640, 480), color='lightblue')
        draw = ImageDraw.Draw(image)
        draw.text((10, 10), f"Scene {scene_num}", fill='black')
        # Truncate description to fit in image
        desc_lines = [scene_description[i:i+50] for i in range(0, min(len(scene_description), 150), 50)]
        for i, line in enumerate(desc_lines):
            draw.text((10, 30 + i*20), line, fill='black')
        draw.text((10, 120), "Generated Visualization", fill='black')
        image.save(output_path)
        return True
    except Exception as e:
        print(f"Error generating mock image for scene {scene_num}: {e}")
        return False

def generate_audio_with_fastrtc(text: str, output_path: str) -> bool:
    """
    Generate audio using FastRTC TTS model
    """
    if not tts_model:
        return False
    
    try:
        # Generate audio using FastRTC
        sample_rate, audio_data = tts_model(text)
        
        # Write the WAV file
        write(output_path, sample_rate, audio_data)
        return True
    except Exception as e:
        print(f"Error generating audio with FastRTC: {e}")
        return False

def generate_mock_audio(scene_text: str, output_path: str):
    """
    Generate mock audio for testing when no TTS is available
    """
    try:
        # Create a simple tone based on text length
        sample_rate = 22050  # Lower sample rate to reduce file size
        # Duration based on text length (0.5 seconds per 50 characters, min 1s, max 10s)
        duration = min(10.0, max(1.0, len(scene_text) / 50.0))
        frequency = 440.0  # A4 note

        # Generate the audio samples
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        # Add some variation to make it more interesting
        audio_data = np.sin(2 * np.pi * frequency * t) * np.exp(-t/2)

        # Write the WAV file
        write(output_path, sample_rate, audio_data.astype(np.float32))
        return True
    except Exception as e:
        print(f"Error generating mock audio: {e}")
        return False

def analyze_story_scenes(story_text: str) -> List[Dict]:
    """
    Simple scene analysis based on paragraph breaks and keywords
    """
    # Split story into paragraphs (scenes)
    paragraphs = [p.strip() for p in story_text.split('\n\n') if p.strip()]
    
    scenes = []
    for i, paragraph in enumerate(paragraphs[:5]):  # Limit to 5 scenes for demo
        # Simple setting detection based on keywords
        setting_keywords = {
            'forest': 'Enchanted Forest',
            'castle': 'Ancient Castle',
            'ocean': 'Open Ocean',
            'city': 'Bustling City',
            'mountain': 'Snowy Mountains',
            'desert': 'Sandy Desert',
            'space': 'Outer Space',
            'underwater': 'Underwater Kingdom'
        }
        
        setting = "Generic Location"
        for keyword, location in setting_keywords.items():
            if keyword in paragraph.lower():
                setting = location
                break
        
        # Simple tone detection
        tone_keywords = {
            'dark': 'Mysterious',
            'scary': 'Frightening',
            'happy': 'Joyful',
            'sad': 'Melancholy',
            'exciting': 'Thrilling',
            'calm': 'Peaceful'
        }
        
        tone = "Neutral"
        for keyword, mood in tone_keywords.items():
            if keyword in paragraph.lower():
                tone = mood
                break
        
        # Create image prompt based on scene details
        image_prompt = f"{setting}, {tone.lower()} atmosphere, digital art"
        
        scene = {
            "scene_number": i + 1,
            "scene_text": paragraph,
            "summary": paragraph[:50] + "..." if len(paragraph) > 50 else paragraph,
            "setting": setting,
            "characters_present": [],  # Would be populated with character detection
            "tone": tone,
            "image_prompt": image_prompt,
            "image_url": None,
            "audio_url": None
        }
        scenes.append(scene)
    
    return scenes

def create_final_video(state: StoryAnalysisState) -> Optional[bytes]:
    """
    Create a final video from the generated images and audio, returning video data in memory.
    """
    try:
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

        return None
    except Exception as e:
        print(f"Unexpected error in create_final_video: {e}")
        return None

async def process_story(story_text: str, image_model: str = "gemini", 
                       api_key: Optional[str] = None, 
                       api_url: Optional[str] = None, 
                       api_model: Optional[str] = None) -> StoryAnalysisState:
    """
    Process a story through all steps and return the results.
    """
    try:
        # Initialize models with provided API configuration
        initialize_models(api_key, api_url, api_model)
        
        # Initialize state
        initial_state = {
            "story_text": story_text,
            "characters": {},
            "scenes": [],
            "overall_style": None,
            "processing_log": []
        }
        
        log = initial_state["processing_log"]
        log.append("Starting story processing...")
        
        # Analyze story into scenes
        scenes = analyze_story_scenes(story_text)
        initial_state["scenes"] = scenes
        log.append(f"Analyzed story into {len(scenes)} scenes")
        
        # Generate images and audio for each scene
        output_dir = settings.IMAGE_OUTPUT_DIR
        os.makedirs(output_dir, exist_ok=True)
        
        audio_output_dir = settings.AUDIO_OUTPUT_DIR
        os.makedirs(audio_output_dir, exist_ok=True)
        
        updated_scenes = []
        
        for scene in scenes:
            scene_num = scene.get('scene_number', 'N/A')
            scene_text = scene.get('scene_text', '')
            setting = scene.get('setting', 'Unknown location')
            image_prompt = scene.get('image_prompt', f"{setting} illustration")
            
            # Generate image - try GenAI first, fallback to mock
            image_filename = f"scene_{scene_num}_image.png"
            image_path = os.path.join(output_dir, image_filename)
            
            image_generated = False
            if genai_client:
                model_name = api_model or settings.IMAGE_API_MODEL or "gemini-2.0-flash-exp-image-generation"
                image_generated = generate_image_with_genai(image_prompt, image_path, model_name)
                if image_generated:
                    log.append(f"Generated image using GenAI for scene {scene_num}")
                else:
                    log.append(f"Failed to generate image with GenAI for scene {scene_num}, using mock")
            
            # If GenAI failed or not available, use mock
            if not image_generated:
                image_generated = generate_mock_image(setting, scene_num, image_path)
            
            if image_generated:
                scene['image_url'] = f"/output/images/{image_filename}"
            else:
                scene['image_url'] = None
                log.append(f"Failed to generate image for scene {scene_num}")
            
            # Generate audio - try FastRTC first, fallback to mock
            audio_filename = f"scene_{scene_num}_audio.wav"
            audio_path = os.path.join(audio_output_dir, audio_filename)
            
            audio_generated = False
            if tts_model:
                audio_generated = generate_audio_with_fastrtc(scene_text, audio_path)
                if audio_generated:
                    log.append(f"Generated audio using FastRTC for scene {scene_num}")
                else:
                    log.append(f"Failed to generate audio with FastRTC for scene {scene_num}, using mock")
            
            # If FastRTC failed or not available, use mock
            if not audio_generated:
                audio_generated = generate_mock_audio(scene_text, audio_path)
            
            if audio_generated:
                scene['audio_url'] = f"/output/audio/{audio_filename}"
            else:
                scene['audio_url'] = None
                log.append(f"Failed to generate audio for scene {scene_num}")
            
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
    except Exception as e:
        # Log the error and return a state with the error
        error_state = {
            "story_text": story_text,
            "characters": {},
            "scenes": [],
            "overall_style": None,
            "processing_log": [f"Error processing story: {str(e)}"]
        }
        print(f"Error in process_story: {e}")
        return error_state