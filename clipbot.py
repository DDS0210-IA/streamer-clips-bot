import os
import requests
import json
import time
import moviepy.editor as mp
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pathlib import Path
import random
import re
import sys

# Load environment variables first
load_dotenv()

# Fix circular import by importing logging after other modules
try:
    import logging
    # Configure logging with a more specific format
    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('clipbot.log', mode='a')
        ]
    )
    logger = logging.getLogger('clipbot')
except Exception as e:
    print(f"Warning: Could not configure logging: {e}")
    # Fallback to simple print statements
    class SimpleLogger:
        def info(self, msg): print(f"INFO: {msg}")
        def error(self, msg): print(f"ERROR: {msg}")
        def warning(self, msg): print(f"WARNING: {msg}")
    logger = SimpleLogger()

# Import whisper after logging setup
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Whisper not available: {e}")
    WHISPER_AVAILABLE = False

class YouTubeShortsAutomation:
    def __init__(self):
        # Load API credentials from .env
        self.twitch_client_id = os.getenv('TWITCH_CLIENT_ID')
        self.twitch_client_secret = os.getenv('TWITCH_CLIENT_SECRET')
        self.twitch_streamer = os.getenv('TWITCH_STREAMER_NAME')
        
        # YouTube API setup
        self.youtube_api_key = os.getenv('YOUTUBE_API_KEY')
        self.youtube_client_id = os.getenv('YOUTUBE_CLIENT_ID')
        self.youtube_client_secret = os.getenv('YOUTUBE_CLIENT_SECRET')
        self.youtube_refresh_token = os.getenv('YOUTUBE_REFRESH_TOKEN')
        self.youtube_streamers = os.getenv('YOUTUBE_STREAMERS', '').split(',')
        
        # Initialize Whisper model for transcription
        self.whisper_model = None
        if WHISPER_AVAILABLE:
            try:
                self.whisper_model = whisper.load_model("base")
                logger.info("Whisper model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {e}")
        else:
            logger.warning("Whisper not available, transcription will be skipped")
        
        # Create directories
        Path("downloads").mkdir(exist_ok=True)
        Path("processed").mkdir(exist_ok=True)
        Path("uploads").mkdir(exist_ok=True)
        
        # Validate credentials
        self._validate_credentials()
        
        logger.info(f"Initialized YouTube Shorts automation for {self.twitch_streamer}")
        logger.info(f"Will also process clips from: {', '.join(self.youtube_streamers)}")

    def _validate_credentials(self):
        """Validate that all required credentials are present"""
        required_creds = {
            'TWITCH_CLIENT_ID': self.twitch_client_id,
            'TWITCH_CLIENT_SECRET': self.twitch_client_secret,
            'TWITCH_STREAMER_NAME': self.twitch_streamer,
            'YOUTUBE_API_KEY': self.youtube_api_key,
            'YOUTUBE_CLIENT_ID': self.youtube_client_id,
            'YOUTUBE_CLIENT_SECRET': self.youtube_client_secret,
            'YOUTUBE_REFRESH_TOKEN': self.youtube_refresh_token
        }
        
        missing_creds = [key for key, value in required_creds.items() if not value]
        if missing_creds:
            logger.error(f"Missing required credentials: {', '.join(missing_creds)}")
            raise Exception(f"Missing credentials: {', '.join(missing_creds)}")

    def get_fresh_access_token(self):
        """Get a fresh access token using the refresh token"""
        try:
            token_url = "https://oauth2.googleapis.com/token"
            data = {
                'client_id': self.youtube_client_id,
                'client_secret': self.youtube_client_secret,
                'refresh_token': self.youtube_refresh_token,
                'grant_type': 'refresh_token'
            }
            
            response = requests.post(token_url, data=data, timeout=10)
            
            if response.status_code == 200:
                token_data = response.json()
                logger.info("Successfully refreshed YouTube access token")
                return token_data['access_token']
            else:
                logger.error(f"Failed to refresh token: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error refreshing YouTube access token: {e}")
            return None

    def get_twitch_oauth_token(self):
        """Get OAuth token for Twitch API"""
        url = "https://id.twitch.tv/oauth2/token"
        params = {
            'client_id': self.twitch_client_id,
            'client_secret': self.twitch_client_secret,
            'grant_type': 'client_credentials'
        }
        
        try:
            response = requests.post(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()['access_token']
            else:
                logger.error(f"Failed to get Twitch OAuth token: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error getting Twitch OAuth token: {e}")
            return None

    def get_twitch_clips(self, streamer_name, limit=20):
        """Fetch recent Twitch clips with proper URL extraction"""
        access_token = self.get_twitch_oauth_token()
        if not access_token:
            return []
        
        headers = {
            'Client-ID': self.twitch_client_id,
            'Authorization': f'Bearer {access_token}'
        }
        
        try:
            # Get user ID
            user_response = requests.get(
                "https://api.twitch.tv/helix/users", 
                headers=headers, 
                params={'login': streamer_name},
                timeout=10
            )
            
            if user_response.status_code != 200:
                logger.error(f"Failed to get user ID for {streamer_name}: {user_response.text}")
                return []
            
            user_data = user_response.json()
            if not user_data.get('data'):
                logger.error(f"No user data found for {streamer_name}")
                return []
            
            user_id = user_data['data'][0]['id']
            
            # Get clips
            clips_params = {
                'broadcaster_id': user_id,
                'first': limit,
                'started_at': (datetime.now() - timedelta(days=7)).isoformat() + 'Z'
            }
            
            clips_response = requests.get(
                "https://api.twitch.tv/helix/clips", 
                headers=headers, 
                params=clips_params,
                timeout=10
            )
            
            if clips_response.status_code == 200:
                clips_data = clips_response.json().get('data', [])
                logger.info(f"Found {len(clips_data)} clips for {streamer_name}")
                return clips_data
            else:
                logger.error(f"Failed to get clips: {clips_response.status_code} - {clips_response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching Twitch clips: {e}")
            return []

    def get_youtube_videos(self, streamer_name, max_results=10):
        """Fetch recent YouTube videos from a streamer using API key"""
        try:
            from googleapiclient.discovery import build
            
            youtube = build('youtube', 'v3', developerKey=self.youtube_api_key)
            
            # Search for the channel
            search_response = youtube.search().list(
                q=streamer_name,
                type='channel',
                part='id',
                maxResults=1
            ).execute()
            
            if not search_response.get('items'):
                logger.error(f"Channel not found: {streamer_name}")
                return []
            
            channel_id = search_response['items'][0]['id']['channelId']
            
            # Get recent videos from the channel
            videos_response = youtube.search().list(
                channelId=channel_id,
                type='video',
                order='date',
                part='id,snippet',
                maxResults=max_results,
                publishedAfter=(datetime.now() - timedelta(days=7)).isoformat() + 'Z'
            ).execute()
            
            videos = []
            for item in videos_response.get('items', []):
                video_data = {
                    'id': item['id']['videoId'],
                    'title': item['snippet']['title'],
                    'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                    'published_at': item['snippet']['publishedAt'],
                    'thumbnail': item['snippet']['thumbnails']['high']['url']
                }
                videos.append(video_data)
            
            logger.info(f"Found {len(videos)} recent videos from {streamer_name}")
            return videos
            
        except Exception as e:
            logger.error(f"Error fetching YouTube videos for {streamer_name}: {e}")
            return []

    def get_clip_download_url(self, clip_url):
        """Extract actual download URL from Twitch clip URL"""
        try:
            # Extract clip slug from URL and construct download URL
            clip_slug = clip_url.split('/')[-1]
            
            # Try multiple possible download URL formats
            possible_urls = [
                f"https://clips-media-assets2.twitch.tv/{clip_slug}.mp4",
                f"https://clips-media-assets.twitch.tv/{clip_slug}.mp4",
                f"https://production.assets.clips.twitchcdn.net/{clip_slug}.mp4"
            ]
            
            for url in possible_urls:
                try:
                    response = requests.head(url, timeout=10)
                    if response.status_code == 200:
                        return url
                except:
                    continue
            
            # Fallback: use yt-dlp to get actual URL
            try:
                import yt_dlp
                ydl_opts = {'quiet': True, 'no_warnings': True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(clip_url, download=False)
                    if info and 'url' in info:
                        return info['url']
            except Exception as yt_error:
                logger.warning(f"yt-dlp fallback failed: {yt_error}")
            
            logger.warning(f"Could not find download URL for clip: {clip_url}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting download URL from {clip_url}: {e}")
            return None

    def download_clip(self, clip_url, filename):
        """Download a clip from Twitch"""
        try:
            download_url = self.get_clip_download_url(clip_url)
            if not download_url:
                return False
            
            response = requests.get(download_url, stream=True, timeout=30)
            if response.status_code == 200:
                filepath = f"downloads/{filename}"
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # Verify file was downloaded and has content
                if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
                    logger.info(f"Downloaded: {filename} ({os.path.getsize(filepath)} bytes)")
                    return True
                else:
                    logger.error(f"Downloaded file is too small or empty: {filename}")
                    return False
            else:
                logger.error(f"Failed to download clip: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error downloading {filename}: {e}")
            return False

    def download_video_segment(self, video_url, output_path, start_time=None, duration=60):
        """Download a video segment using yt-dlp"""
        try:
            import yt_dlp
            
            ydl_opts = {
                'format': 'best[height<=720]',
                'outtmpl': output_path,
                'extract_flat': False,
                'quiet': True,
                'no_warnings': True
            }
            
            # Add time constraints if specified
            if start_time:
                ydl_opts['external_downloader_args'] = [
                    '-ss', str(start_time),
                    '-t', str(duration)
                ]
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
            
            # Verify download
            if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                logger.info(f"Downloaded video segment: {output_path}")
                return True
            else:
                logger.error(f"Video segment download failed or file too small: {output_path}")
                return False
            
        except Exception as e:
            logger.error(f"Error downloading video segment: {e}")
            return False

    def transcribe_audio(self, video_path):
        """Transcribe audio using Whisper"""
        if not self.whisper_model:
            logger.warning("Whisper model not available, skipping transcription")
            return ""
        
        try:
            result = self.whisper_model.transcribe(video_path)
            return result.get('text', '')
        except Exception as e:
            logger.error(f"Error transcribing {video_path}: {e}")
            return ""

    def analyze_content(self, transcription):
        """Analyze content for highlights"""
        highlight_keywords = {
            'excitement': ['wow', 'amazing', 'incredible', 'perfect', 'clutch', 'insane', 'crazy'],
            'action': ['headshot', 'kill', 'victory', 'win', 'champion', 'eliminated'],
            'reaction': ['omg', 'wtf', 'holy', 'jesus', 'god', 'damn'],
            'skill': ['pro', 'skilled', 'talent', 'god-tier', 'masterclass']
        }
        
        content_analysis = {
            'total_score': 0,
            'categories': {},
            'dominant_emotion': 'neutral'
        }
        
        transcription_lower = transcription.lower()
        
        for category, keywords in highlight_keywords.items():
            category_score = sum(transcription_lower.count(keyword) for keyword in keywords)
            content_analysis['categories'][category] = category_score
            content_analysis['total_score'] += category_score
        
        # Determine dominant emotion
        if content_analysis['categories']:
            max_category = max(content_analysis['categories'].items(), key=lambda x: x[1])
            if max_category[1] > 0:
                content_analysis['dominant_emotion'] = max_category[0]
        
        return content_analysis

    def create_vertical_video(self, input_path, output_path):
        """Convert video to vertical format (1080x1920) for YouTube Shorts"""
        try:
            # Fix PIL.Image ANTIALIAS compatibility issue
            try:
                import PIL.Image
                if not hasattr(PIL.Image, 'ANTIALIAS'):
                    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
            except ImportError:
                logger.warning("PIL not available, proceeding without explicit ANTIALIAS fix")
            
            video = mp.VideoFileClip(input_path)
            
            if video.duration < 1:
                logger.error(f"Video too short: {video.duration}s")
                video.close()
                return False
            
            target_width, target_height = 1080, 1920
            video_aspect = video.w / video.h
            target_aspect = target_width / target_height
            
            # Crop to vertical aspect ratio
            if video_aspect > target_aspect:
                # Video is too wide, crop horizontally
                new_width = int(video.h * target_aspect)
                x_center = video.w / 2
                x1 = int(x_center - new_width / 2)
                video = video.crop(x1=x1, x2=x1 + new_width)
            else:
                # Video is too tall, crop vertically
                new_height = int(video.w / target_aspect)
                y_center = video.h / 2
                y1 = int(y_center - new_height / 2)
                video = video.crop(y1=y1, y2=y1 + new_height)
            
            # Resize to target dimensions
            video = video.resize((target_width, target_height))
            
            # Write with optimized settings
            video.write_videofile(
                output_path, 
                codec='libx264', 
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                fps=30,
                verbose=False,
                logger=None
            )
            video.close()
            
            logger.info(f"Created vertical video: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating vertical video: {e}")
            return False

    def trim_video(self, input_path, output_path, max_duration=40):
        """Trim video to optimal duration for Shorts"""
        try:
            # Fix PIL.Image ANTIALIAS compatibility issue
            try:
                import PIL.Image
                if not hasattr(PIL.Image, 'ANTIALIAS'):
                    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
            except ImportError:
                logger.warning("PIL not available, proceeding without explicit ANTIALIAS fix")
                
            video = mp.VideoFileClip(input_path)
            
            if video.duration > max_duration:
                # Take the middle portion for best content
                start_time = max(0, (video.duration - max_duration) / 2)
                end_time = start_time + max_duration
                video = video.subclip(start_time, end_time)
            
            video.write_videofile(
                output_path, 
                codec='libx264', 
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                verbose=False,
                logger=None
            )
            video.close()
            return True
        except Exception as e:
            logger.error(f"Error trimming video: {e}")
            return False

    def generate_engaging_title(self, clip_title, content_analysis, streamer_name):
        """Generate engaging YouTube Short titles"""
        templates = {
            'excitement': [
                f"THIS {streamer_name.upper()} MOMENT IS INSANE! 🔥",
                f"{streamer_name} GOES ABSOLUTELY CRAZY! 😱",
                f"UNBELIEVABLE {streamer_name} PLAY! 🤯"
            ],
            'action': [
                f"{streamer_name} DESTROYS EVERYONE! 💀",
                f"UNSTOPPABLE {streamer_name} GAMEPLAY! 🎯",
                f"{streamer_name} DOMINATION! ⚡"
            ],
            'skill': [
                f"{streamer_name} IS A LITERAL GOD! 👑",
                f"PRO LEVEL {streamer_name} SKILLS! 🎯",
                f"{streamer_name} MASTERCLASS! 🔥"
            ],
            'neutral': [
                f"BEST {streamer_name} MOMENTS! 🔥",
                f"{streamer_name} HIGHLIGHTS! ⭐",
                f"EPIC {streamer_name} CLIP! 🎮"
            ]
        }
        
        emotion = content_analysis.get('dominant_emotion', 'neutral')
        selected_titles = templates.get(emotion, templates['neutral'])
        return random.choice(selected_titles)

    def upload_to_youtube_shorts(self, video_path, title, description, tags=None):
        """Upload video to YouTube as a Short using direct API calls"""
        try:
            access_token = self.get_fresh_access_token()
            if not access_token:
                logger.error("Failed to get access token for YouTube upload")
                return False

            # Step 1: Initialize the upload
            metadata = {
                'snippet': {
                    'title': title,
                    'description': description + '\n\n#Shorts',
                    'tags': tags or [],
                    'categoryId': '20'  # Gaming category
                },
                'status': {
                    'privacyStatus': 'public',
                    'selfDeclaredMadeForKids': False
                }
            }

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            # Initialize upload session
            init_url = 'https://www.googleapis.com/upload/youtube/v3/videos'
            init_params = {
                'part': 'snippet,status',
                'uploadType': 'resumable'
            }

            init_response = requests.post(
                init_url,
                params=init_params,
                headers=headers,
                json=metadata,
                timeout=30
            )

            if init_response.status_code not in [200, 201]:
                logger.error(f"Failed to initialize upload: {init_response.status_code} - {init_response.text}")
                return False

            # Get upload URL from Location header
            upload_url = init_response.headers.get('Location')
            if not upload_url:
                logger.error("No upload URL returned from YouTube")
                return False

            # Step 2: Upload the video file
            with open(video_path, 'rb') as video_file:
                video_data = video_file.read()

            upload_headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'video/mp4'
            }

            upload_response = requests.put(
                upload_url,
                headers=upload_headers,
                data=video_data,
                timeout=300  # 5 minutes timeout for video upload
            )

            if upload_response.status_code in [200, 201]:
                response_data = upload_response.json()
                video_id = response_data.get('id')
                
                if video_id:
                    logger.info(f"🎬 Successfully uploaded YouTube Short: https://youtube.com/shorts/{video_id}")
                    logger.info(f"📝 Title: {title}")
                    return True
                else:
                    logger.error("Upload successful but no video ID returned")
                    return False
            else:
                logger.error(f"Video upload failed: {upload_response.status_code} - {upload_response.text}")
                return False

        except Exception as e:
            logger.error(f"YouTube upload failed: {e}")
            return False

    def process_clips(self):
        """Main processing function with improved error handling"""
        logger.info("🚀 Starting YouTube Shorts creation process...")
        
        # Get Twitch clips
        clips = self.get_twitch_clips(self.twitch_streamer)
        if not clips:
            logger.warning("No Twitch clips found")
            return 0
        
        processed_count = 0
        max_uploads = 3  # Limit uploads per run to avoid quota issues
        
        for clip in clips[:max_uploads * 2]:  # Process more clips to account for failures
            if processed_count >= max_uploads:
                break
                
            try:
                clip_id = clip['id']
                clip_title = clip['title']
                clip_url = clip['url']
                streamer_name = self.twitch_streamer
                
                logger.info(f"🎬 Processing clip: {clip_title}")
                
                # Download clip
                filename = f"twitch_clip_{clip_id}.mp4"
                if not self.download_clip(clip_url, filename):
                    logger.warning(f"Failed to download clip {clip_id}, skipping...")
                    continue
                
                input_path = f"downloads/{filename}"
                
                # Verify file exists and has content
                if not os.path.exists(input_path) or os.path.getsize(input_path) < 1000:
                    logger.warning(f"Downloaded file is invalid: {input_path}")
                    continue
                
                # Transcribe and analyze
                transcription = self.transcribe_audio(input_path)
                content_analysis = self.analyze_content(transcription)
                
                # Process video
                vertical_path = f"processed/vertical_{filename}"
                if not self.create_vertical_video(input_path, vertical_path):
                    logger.warning(f"Failed to create vertical video for {clip_id}")
                    continue
                
                final_path = f"uploads/final_{filename}"
                if not self.trim_video(vertical_path, final_path, 40):
                    logger.warning(f"Failed to trim video for {clip_id}")
                    continue
                
                # Generate content metadata
                title = self.generate_engaging_title(clip_title, content_analysis, streamer_name)
                description = f"🔥 Epic {streamer_name} gaming moment!\n\n🎮 Follow for more amazing clips!\n\n"
                tags = ['shorts', 'gaming', streamer_name.lower(), 'viral', 'epic', 'twitch']
                
                # Upload to YouTube
                if self.upload_to_youtube_shorts(final_path, title, description, tags):
                    processed_count += 1
                    logger.info(f"✅ Successfully created Short #{processed_count}: {title}")
                else:
                    logger.error(f"Failed to upload Short for clip {clip_id}")
                
                # Cleanup files
                for path in [input_path, vertical_path, final_path]:
                    if os.path.exists(path):
                        try:
                            os.remove(path)
                        except:
                            pass
                
                # Rate limiting
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"Error processing clip {clip.get('id', 'unknown')}: {e}")
                continue
        
        logger.info(f"🎉 Process completed! Created {processed_count} new YouTube Shorts!")
        return processed_count

def main():
    """Run the automation with proper error handling"""
    try:
        automation = YouTubeShortsAutomation()
        result = automation.process_clips()
        logger.info(f"Automation completed. Created {result} shorts.")
    except Exception as e:
        logger.error(f"Automation failed: {e}")
        return 1
    return 0

if __name__ == "__main__":
    main()