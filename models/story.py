from typing import List, Dict, Optional, Any
from typing_extensions import TypedDict

class SceneInfo(TypedDict):
    scene_number: int
    scene_text: str
    summary: str
    setting: str
    characters_present: List[str]
    tone: str
    image_prompt: Optional[str]
    image_base64: Optional[str]
    audio_array: Optional[str]

class StoryAnalysisState(TypedDict):
    story_text: str
    characters: Dict[str, Dict[str, str]]
    scenes: List[SceneInfo]
    overall_style: Optional[str]
    processing_log: List[str]
