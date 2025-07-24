# Story Visualizer Web

A web application that transforms short stories into audio-visual experiences using Generative AI technologies.

## Features

- Character analysis and description generation
- Scene segmentation and analysis
- Multiple image generation model support (Google Gemini, OpenAI DALL-E, Stability AI)
- Audio narration using FastRTC TTS
- Final video composition combining images and audio

## Installation

1. Clone the repository
2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Set up your environment variables by copying `.env.example` to `.env` and filling in your API keys:
   ```
   cp .env.example .env
   ```

## Usage

1. Run the application:
   ```
   python main.py
   ```
2. Open your browser and navigate to `http://localhost:8000`
3. Paste your short story into the text area
4. Select your preferred image generation model
5. Click "Process Story" to generate the visualization

## API Endpoints

- `GET /` - Serve the main web interface
- `POST /api/process` - Process a story and generate visualization

## Technologies Used

- FastAPI - Web framework
- LangGraph - Workflow orchestration
- Google Gemini - Text analysis and image generation
- OpenAI DALL-E - Alternative image generation
- FastRTC - Text-to-speech
- MoviePy - Video composition

## Project Structure

```
story-visualizer-web/
├── main.py                 # Main application file
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variables template
├── README.md               # This file
├── config/
│   └── settings.py         # Configuration settings
├── models/
│   └── story.py            # Data models
├── services/
│   └── story_processor.py  # Story processing logic
├── static/                 # Static files (CSS, JS, images)
└── templates/              # HTML templates
```