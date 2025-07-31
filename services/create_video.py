import os
import asyncio
from moviepy import ImageClip, AudioArrayClip, concatenate_videoclips
from services.create_final_state import create_finalstate, create_finalstate_async
import base64
import io
from PIL import Image
import numpy as np
from io import BytesIO

async def create_video_async(story_text, process_id=None, log_storage=None, api_key=None):
    final_state = await create_finalstate_async(story_text, process_id, log_storage, api_key)
    # Add a small delay to ensure streaming connection is established
    await asyncio.sleep(0.01)
    # -----------------------------------------------------
    
    scene_clips = [] # To store video clips for each scene
    
    print("Starting video creation process...")
    # Force flush logs to ensure they're sent immediately
    import sys
    sys.stdout.flush()
    sys.stderr.flush()
    
    # --- Iterate through scenes and create video clips ---
    if 'scenes' in final_state and isinstance(final_state['scenes'], list):
        for scene in final_state['scenes']:
            scene_num = scene.get('scene_number', 'Unknown')
            image_base64 = scene.get('image_base64')
            audio_array = scene.get('audio_array')
            
            # Skip scenes without required data
            if not image_base64 or audio_array is None:
                print(f"  Warning: Missing image or audio data for scene {scene_num}. Skipping scene.")
                continue
                
            sample_rate, array = audio_array
            print(f"\nProcessing Scene {scene_num}...")
            
            if array.dtype == np.float32:
                if np.max(np.abs(array)) > 1.0:
                    array = array / np.max(np.abs(array))
            
            try:
                # --- Load audio to get duration ---
                audio_clip = AudioArrayClip(np.repeat(array.reshape(-1, 1), 2, axis=1), fps=sample_rate)
                scene_duration = audio_clip.duration
                if scene_duration <= 0:
                    print(f"  Warning: Audio duration is zero or negative for scene {scene_num}. Skipping scene.")
                    audio_clip.close() # Close the clip
                    continue
                print(f"  Audio Duration: {scene_duration:.2f} seconds")
                # Force flush logs to ensure they're sent immediately
                import sys
                sys.stdout.flush()
                sys.stderr.flush()
                
                # --- Create image clip ---
                # Set image duration to match audio duration
                # Yield control to allow event loop to process log streaming
                await asyncio.sleep(0.01)
                
                image = Image.open(BytesIO(image_base64))
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
                # Force flush logs to ensure they're sent immediately
                import sys
                sys.stdout.flush()
                sys.stderr.flush()
                
                # Yield control to allow event loop to process log streaming
                await asyncio.sleep(0.01)
                
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
        # Force flush logs to ensure they're sent immediately
        import sys
        sys.stdout.flush()
        sys.stderr.flush()
        # Yield control to allow event loop to process log streaming
        await asyncio.sleep(0.01)
        try:
            print("Concatenating video clips...")
            # Force flush logs to ensure they're sent immediately
            sys.stdout.flush()
            sys.stderr.flush()
            # Yield control to allow event loop to process log streaming
            await asyncio.sleep(0.01)
            final_clip = concatenate_videoclips(scene_clips, method="compose")
            # --- Cleanup: Close any remaining clips in the list ---
            print("Cleaning up...")
            # Force flush logs to ensure they're sent immediately
            sys.stdout.flush()
            sys.stderr.flush()
            # Yield control to allow event loop to process log streaming
            await asyncio.sleep(0.01)
            for clip in scene_clips:
                if hasattr(clip, 'close'):
                    clip.close()
            print("Video creation process finished.")
            # Force flush logs to ensure they're sent immediately
            sys.stdout.flush()
            sys.stderr.flush()
            # Yield control to allow event loop to process log streaming
            await asyncio.sleep(0.01)
            return final_clip
            
        except Exception as e:
            print(f"Error during concatenation: {e}")
            # Close any remaining clips on error
            for clip in scene_clips:
                if hasattr(clip, 'close'):
                    clip.close()
            raise
    else:
        print("No valid scene clips were created. Final video cannot be generated.")
        # Return a simple black clip as fallback
        from moviepy import ColorClip
        return ColorClip(size=(640, 480), color=(0, 0, 0), duration=1)

def create_video(story_text, process_id=None, log_storage=None, api_key=None):
    final_state = create_finalstate(story_text, process_id, log_storage, api_key)
    # -----------------------------------------------------

    scene_clips = [] # To store video clips for each scene

    print("Starting video creation process...")

    # --- Iterate through scenes and create video clips ---
    if 'scenes' in final_state and isinstance(final_state['scenes'], list):
        for scene in final_state['scenes']:
            scene_num = scene.get('scene_number', 'Unknown')
            image_base64 = scene.get('image_base64')
            audio_array = scene.get('audio_array')
            
            # Skip scenes without required data
            if not image_base64 or audio_array is None:
                print(f"  Warning: Missing image or audio data for scene {scene_num}. Skipping scene.")
                continue
                
            sample_rate, array = audio_array
            print(f"\nProcessing Scene {scene_num}...")
            
            if array.dtype == np.float32:
                if np.max(np.abs(array)) > 1.0:
                    array = array / np.max(np.abs(array))

            try:
                # --- Load audio to get duration ---
                audio_clip = AudioArrayClip(np.repeat(array.reshape(-1, 1), 2, axis=1), fps=sample_rate)
                scene_duration = audio_clip.duration
                if scene_duration <= 0:
                    print(f"  Warning: Audio duration is zero or negative for scene {scene_num}. Skipping scene.")
                    audio_clip.close() # Close the clip
                    continue
                print(f"  Audio Duration: {scene_duration:.2f} seconds")

                # --- Create image clip ---
                # Set image duration to match audio duration

                image = Image.open(BytesIO(image_base64))
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
        # Force flush logs to ensure they're sent immediately
        import sys
        sys.stdout.flush()
        sys.stderr.flush()
        # Yield control to allow event loop to process log streaming
        try:
            print("Concatenating video clips...")
            # Force flush logs to ensure they're sent immediately
            sys.stdout.flush()
            sys.stderr.flush()
            # Yield control to allow event loop to process log streaming
            final_clip = concatenate_videoclips(scene_clips, method="compose")
            # --- Cleanup: Close any remaining clips in the list ---
            print("Cleaning up...")
            # Force flush logs to ensure they're sent immediately
            sys.stdout.flush()
            sys.stderr.flush()
            # Yield control to allow event loop to process log streaming
            for clip in scene_clips:
                if hasattr(clip, 'close'):
                    clip.close()
            print("Video creation process finished.")
            # Force flush logs to ensure they're sent immediately
            sys.stdout.flush()
            sys.stderr.flush()
            # Yield control to allow event loop to process log streaming
            return final_clip
            
        except Exception as e:
            print(f"Error during concatenation: {e}")
            # Close any remaining clips on error
            for clip in scene_clips:
                if hasattr(clip, 'close'):
                    clip.close()
            raise
    else:
        print("No valid scene clips were created. Final video cannot be generated.")
        # Return a simple black clip as fallback
        from moviepy import ColorClip
        return ColorClip(size=(640, 480), color=(0, 0, 0), duration=1)

    
    

    

    