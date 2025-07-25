# Story Visualizer Web

A web application that transforms short stories into audio-visual experiences using Generative AI technologies.

## Features

- Character analysis and description generation
- Scene segmentation and analysis
- Image generation using Google GenAI
- Audio narration using FastRTC TTS
- Final video composition combining images and audio with MoviePy
- Dark mode UI with responsive design
- Real-time processing logs

## Prerequisites

- Python 3.8 or higher
- Google API Key for Gemini models
- FastRTC API access (for text-to-speech)

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd story-visualizer-web
   ```

2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up your environment variables:
   Create a `.env` file in the project root with the following variables:
   ```env
   GOOGLE_API_KEY=your_google_api_key_here
   ```

## Usage

1. Run the application:
   ```bash
   python main.py
   ```

2. Open your browser and navigate to `http://localhost:8000`

3. Paste your short story into the text area

4. Click "Visualize Story" to generate the visualization

5. Watch the real-time processing logs in the sidebar

6. Once processing is complete, view and download your generated video

## Demo

Check out our demo video to see the Story Visualizer in action:

<video src="assets/Demo_visualizer)](assets/Demo_visualizer.mp4" width="300" />


## API Endpoints

- `GET /` - Serve the main web interface
- `POST /api/process` - Process a story and generate visualization
- `GET /api/video/{video_id}` - Stream the generated video
- `GET /api/video/by_process/{process_id}` - Check if video processing is complete
- `GET /api/logs/{process_id}` - Stream processing logs

## Technologies Used

- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [LangGraph](https://langchain-ai.github.io/langgraph/) - Workflow orchestration
- [Google GenAI](https://ai.google.dev/) - Text analysis and image generation
- [FastRTC](https://fastrtc.ai/) - Text-to-speech
- [MoviePy](https://zulko.github.io/moviepy/) - Video composition
- [Bootstrap 5](https://getbootstrap.com/) - Frontend styling

## Project Structure

```
story-visualizer-web/
├── main.py                 # Main application file
├── requirements.txt        # Python dependencies
├── README.md               # This file
├── config/
│   └── settings.py         # Configuration settings
├── models/
│   └── story.py            # Data models
├── services/
│   ├── create_final_state.py  # Final state creation
│   ├── create_video.py        # Video creation with MoviePy
│   └── story_processor.py     # Story processing logic
├── static/                 # Static files (CSS, JS, images)
├── templates/              # HTML templates
│   └── index.html          # Main HTML template
└── assets/                 # Demo and documentation assets
    └── Demo_visualizer     # Demo video
```

## How It Works

1. **Story Analysis**: The application uses Google's Gemini model to analyze the story text, identifying characters and breaking the story into scenes.

2. **Character Description**: For each character, the application either extracts descriptions from the text or generates them using the LLM.

3. **Scene Analysis**: Each scene is analyzed for setting, characters present, and overall tone.

4. **Visual Style**: The application determines an overall visual style for consistent image generation.

5. **Image Generation**: Using Google's image generation model, the application creates images for each scene based on detailed prompts.

6. **Audio Generation**: FastRTC's text-to-speech converts each scene's text into audio.

7. **Video Composition**: MoviePy combines the generated images and audio into a final video.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.