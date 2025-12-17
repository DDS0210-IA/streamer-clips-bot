# Streamer Clips Automation Bot 🎬🤖

An automated content pipeline that extracts viral moments from popular streamers,
edits them into vertical short-form videos, and uploads them automatically to
multiple social media platforms.

This project was built to demonstrate skills in automation, API integration,
video processing, and applied artificial intelligence.

---

## 🚀 Features

- 🔴 Clip extraction from **Twitch** and **YouTube**
- 🧠 AI-based highlight detection using:
  - Audio intensity
  - Speech transcription (subtitles)
- 📐 Automatic vertical video formatting (9:16)
- ✂️ Dynamic clip length (10–60 seconds)
- ⏰ Scheduled publishing **5 times per day**
- 📤 Automated uploads to:
  - YouTube Shorts
  - Instagram Reels
  - TikTok
- 🐧 Runs locally on **Linux**
- 🔐 Secure handling of API keys using `.env`

---

## 🛠️ Tech Stack

- **Python 3**
- **yt-dlp** – video & clip downloading
- **FFmpeg** – video editing & formatting
- **OpenAI Whisper** – speech-to-text transcription
- **Twitch API**
- **YouTube Data API**
- **Cron (Linux)** – task scheduling
- **dotenv** – environment variable management

---

## ⏱️ Automation Schedule

The bot automatically publishes **5 clips per day** at:

- 09:00
- 12:00
- 15:00
- 18:00
- 21:00

All scheduling is handled via Linux cron jobs.

---

## 📁 Project Structure
