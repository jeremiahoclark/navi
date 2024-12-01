# Japanese Text Translator

## Overview
This is a desktop application that captures screenshots, detects Japanese text, and provides translations using GPT-4o-mini and text-to-speech functionality.

## Prerequisites
- Python 3.8+
- API Keys:
  - OpenAI API Key
  - Eleven Labs API Key

## Setup

1. Clone the repository
```bash
git clone <repository-url>
cd <repository-name>
```

2. Create a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Create a `.env` file with your API keys
```
OPENAI_API_KEY=your_openai_api_key
ELEVEN_LABS_API_KEY=your_eleven_labs_api_key
```

5. Optional: Install media player
- For macOS: `brew install mpv`
- For Linux: `sudo apt-get install mpv`
- For Windows: Download from https://mpv.io/

## Running the Application
```bash
python app.py
```

## Features
- Automatic screenshot capture and Japanese text detection
- Translation to English
- Text-to-Speech functionality
- Customizable capture interval
- Reference sheet for Hiragana and Katakana

## Dependencies
- PyAutoGUI for screenshot capture
- Pillow for image processing
- OpenAI for text translation
- Eleven Labs for text-to-speech
- Tkinter for GUI

## License
[Add your license information here] 