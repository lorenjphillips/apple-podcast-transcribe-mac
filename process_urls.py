#!/usr/bin/env python3
"""
Script to process a list of URLs using macscribe-like functionality.
Reads URLs from a file and processes them for transcription.
"""

import os
import sys
import subprocess
import tempfile
import re
from pathlib import Path
from typing import List, Optional, Tuple
import typer
import pyperclip
import yt_dlp
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

app = typer.Typer()
console = Console()

def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing invalid characters."""
    # Remove invalid characters and replace with underscores
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove multiple underscores
    filename = re.sub(r'_+', '_', filename)
    # Remove leading/trailing underscores and dots
    filename = filename.strip('_.')
    return filename

def download_audio(url: str, output_dir: str) -> Optional[Tuple[str, str]]:
    """Download audio from URL using yt-dlp. Returns (audio_file_path, title)."""
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        'extractaudio': True,
        'audioformat': 'mp3',
        'audioquality': '192K',
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'Unknown')
            filename = ydl.prepare_filename(info)
            # Change extension to mp3 since we're extracting audio
            audio_file = os.path.splitext(filename)[0] + '.mp3'
            final_audio_file = audio_file if os.path.exists(audio_file) else filename
            return (final_audio_file, title) if final_audio_file else None
    except Exception as e:
        console.print(f"[red]Error downloading {url}: {e}[/red]")
        return None

def transcribe_audio(audio_file: str, model: str = "base") -> str:
    """Transcribe audio using whisper or placeholder."""
    try:
        import whisper
        console.print(f"[blue]Transcribing with Whisper model: {model}[/blue]")
        
        # Load whisper model
        whisper_model = whisper.load_model(model)
        
        # Transcribe
        result = whisper_model.transcribe(audio_file)
        return result["text"].strip()
        
    except ImportError:
        console.print(f"[yellow]Note: Using placeholder transcription for {audio_file}[/yellow]")
        console.print("[yellow]To enable real transcription, install: pip install openai-whisper[/yellow]")
        
        # Return a placeholder transcript
        return f"[PLACEHOLDER TRANSCRIPT] Audio file: {os.path.basename(audio_file)}\nThis would contain the actual transcription when whisper is properly installed."
    except Exception as e:
        console.print(f"[red]Error transcribing audio: {e}[/red]")
        return f"[ERROR] Failed to transcribe: {str(e)}"

def save_transcript_to_file(transcript: str, title: str, url: str) -> str:
    """Save transcript to transcripts folder with episode name."""
    # Create transcripts directory if it doesn't exist
    transcripts_dir = Path("transcripts")
    transcripts_dir.mkdir(exist_ok=True)
    
    # Sanitize title for filename
    filename = sanitize_filename(title)
    if not filename or filename == "Unknown":
        filename = f"transcript_{len(list(transcripts_dir.glob('*.txt'))) + 1}"
    
    # Ensure .txt extension
    if not filename.endswith('.txt'):
        filename += '.txt'
    
    # Create full path
    filepath = transcripts_dir / filename
    
    # Add counter if file exists
    counter = 1
    original_filepath = filepath
    while filepath.exists():
        name_without_ext = original_filepath.stem
        filepath = transcripts_dir / f"{name_without_ext}_{counter}.txt"
        counter += 1
    
    # Prepare content with metadata
    content = f"""Episode: {title}
URL: {url}
Transcribed: {Path().cwd()}

{'-' * 80}

{transcript}"""
    
    # Save to file
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        console.print(f"[green]Transcript saved to: {filepath}[/green]")
        return str(filepath)
    except Exception as e:
        console.print(f"[red]Error saving transcript: {e}[/red]")
        return ""

def process_url(url: str, model: str = "base") -> Optional[Tuple[str, str, str]]:
    """Process a single URL - download audio and transcribe. Returns (transcript, title, filepath)."""
    console.print(f"[blue]Processing: {url}[/blue]")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Download audio
        download_result = download_audio(url, temp_dir)
        if not download_result:
            return None
        
        audio_file, title = download_result
        console.print(f"[green]Downloaded: {os.path.basename(audio_file)}[/green]")
        
        # Transcribe audio
        transcript = transcribe_audio(audio_file, model)
        
        # Save transcript to file
        filepath = save_transcript_to_file(transcript, title, url)
        
        return (transcript, title, filepath)

def read_urls_from_file(file_path: str) -> List[str]:
    """Read URLs from a text file, one per line."""
    try:
        with open(file_path, 'r') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        return urls
    except FileNotFoundError:
        console.print(f"[red]Error: File {file_path} not found[/red]")
        return []
    except Exception as e:
        console.print(f"[red]Error reading file: {e}[/red]")
        return []

@app.command()
def process_urls(
    urls_file: str = typer.Argument(..., help="Path to file containing URLs (one per line)"),
    model: str = typer.Option("base", "--model", "-m", help="Whisper model to use (tiny, base, small, medium, large)"),
    copy_to_clipboard: bool = typer.Option(True, "--clipboard/--no-clipboard", help="Copy transcripts to clipboard")
):
    """Process multiple URLs from a file and transcribe them."""
    
    if not os.path.exists(urls_file):
        console.print(f"[red]Error: URLs file '{urls_file}' not found[/red]")
        raise typer.Exit(1)
    
    urls = read_urls_from_file(urls_file)
    if not urls:
        console.print("[red]No valid URLs found in file[/red]")
        raise typer.Exit(1)
    
    console.print(f"[blue]Found {len(urls)} URLs to process[/blue]")
    
    all_transcripts = []
    processed_files = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        
        for i, url in enumerate(urls, 1):
            task = progress.add_task(f"Processing URL {i}/{len(urls)}", total=None)
            
            result = process_url(url, model)
            if result:
                transcript, title, filepath = result
                all_transcripts.append(f"Episode: {title}\nURL: {url}\nFile: {filepath}\n{'-'*80}\n{transcript}")
                processed_files.append(filepath)
                console.print(f"[green]✓ Completed {i}/{len(urls)}: {title}[/green]")
            else:
                console.print(f"[red]✗ Failed to process: {url}[/red]")
            
            progress.remove_task(task)
    
    if all_transcripts:
        combined_transcript = "\n\n".join(all_transcripts)
        
        # Copy to clipboard if requested
        if copy_to_clipboard:
            try:
                pyperclip.copy(combined_transcript)
                console.print("[green]All transcripts copied to clipboard![/green]")
            except Exception as e:
                console.print(f"[yellow]Could not copy to clipboard: {e}[/yellow]")
        
        console.print(f"[blue]Processed {len(all_transcripts)} URLs successfully[/blue]")
        console.print(f"[blue]Transcript files saved in: transcripts/[/blue]")
        for filepath in processed_files:
            if filepath:
                console.print(f"  - {filepath}")
    else:
        console.print("[red]No transcripts were generated[/red]")

@app.command()
def single_url(
    url: str = typer.Argument(..., help="URL to process"),
    model: str = typer.Option("base", "--model", "-m", help="Whisper model to use (tiny, base, small, medium, large)")
):
    """Process a single URL (similar to original macscribe)."""
    result = process_url(url, model)
    
    if result:
        transcript, title, filepath = result
        try:
            pyperclip.copy(transcript)
            console.print("[green]Transcript copied to clipboard![/green]")
            console.print(f"[green]Transcript saved to: {filepath}[/green]")
        except Exception as e:
            console.print(f"[yellow]Could not copy to clipboard: {e}[/yellow]")
            console.print("\n" + transcript)
    else:
        console.print("[red]Failed to process URL[/red]")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()