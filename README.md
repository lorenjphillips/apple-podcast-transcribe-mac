# Audio Transcription Script

A Python script that processes URLs from a list and transcribes them using macscribe-like functionality.

## Setup

1. **Create and activate virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install yt-dlp typer pyperclip rich
   ```

3. **For full transcription support (optional):**
   ```bash
   pip install openai-whisper
   ```

## Usage

### Process multiple URLs from a file:
```bash
python process_urls.py urls.txt
```

### Process a single URL:
```bash
python process_urls.py single-url "https://www.youtube.com/watch?v=example"
```

### Options:
- `--model, -m`: Specify transcription model (default: mlx-community/whisper-large-v3-mlx)
- `--output, -o`: Save transcripts to file
- `--clipboard/--no-clipboard`: Copy to clipboard (default: enabled)

### Examples:
```bash
# Process URLs and save to file
python process_urls.py urls.txt --output transcripts.txt

# Process with custom model
python process_urls.py urls.txt --model base

# Process without copying to clipboard
python process_urls.py urls.txt --no-clipboard
```

## URL File Format

Create a text file with one URL per line:
```
# Comments start with #
https://www.youtube.com/watch?v=example1
https://podcasts.apple.com/us/podcast/example/id123456789

# Blank lines are ignored
https://www.youtube.com/watch?v=example2
```

## Features

- **Multi-platform support**: YouTube, Apple Podcasts, and other yt-dlp supported sites
- **Batch processing**: Process multiple URLs from a file
- **Clipboard integration**: Automatically copies transcripts to clipboard
- **Progress tracking**: Shows progress for multiple URL processing
- **Error handling**: Continues processing even if some URLs fail
- **Flexible output**: Save to file or copy to clipboard

## Files

- `process_urls.py`: Main script
- `urls.txt`: Sample URL list file
- `venv/`: Python virtual environment

## Notes

- The script currently uses a placeholder transcription function
- Install `openai-whisper` for actual transcription capabilities
- Audio files are temporarily downloaded and then cleaned up
- Supports all sites that yt-dlp can handle