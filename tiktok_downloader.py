import os
import sys
import subprocess
import time
from pathlib import Path

def check_and_install_ytdlp():
    """Check if yt-dlp is installed, if not, install it"""
    try:
        subprocess.run(['yt-dlp', '--version'], capture_output=True, check=True)
        print("✓ yt-dlp is already installed")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("yt-dlp not found. Installing...")
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'yt-dlp'], check=True)
            print("✓ yt-dlp installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to install yt-dlp: {e}")
            return False

def read_urls_from_file(file_path):
    """Read URLs from a text file and return them as a list"""
    try:
        # Check if file exists first
        if not os.path.exists(file_path):
            print(f"Error: File '{file_path}' not found.")
            print(f"Current directory: {os.getcwd()}")
            print(f"Files in current directory: {os.listdir('.')}")
            print("Please make sure 'tiktok_urls.txt' is in the same directory as this script")
            return []
            
        with open(file_path, 'r', encoding='utf-8') as file:
            urls = [line.strip() for line in file if line.strip() and not line.strip().startswith('#')]
        
        if not urls:
            print(f"Warning: No URLs found in '{file_path}' or file is empty")
            return []
            
        return urls
    except PermissionError:
        print(f"Error: Permission denied reading '{file_path}'")
        return []
    except Exception as e:
        print(f"Error reading file '{file_path}': {e}")
        return []

def get_tiktoks_directory():
    """Get the tiktoks directory path"""
    tiktoks_dir = Path("tiktoks")
    if not tiktoks_dir.exists():
        print("Error: 'tiktoks' directory not found. Please make sure it exists.")
        return None
    return tiktoks_dir

def download_tiktok_video(url, download_dir):
    """Download TikTok video using yt-dlp"""
    try:
        # yt-dlp command with options optimized for TikTok
        cmd = [
            'yt-dlp',
            '--no-playlist',
            '--format', 'best/mp4',  # Prefer mp4 format
            '--output', str(download_dir / '%(uploader)s_%(id)s.%(ext)s'),  # Simpler filename
            '--restrict-filenames',
            '--no-warnings',
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            '--referer', 'https://www.tiktok.com/',
            url
        ]
        
        # Run yt-dlp command
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print(f"✓ Successfully downloaded: {url}")
            return True
        else:
            print(f"✗ Failed to download: {url}")
            if result.stderr:
                print(f"  Error: {result.stderr.strip()}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"✗ Timeout downloading: {url}")
        return False
    except Exception as e:
        print(f"✗ Error downloading {url}: {e}")
        return False

def main():
    print("TikTok Video Downloader (using yt-dlp)")
    print("=" * 45)
    
    # Check and install yt-dlp if needed
    if not check_and_install_ytdlp():
        print("Cannot proceed without yt-dlp. Please install it manually:")
        print("pip install yt-dlp")
        return
    
    # Get tiktoks directory
    tiktoks_dir = get_tiktoks_directory()
    if not tiktoks_dir:
        return
    print(f"✓ Using existing directory: {tiktoks_dir.absolute()}")
    
    # Configuration
    txt_file = "tiktok_urls.txt"
    delay_between_downloads = 3  # seconds between downloads
    
    # Read URLs from file
    urls = read_urls_from_file(txt_file)
    
    if not urls:
        print("\nPlease create 'tiktok_urls.txt' with TikTok URLs like this:")
        print("https://www.tiktok.com/@username/video/1234567890")
        print("https://vm.tiktok.com/shortlink/")
        print("# Lines starting with # are ignored")
        return
    
    print(f"\nFound {len(urls)} URLs to download:")
    for i, url in enumerate(urls, 1):
        print(f"{i}. {url}")
    
    print(f"\nStarting downloads...")
    print("-" * 50)
    
    # Download each video
    successful_downloads = 0
    failed_downloads = 0
    
    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] Downloading: {url}")
        
        if download_tiktok_video(url, tiktoks_dir):
            successful_downloads += 1
        else:
            failed_downloads += 1
        
        # Add delay between downloads
        if i < len(urls):
            print(f"Waiting {delay_between_downloads} seconds...")
            time.sleep(delay_between_downloads)
    
    # Summary
    print("\n" + "=" * 50)
    print("DOWNLOAD SUMMARY")
    print(f"Total URLs processed: {len(urls)}")
    print(f"Successful downloads: {successful_downloads}")
    print(f"Failed downloads: {failed_downloads}")
    print(f"Files saved to: {tiktoks_dir.absolute()}")
    
    # Show downloaded files
    downloaded_files = list(tiktoks_dir.glob("*"))
    if downloaded_files:
        print(f"\nDownloaded files:")
        for file in downloaded_files:
            if file.is_file() and file.suffix in ['.mp4', '.webm', '.mkv']:
                print(f"  📹 {file.name}")

if __name__ == "__main__":
    main()
