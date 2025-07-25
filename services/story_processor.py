import operator
import os
from typing import Optional
import time # Added for delays gemini-2.0-flash has rate limits of 10 per min

# Langchain/LangGraph specific imports
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI # For text generation
from langchain_community.chat_models import ChatOpenAI
from langgraph.graph import StateGraph, END

# Google genai
from google import genai
from google.genai import types

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

def initialize_models(api_key: Optional[str] = None):
    """
    Initialize the models with provided API configuration
    """
    global llm, genai_client, tts_model
    
    # Use provided API key or fallback to settings
    google_api_key = api_key or settings.GOOGLE_API_KEY
    image_model = "gemini-2.0-flash-exp-image-generation"
    openrouter_api_key = settings.OPENROUTER_API_KEY
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
    
    # Initialize LLM model
    if google_api_key and GOOGLE_GENAI_AVAILABLE:
        try:
            os.environ["GOOGLE_API_KEY"] = google_api_key
            llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.7)
            # llm = ChatOpenAI(

            #                 openai_api_key=openrouter_api_key,

            #                 openai_api_base="https://openrouter.ai/api/v1",

            #                 model_name="google/gemini-2.5-pro-exp-03-25"
            #                 )
            
            print(f"Google GenAI LLM initialized with model: gemini-2.0-flash")
        except Exception as e:
            print(f"Error initializing Google GenAI LLM: {e}")
            llm = None
    else:
        llm = None
        if not google_api_key:
            print("⚠️ Google API key not provided.")
      

    # Initialize FastRTC TTS model
    if FASTRTC_AVAILABLE:
        try:
            tts_model = get_tts_model()
            print("FastRTC TTS model initialized")
        except Exception as e:
            print(f"Error initializing FastRTC TTS model: {e}")
            tts_model = None
    else:
        tts_model = None
        print("⚠️ FastRTC library not available.")

# --- 2. Define Nodes (Functions) ---

def read_story(state: StoryAnalysisState) -> StoryAnalysisState:
    """
    Node to load the story text into the state.
    """
    log = state.get("processing_log", [])
    log.append("Reading story...")
    print("--- Reading Story ---")
    return {"processing_log": log}

def analyze_characters(state: StoryAnalysisState) -> StoryAnalysisState:
    """
    Node to identify characters and their initial descriptions using Gemini (via Langchain).
    """
    log = state.get("processing_log", [])
    log.append("Analyzing characters using Gemini...")
    print("--- Analyzing Characters (using Gemini) ---")
    story = state["story_text"]
    characters_found = {}


    prompt_template = ChatPromptTemplate.from_messages([
        ("system", """You are an expert literary analyst. Your task is to read the provided story text and identify all named characters.
For each character, extract any description of their appearance, or notable features mentioned directly in the text.
Output the results as a JSON object where keys are the character names and values are dictionaries containing a single key "description" with the extracted description as a string.
If no description is found for a character, set the value of "description" to null or an empty string.

Example JSON output format:
{{
  "Character Name 1": {{"description": "Description found in text."}},
  "Character Name 2": {{"description": null}}
}}
"""),
        ("human", "Please analyze the following story text:\n\n{story_text}")
    ])
    parser = JsonOutputParser()
    chain = prompt_template | llm | parser

    try:
        response = chain.invoke({"story_text": story})
        characters_found = response
        # Ensure description is always a string (replace null with empty string if needed)
        for char, details in characters_found.items():
            if details is not None and details.get("description") is None:
                 characters_found[char]["description"] = ""
            # Handle cases where the character value itself might be None from JSON
            elif details is None:
                 characters_found[char] = {"description": ""}
        log.append(f"Successfully analyzed characters. Found: {list(characters_found.keys())}")
        print(f"Found characters: {characters_found}")
    except Exception as e:
        log.append(f"Error analyzing characters: {e}")
        print(f"Error during character analysis: {e}")

    return {"characters": characters_found, "processing_log": log}


def generate_missing_descriptions(state: StoryAnalysisState) -> StoryAnalysisState:
    """
    Node to generate descriptions for characters identified without one using Gemini (via Langchain).
    """
    log = state.get("processing_log", [])
    log.append("Checking for and generating missing descriptions using Gemini...")
    print("--- Generating Missing Descriptions (using Gemini) ---")
    characters = state.get("characters", {})
    story = state["story_text"]
    updated_characters = characters.copy()


    prompt_template = ChatPromptTemplate.from_messages([
        ("system", """You are a creative character designer. Based on the character's name and the provided story context, generate a brief, plausible physical description (appearance, clothing, general impression) for the character.
Focus on visual details suitable for image generation later.
Output ONLY the generated description as a plain string."""),
        ("human", "Generate a description for the character '{character_name}' based on this story context:\n\n{story_context}")
    ])
    parser = StrOutputParser()
    chain = prompt_template | llm | parser

    characters_to_generate = []
    if isinstance(characters, dict):
        for name, details in characters.items():
            # Check if details is a dict and if description is missing/empty
            if isinstance(details, dict) and not details.get("description", "").strip():
                characters_to_generate.append(name)
            # Handle cases where the character entry might not be a dict (e.g., due to parsing error)
            elif not isinstance(details, dict):
                 log.append(f"Skipping description generation for '{name}' due to unexpected format: {details}")
                 print(f"Warning: Skipping description generation for '{name}' due to unexpected format.")
                 # Ensure the entry is a dict for consistency, even if description remains missing
                 updated_characters[name] = {"description": ""}


    if not characters_to_generate:
        log.append("No missing descriptions to generate.")
        print("No missing descriptions to generate.")
        # Ensure the returned state always includes the characters dict
        return {"characters": updated_characters, "processing_log": log}

    print(f"Attempting to generate descriptions for: {', '.join(characters_to_generate)}")
    for name in characters_to_generate:
        time.sleep(8) #Gemini-2.0-flash has rate limit of 10 per minute
        try:
            # Invoke the chain
            generated_desc = chain.invoke({
                "character_name": name,
                "story_context": story # Provide the full story as context
            })
            # Ensure the character exists in updated_characters before assigning
            if name not in updated_characters:
                 updated_characters[name] = {} # Initialize if somehow missing
            updated_characters[name]["description"] = generated_desc.strip()
            log.append(f"Successfully generated description for {name}.")
            print(f"Generated description for {name}: {generated_desc.strip()}")
        except Exception as e:
            log.append(f"Error generating description for {name}: {e}")
            print(f"Error generating description for {name}: {e}")
            # Optionally set a default error description
            if name not in updated_characters:
                 updated_characters[name] = {}
            updated_characters[name]["description"] = "Error generating description."

    return {"characters": updated_characters, "processing_log": log}


def analyze_scenes(state: StoryAnalysisState) -> StoryAnalysisState:
    """
    Node to break the story into scenes and extract details for each using Gemini (via Langchain).
    """
    log = state.get("processing_log", [])
    log.append("Analyzing scenes using Gemini...")
    print("--- Analyzing Scenes (using Gemini) ---")
    story = state["story_text"]
    character_names = list(state.get("characters", {}).keys())
    scenes_found = []

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", """You are a skilled screenwriter and story analyst. Your task is to read the provided story text and divide it into logical scenes based on changes in location, time, or main character focus.

For each scene you identify, provide the following details:
1.  `scene_number`: An integer starting from 1.
2.  `scene_text`: A full text from the scene directly from the story.
3.  `summary`: A brief 1-2 sentence summary of the main action or content of the scene.
4.  `setting`: A short description of the scene's location and environment (e.g., 'sunny river bank', 'dark forest path', 'inside a rabbit hole').
5.  `characters_present`: A list of names of the characters who are actively present in the scene. Use the provided list of known character names: {character_list}. If other characters seem present, include their names too.
6.  `tone`: A single word or short phrase describing the overall mood or tone of the scene (e.g., 'calm', 'curious', 'frantic', 'mysterious', 'tense', 'confusing').

Output the results as a JSON list, where each element in the list is an object representing a scene with the keys 'scene_number', 'scene_text', 'summary', 'setting', 'characters_present', and 'tone'.

Example JSON output format:
[
  {{
    "scene_number": 1,
    "scene_text": "A wakes up to a new day in his tiny and messy bedroom, but A feels refresh, looking forward to go on this adventures.",
    "summary": "Character A wakes up and prepares for their journey.",
    "setting": "Small, cluttered bedroom",
    "characters_present": ["Character A"],
    "tone": "calm"
  }},
  {{
    "scene_number": 2,
    "scene_text": "A was wandering through the forest, the sun shinning through the leaves. A enjoyed his time in the wood when he ran into B, B is supposed to be sick.",
    "summary": "Character A meets Character B while walking through the forest.",
    "setting": "Sun-dappled forest path",
    "characters_present": ["Character A", "Character B"],
    "tone": "curious"
  }}
]
"""),
        ("human", "Please analyze the following story text and identify the scenes:\n\n{story_text}\n\nKnown character names: {character_list_str}")
    ])
    parser = JsonOutputParser()
    chain = prompt_template | llm | parser

    try:
        response = chain.invoke({
            "story_text": story,
            "character_list": character_names,
            "character_list_str": ", ".join(character_names)
        })
        # Initialize added fields
        scenes_found = []
        for scene_data in response:
             # Ensure basic structure even if LLM hallucinates extra fields
             validated_scene_data = {
                 'scene_number': scene_data.get('scene_number'),
                 'scene_text': scene_data.get('scene_text'),
                 'summary': scene_data.get('summary'),
                 'setting': scene_data.get('setting'),
                 'characters_present': scene_data.get('characters_present', []),
                 'tone': scene_data.get('tone'),
                 'image_prompt': None,
                 'image_base64': None,
                 'audio_array': None
             }
             scenes_found.append(validated_scene_data)


        log.append(f"Successfully analyzed scenes. Found {len(scenes_found)} scenes.")
        print(f"Found {len(scenes_found)} scenes.")

    except Exception as e:
        log.append(f"Error analyzing scenes: {e}")
        print(f"Error during scene analysis: {e}")
        scenes_found = [] # Ensure it's an empty list on error

    return {"scenes": scenes_found, "processing_log": log}


def determine_overall_style(state: StoryAnalysisState) -> StoryAnalysisState:
    """
    Node to determine an overall visual style based on the story text using Gemini for consistent style for image generation.
    """
    log = state.get("processing_log", [])
    log.append("Determining overall visual style using Gemini...")
    print("--- Determining Overall Visual Style (using Gemini) ---")
    story = state["story_text"]
    suggested_style = None # Initialize

    # Prompt to suggest a style
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", """You are an expert art director. Based on the overall tone, genre, setting, and content of the following story, suggest a concise visual style descriptor suitable for guiding an image generation model.
Examples: 'children's book illustration', 'dark fantasy oil painting', 'realistic sci-fi render', 'vintage cartoon style', 'photorealistic, cinematic lighting'.
Output ONLY the suggested style descriptor string, prefixed with a space (e.g., ' children's book illustration')."""),
        ("human", "Determine a visual style for this story:\n\n{story_text}")
    ])

    parser = StrOutputParser()
    chain = prompt_template | llm | parser

    try:
        # Invoke the chain with the story text
        suggested_style = chain.invoke({"story_text": story}).strip()
        # Basic validation: ensure it starts with a space
        if suggested_style and not suggested_style.startswith(" "):
             suggested_style = " " + suggested_style # Add prefix if missing

        log.append(f"Suggested overall style: '{suggested_style}'")
        print(f"Suggested overall style: '{suggested_style}'")

    except Exception as e:
        log.append(f"Error determining overall style: {e}")
        print(f"Error determining overall style: {e}")
        suggested_style = " illustration" # Fallback style on error

    # Ensure a fallback style if suggestion is empty or just the prefix
    if not suggested_style or suggested_style == " ":
        suggested_style = " illustration" # Default fallback style
        log.append(f"Using fallback style: '{suggested_style}'")
        print(f"Using fallback style: '{suggested_style}'")


    return {"overall_style": suggested_style, "processing_log": log}


def generate_image_prompts(state: StoryAnalysisState) -> StoryAnalysisState:
    """
    Node to generate image prompts for each scene using Gemini (via Langchain),
    including descriptions of characters present and adding the determined overall style descriptor.
    """
    log = state.get("processing_log", [])
    log.append("Generating image prompts using Gemini...")
    print("--- Generating Image Prompts (using Gemini) ---")
    scenes = state.get("scenes", [])
    characters_info = state.get("characters", {})
    # Get the determined overall style from the state
    overall_style = state.get("overall_style")
    updated_scenes = []

    if not llm:
        log.append("LLM not available. Skipping image prompt generation.")
        print("LLM not available. Skipping image prompt generation.")
        return {"scenes": scenes, "processing_log": log}

    # Use a default style if none was determined or passed
    if not overall_style:
        overall_style = " illustration" # Default fallback style
        log.append(f"Overall style not found in state, using fallback: '{overall_style}'")
        print(f"Overall style not found in state, using fallback: '{overall_style}'")

    print(f"Using overall style for prompts: '{overall_style}'")

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", """You are an expert prompt engineer for text-to-image models.
Based on the provided scene details, create a concise yet descriptive prompt suitable for generating an image.
The prompt should capture the essence of the scene: the environment, characters (incorporating their descriptions), actions, and mood/tone.
Focus on visual elements. Output ONLY the generated prompt as a plain string.
"""),
        ("human", """Generate an image prompt for the following scene:
Scene Number: {scene_number}
Summary: {summary}
Setting: {setting}
Characters Present: {characters_present}
Relevant Character Descriptions:
{relevant_character_descriptions}
Tone: {tone}""")
    ])

    parser = StrOutputParser()
    chain = prompt_template | llm | parser

    for scene in scenes:
        scene_num = scene.get('scene_number', 'N/A')
        try:
            present_char_names = scene.get('characters_present', [])
            relevant_descriptions_list = []
            if isinstance(characters_info, dict):
                for name in present_char_names:
                    char_data = characters_info.get(name)
                    if isinstance(char_data, dict):
                        description = char_data.get('description', '').strip()
                        if description:
                            relevant_descriptions_list.append(f"- {name}: {description}")
                        else:
                            relevant_descriptions_list.append(f"- {name}: (No specific description provided)")
                    else:
                         relevant_descriptions_list.append(f"- {name}: (Character data missing)")

            if not relevant_descriptions_list:
                 relevant_desc_text = "None specific to this scene."
            else:
                 relevant_desc_text = "\n".join(relevant_descriptions_list)

            # Get the base content prompt from the LLM
            image_prompt_content = chain.invoke({
                "scene_number": scene_num,
                "summary": scene.get('summary', ''),
                "setting": scene.get('setting', ''),
                "characters_present": ", ".join(present_char_names) if present_char_names else "None",
                "relevant_character_descriptions": relevant_desc_text,
                "tone": scene.get('tone', '')
            })

            # Append the determined overall_style
            final_image_prompt = f"{image_prompt_content.strip()}. In the following style {overall_style}"

            # Store the final prompt (content + style)
            scene['image_prompt'] = final_image_prompt
            log.append(f"Generated image prompt for scene {scene_num}.")
            # Print the final prompt being used
            print(f"Generated image prompt for scene {scene_num}: {final_image_prompt}")

        except Exception as e:
            log.append(f"Error generating image prompt for scene {scene_num}: {e}")
            print(f"Error generating image prompt for scene {scene_num}: {e}")
            scene['image_prompt'] = "Error generating image prompt."

        updated_scenes.append(scene)

    return {"scenes": updated_scenes, "processing_log": log}


def generate_images_for_scenes(state: StoryAnalysisState) -> StoryAnalysisState:
    """
    Node to generate images based on prompts using the Google GenAI API
    and save them locally.
    """
    log = state.get("processing_log", [])
    log.append("Generating images using Google GenAI...")
    print("--- Generating Images (using Google GenAI) ---")
    scenes = state.get("scenes", [])
    updated_scenes = []

    # Ensure the GenAI client was initialized
    if not genai_client:
         log.append("Google GenAI Image Generation client not available. Skipping image generation.")
         print("⚠️ Google GenAI Image Generation client not available. Skipping image generation.")
         # Add existing scenes back without image URLs
         for scene in scenes:
             scene['image_base64'] = None
             updated_scenes.append(scene)
         return {"scenes": updated_scenes, "processing_log": log}


    for scene in scenes:
        image_prompt = scene.get('image_prompt')
        scene_num = scene.get('scene_number', 'N/A')
        generated_image_base64  = None # Initialize path for this scene

        if image_prompt and "Error" not in image_prompt:
            print(f"Attempting image generation for scene {scene_num}...")
            try:
                # Use the prompt directly as contents
                contents = image_prompt

                # Call the Google GenAI API for image generation using client.models.generate_content
                response = genai_client.models.generate_content(
                            model="gemini-2.0-flash-exp-image-generation", # Specific model for image generation
                            contents=contents,
                            config=types.GenerateContentConfig(
                              response_modalities=['Text', 'Image'], # Both Text and Image as per https://ai.google.dev/gemini-api/docs/image-generation#gemini
                            )
                        )
                time.sleep(8) #Gemini-2.0-flash has rate limit of 10 per minute
                # Process the response to find and save the image
                image_saved = False
                # Check if candidates exist and have content parts
                if response.candidates and hasattr(response.candidates[0], 'content') and hasattr(response.candidates[0].content, 'parts'):
                    for part in response.candidates[0].content.parts:
                        # Check if the part has inline_data and if that data has a 'data' attribute
                        if hasattr(part, 'inline_data') and hasattr(part.inline_data, 'data'):
                            print(f"Image data received for scene {scene_num}.")
                            image_data = part.inline_data.data
                            try:
                            
                               
                                # Save the image
                                generated_image_base64 = image_data
                                print(f"Saved image for scene {scene_num}")
                                log.append(f"Generated and saved image for scene {scene_num}")
                                image_saved = True
                                break # Assuming only one image part per scene
                            except Exception as img_err:
                                log.append(f"Error processing/saving image data for scene {scene_num}: {img_err}")
                                print(f"Error processing/saving image data for scene {scene_num}: {img_err}")
                                # Keep generated_image_base64 as None

                if not image_saved:
                     log.append(f"No valid image data found or saved in response for scene {scene_num}.")
                     print(f"Warning: No valid image data found or saved in API response for scene {scene_num}.")

            except Exception as e:
                log.append(f"Error during image generation API call for scene {scene_num}: {e}")
                print(f"Error during image generation API call for scene {scene_num}: {e}")
                # Keep generated_image_base64 as None

        else:
            log.append(f"Skipping image generation for scene {scene_num} due to missing or error in prompt.")
            print(f"Skipping image generation for scene {scene_num} (invalid prompt).")
            # Keep generated_image_base64 as None

        # Update the scene info with the file path (or None if failed)
        scene['image_base64'] = generated_image_base64 
        updated_scenes.append(scene)

    return {"scenes": updated_scenes, "processing_log": log}

# ---  Audio Generation ---


def generate_audio_for_scenes(state: StoryAnalysisState) -> StoryAnalysisState:
    """
    Node to generate audio for a scene
    """
    log = state.get("processing_log", [])
    log.append("Generating audio ...")
    print("--- Generating Audio ---")
    scenes = state.get("scenes", [])
    updated_scenes = []

    # Create an output directory if it doesn't exist

    for scene in scenes:
        scene_text = scene.get('scene_text')
        scene_num = scene.get('scene_number', 'N/A')
        generated_audio_array = None # Initialize path for this scene

        if scene_text:
            print(f"Audio generation for scene {scene_num}...")
            try:
                
                generated_audio_array = tts_model.tts(scene_text)    
                

                # ==========================================================

                print(f"Saving audio for scene {scene_num}")
                log.append(f"Audio generation for scene {scene_num}.")

            except Exception as e:
                log.append(f"Error during audio generation for scene {scene_num}: {e}")
                print(f"Error during audio generation for scene {scene_num}: {e}")
                generated_audio_array = None # Indicate failure
        else:
            log.append(f"Skipping audio generation for scene {scene_num} due to missing scene text.")
            print(f"Skipping audio generation for scene {scene_num} (missing text).")
            generated_audio_array = None # Ensure path is None if text is missing

        # Update the scene info with the file path (or None if failed)
        scene['audio_array'] = generated_audio_array
        updated_scenes.append(scene)

    return {"scenes": updated_scenes, "processing_log": log}

def create_graph():
    initialize_models()
    workflow = StateGraph(StoryAnalysisState)
    # Add the nodes
    workflow.add_node("read_story", read_story)
    workflow.add_node("analyze_characters", analyze_characters)
    workflow.add_node("generate_descriptions", generate_missing_descriptions)
    workflow.add_node("analyze_scenes", analyze_scenes)
    workflow.add_node("determine_style", determine_overall_style)
    workflow.add_node("generate_image_prompts", generate_image_prompts)
    workflow.add_node("generate_images", generate_images_for_scenes)
    workflow.add_node("generate_audio", generate_audio_for_scenes) 

    # Define the edges (flow)
    workflow.set_entry_point("read_story")
    workflow.add_edge("read_story", "analyze_characters")
    workflow.add_edge("analyze_characters", "generate_descriptions")
    workflow.add_edge("generate_descriptions", "analyze_scenes")
    workflow.add_edge("analyze_scenes", "determine_style")
    workflow.add_edge("determine_style", "generate_image_prompts")
    workflow.add_edge("generate_image_prompts", "generate_images")
    workflow.add_edge("generate_images", "generate_audio") 
    workflow.add_edge("generate_audio", END) 

    # Compile the graph
    graph = workflow.compile()
    return graph