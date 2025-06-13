#!/usr/bin/env python3
"""
Apple Podcasts URL Scraper

A comprehensive tool to extract episode URLs from any Apple Podcasts page.
Supports multiple extraction methods and can handle large podcasts with hundreds of episodes.

Features:
- iTunes API for recent episodes (up to 200)
- Search API for older episodes
- URL validation
- Flexible output options
- Rate limiting protection

Usage:
    python apple_podcast_scraper.py "https://podcasts.apple.com/us/podcast/founders/id1141877104"
    python apple_podcast_scraper.py --help
"""

import requests
import re
import time
from typing import List, Optional
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

app = typer.Typer(help="Extract episode URLs from Apple Podcasts")
console = Console()

def extract_podcast_id(url: str) -> Optional[str]:
    """Extract podcast ID from Apple Podcasts URL."""
    match = re.search(r'/id(\d+)', url)
    return match.group(1) if match else None

def get_recent_episodes_from_api(podcast_id: str) -> List[str]:
    """
    Get recent episodes using Apple's iTunes API.
    Limited to ~200 most recent episodes.
    """
    base_url = "https://itunes.apple.com/lookup"
    params = {
        'id': podcast_id,
        'media': 'podcast',
        'entity': 'podcastEpisode',
        'limit': 200  # iTunes API maximum
    }
    
    try:
        console.print(f"[blue]Fetching recent episodes from iTunes API...[/blue]")
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        results = data.get('results', [])
        
        # Skip the first result which is podcast info, rest are episodes
        episodes = results[1:] if len(results) > 1 else []
        
        episode_urls = []
        for episode in episodes:
            episode_id = episode.get('trackId')
            episode_name = episode.get('trackName', '').replace(' ', '-').lower()
            # Sanitize episode name for URL
            episode_name = re.sub(r'[^a-z0-9-]', '-', episode_name)
            episode_name = re.sub(r'-+', '-', episode_name).strip('-')
            
            if episode_id:
                episode_url = f"https://podcasts.apple.com/us/podcast/{episode_name}/id{podcast_id}?i={episode_id}"
                episode_urls.append(episode_url)
        
        console.print(f"[green]Found {len(episode_urls)} recent episodes[/green]")
        return episode_urls
        
    except requests.RequestException as e:
        console.print(f"[red]Error fetching from iTunes API: {e}[/red]")
        return []
    except Exception as e:
        console.print(f"[red]Error parsing iTunes API response: {e}[/red]")
        return []

def search_for_older_episodes(podcast_id: str, existing_urls: List[str], 
                            start_episode: int = 1, end_episode: int = 200,
                            max_requests: int = 50) -> List[str]:
    """
    Search for older episodes by episode number using iTunes Search API.
    Uses rate limiting to avoid 403 errors.
    """
    console.print(f"[blue]Searching for episodes {start_episode}-{end_episode}...[/blue]")
    
    found_urls = []
    requests_made = 0
    
    for episode_num in range(start_episode, end_episode + 1):
        if requests_made >= max_requests:
            console.print(f"[yellow]Reached request limit ({max_requests}), stopping search[/yellow]")
            break
            
        search_terms = [
            f"founders {episode_num}",
            f"founders episode {episode_num}",
        ]
        
        episode_found = False
        for term in search_terms:
            if requests_made >= max_requests:
                break
                
            try:
                search_url = "https://itunes.apple.com/search"
                search_params = {
                    'term': term,
                    'media': 'podcast',
                    'entity': 'podcastEpisode',
                    'limit': 50
                }
                
                response = requests.get(search_url, params=search_params, timeout=15)
                requests_made += 1
                
                if response.status_code == 403:
                    console.print(f"[yellow]Rate limited, stopping search at episode {episode_num}[/yellow]")
                    return found_urls
                
                response.raise_for_status()
                
                data = response.json()
                results = data.get('results', [])
                
                for result in results:
                    if (result.get('collectionId') == int(podcast_id) and 
                        result.get('kind') == 'podcast-episode'):
                        
                        episode_id = result.get('trackId')
                        episode_name = result.get('trackName', '').replace(' ', '-').lower()
                        episode_name = re.sub(r'[^a-z0-9-]', '-', episode_name)
                        episode_name = re.sub(r'-+', '-', episode_name).strip('-')
                        
                        if episode_id:
                            episode_url = f"https://podcasts.apple.com/us/podcast/{episode_name}/id{podcast_id}?i={episode_id}"
                            if episode_url not in existing_urls and episode_url not in found_urls:
                                found_urls.append(episode_url)
                                console.print(f"[green]Found episode {episode_num}: {result.get('trackName', 'Unknown')}[/green]")
                                episode_found = True
                                break
                
                time.sleep(0.5)  # Rate limiting
                
                if episode_found:
                    break  # Found episode with this search term, move to next episode
                    
            except Exception as e:
                if "403" in str(e):
                    console.print(f"[yellow]Rate limited, stopping search[/yellow]")
                    return found_urls
                continue
        
        # Longer pause between episodes to be more respectful
        if episode_num % 10 == 0:
            time.sleep(2)
    
    console.print(f"[green]Search found {len(found_urls)} additional episodes[/green]")
    return found_urls

def validate_urls(urls: List[str], sample_size: int = 10) -> int:
    """Validate a sample of URLs to check if they're accessible."""
    if not urls:
        return 0
    
    sample_urls = urls[:sample_size] if len(urls) > sample_size else urls
    valid_count = 0
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    console.print(f"[blue]Validating {len(sample_urls)} URLs...[/blue]")
    
    for url in sample_urls:
        try:
            response = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
            if response.status_code == 200:
                valid_count += 1
        except:
            pass
        time.sleep(0.2)  # Be respectful
    
    return valid_count

@app.command()
def scrape(
    podcast_url: str = typer.Argument(..., help="Apple Podcasts URL (e.g., https://podcasts.apple.com/us/podcast/name/id123456)"),
    output: str = typer.Option("podcast_urls.txt", "--output", "-o", help="Output file for URLs"),
    search_older: bool = typer.Option(True, "--search-older/--no-search-older", help="Search for older episodes"),
    search_range: str = typer.Option("1-200", "--range", "-r", help="Episode range to search (e.g., '1-100')"),
    max_search_requests: int = typer.Option(100, "--max-requests", help="Maximum search requests to avoid rate limiting"),
    validate: bool = typer.Option(True, "--validate/--no-validate", help="Validate a sample of URLs"),
    append: bool = typer.Option(False, "--append", "-a", help="Append to existing file")
):
    """
    Scrape episode URLs from an Apple Podcasts page.
    
    Examples:
        # Basic scraping (recent episodes only)
        python apple_podcast_scraper.py "https://podcasts.apple.com/us/podcast/founders/id1141877104"
        
        # Search for older episodes in a specific range
        python apple_podcast_scraper.py "https://podcasts.apple.com/podcast/id123456" --range "1-150"
        
        # Append to existing file without validation
        python apple_podcast_scraper.py "https://podcasts.apple.com/podcast/id123456" --append --no-validate
    """
    
    console.print(f"[blue]Scraping podcast: {podcast_url}[/blue]")
    
    # Extract podcast ID
    podcast_id = extract_podcast_id(podcast_url)
    if not podcast_id:
        console.print("[red]Error: Could not extract podcast ID from URL[/red]")
        console.print("[yellow]Make sure the URL is in format: https://podcasts.apple.com/us/podcast/name/id123456[/yellow]")
        raise typer.Exit(1)
    
    all_urls = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        
        # Get recent episodes from iTunes API
        task = progress.add_task("Fetching recent episodes...", total=None)
        recent_urls = get_recent_episodes_from_api(podcast_id)
        all_urls.extend(recent_urls)
        progress.remove_task(task)
        
        # Search for older episodes if requested
        if search_older and recent_urls:
            # Parse search range
            try:
                start_ep, end_ep = map(int, search_range.split('-'))
            except ValueError:
                console.print(f"[red]Invalid range format: {search_range}. Use format like '1-100'[/red]")
                raise typer.Exit(1)
            
            task = progress.add_task("Searching for older episodes...", total=None)
            older_urls = search_for_older_episodes(
                podcast_id, all_urls, start_ep, end_ep, max_search_requests
            )
            all_urls.extend(older_urls)
            progress.remove_task(task)
    
    if not all_urls:
        console.print("[red]No episode URLs found. The podcast might be private or the URL might be incorrect.[/red]")
        raise typer.Exit(1)
    
    # Remove duplicates while preserving order
    unique_urls = []
    seen = set()
    for url in all_urls:
        if url not in seen:
            unique_urls.append(url)
            seen.add(url)
    
    console.print(f"[green]Found {len(unique_urls)} unique episodes[/green]")
    
    # Validate URLs if requested
    if validate:
        valid_count = validate_urls(unique_urls)
        console.print(f"[blue]Validation: {valid_count}/{min(len(unique_urls), 10)} URLs are accessible[/blue]")
    
    # Save URLs to file
    try:
        mode = 'a' if append else 'w'
        with open(output, mode, encoding='utf-8') as f:
            if not append:
                f.write(f"# Podcast URLs extracted from {podcast_url}\n")
                f.write(f"# Total episodes: {len(unique_urls)}\n")
                f.write(f"# Generated by Apple Podcast Scraper\n\n")
            elif append:
                f.write(f"\n# Additional episodes from {podcast_url}\n")
            
            for url in unique_urls:
                f.write(f"{url}\n")
        
        action = "Added to" if append else "Saved to"
        console.print(f"[green]{action} {output}: {len(unique_urls)} URLs[/green]")
        
        # Show preview
        console.print("\n[blue]Preview of first 5 URLs:[/blue]")
        for i, url in enumerate(unique_urls[:5], 1):
            console.print(f"  {i}. {url}")
        
        if len(unique_urls) > 5:
            console.print(f"  ... and {len(unique_urls) - 5} more")
            
    except Exception as e:
        console.print(f"[red]Error saving URLs to file: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def validate_file(
    file_path: str = typer.Argument(..., help="File containing URLs to validate"),
    sample_size: int = typer.Option(20, "--sample", "-s", help="Number of URLs to validate")
):
    """Validate URLs in a file to check if they're accessible."""
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except FileNotFoundError:
        console.print(f"[red]File {file_path} not found[/red]")
        raise typer.Exit(1)
    
    if not urls:
        console.print("[red]No URLs found in file[/red]")
        raise typer.Exit(1)
    
    console.print(f"[blue]Found {len(urls)} URLs in file[/blue]")
    
    valid_count = validate_urls(urls, sample_size)
    success_rate = (valid_count / min(len(urls), sample_size)) * 100
    
    console.print(f"[green]Validation complete: {valid_count}/{min(len(urls), sample_size)} URLs accessible ({success_rate:.1f}%)[/green]")

@app.command()
def info(podcast_url: str = typer.Argument(..., help="Apple Podcasts URL")):
    """Get basic information about a podcast."""
    
    podcast_id = extract_podcast_id(podcast_url)
    if not podcast_id:
        console.print("[red]Error: Could not extract podcast ID from URL[/red]")
        raise typer.Exit(1)
    
    try:
        base_url = "https://itunes.apple.com/lookup"
        params = {'id': podcast_id}
        
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        results = data.get('results', [])
        
        if not results:
            console.print("[red]Podcast not found[/red]")
            raise typer.Exit(1)
        
        podcast = results[0]
        
        console.print("\n[blue]Podcast Information:[/blue]")
        console.print(f"  Name: {podcast.get('collectionName', 'Unknown')}")
        console.print(f"  Artist: {podcast.get('artistName', 'Unknown')}")
        console.print(f"  Genre: {podcast.get('primaryGenreName', 'Unknown')}")
        console.print(f"  Episode Count: {podcast.get('trackCount', 'Unknown')}")
        console.print(f"  Country: {podcast.get('country', 'Unknown')}")
        
        if podcast.get('feedUrl'):
            console.print(f"  RSS Feed: {podcast.get('feedUrl')}")
        
        console.print(f"  iTunes URL: {podcast.get('collectionViewUrl', 'Unknown')}")
        
    except Exception as e:
        console.print(f"[red]Error fetching podcast info: {e}[/red]")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()