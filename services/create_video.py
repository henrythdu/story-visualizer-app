import os
from moviepy import ImageClip,AudioArrayClip, concatenate_videoclips
from services.create_final_state import create_finalstate
import base64
import io
from PIL import Image
import numpy as np

def create_video(story_text):
    final_state = create_finalstate(story_text)
    # -----------------------------------------------------

    output_video_filename = "final_story_video.mp4"
    scene_clips = [] # To store video clips for each scene

    print("Starting video creation process...")

    # --- Iterate through scenes and create video clips ---
    if 'scenes' in final_state and isinstance(final_state['scenes'], list):
        for scene in final_state['scenes']:
            scene_num = scene.get('scene_number', 'Unknown')
            image_base64 = scene.get('image_base64')
            audio_array = scene.get('audio_array')
            sample_rate, array = audio_array
            print(f"\nProcessing Scene {scene_num}...")
            if array.dtype == np.float32:
                if np.max(np.abs(array)) > 1.0:
                    array = array / np.max(np.abs(array))

            try:
                # --- Load audio to get duration ---
                audio_clip = AudioArrayClip(np.repeat(array.reshape(-1, 1), 2, axis=1),fps=sample_rate)
                scene_duration = audio_clip.duration
                if scene_duration <= 0:
                    print(f"  Warning: Audio duration is zero or negative for scene {scene_num}. Skipping scene.")
                    audio_clip.close() # Close the clip
                    continue
                print(f"  Audio Duration: {scene_duration:.2f} seconds")

                # --- Create image clip ---
                # Set image duration to match audio duration

            
                image = Image.open(io.BytesIO(image_base64))
                # Convert to RGB if necessary (MoviePy works best with RGB)
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                # Convert PIL image to numpy array
                image_array = np.array(image)
                img_clip = ImageClip(image_array).with_duration(scene_duration)

                # --- Set audio for the image clip ---
                video_clip = img_clip.with_audio(audio_clip)

                # Add the completed scene clip to our list
                scene_clips.append(video_clip)
                print(f"  Successfully created video clip for scene {scene_num}.")

            except Exception as e:
                print(f"  Error processing scene {scene_num}: {e}")
                # Ensure clips are closed if an error occurs mid-processing
                if 'audio_clip' in locals() and hasattr(audio_clip, 'close'):
                    audio_clip.close()
                if 'img_clip' in locals() and hasattr(img_clip, 'close'):
                    img_clip.close()
                if 'video_clip' in locals() and hasattr(video_clip, 'close'):
                    video_clip.close()


    else:
        print("Error: 'scenes' key not found or is not a list in final_state.")

    # --- Concatenate all scene clips ---
    if scene_clips:
        print(f"\nConcatenating {len(scene_clips)} scene clips...")
        try:
            final_clip = concatenate_videoclips(scene_clips, method="compose")
            # --- Cleanup: Close any remaining clips in the list ---
            print("Cleaning up...")
            for clip in scene_clips:
                if hasattr(clip, 'close'):
                    clip.close()
            print("Video creation process finished.")
            return final_clip
            
        except Exception as e:
            print(f"Error during concatenation or writing final video: {e}")
    else:
        print("No valid scene clips were created. Final video cannot be generated.")

    
    

    

    