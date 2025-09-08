ytdl_format_options = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    # Add your custom options here
}


# Discord Music Bot 🎵

A modern Discord bot for playing music from YouTube and Spotify, with advanced queue management, interactive controls, and easy setup.

## 🚀 Features
- Play music from YouTube and Spotify (tracks & playlists)
- Add, remove, shuffle, and loop songs in a queue
- Pause, resume, skip, stop, and clear queue
- Volume control
- Rich embeds with song info and album art
- Interactive Discord UI buttons
- Slash commands and prefix commands
- Spotify → YouTube fallback for playback

## 🛠️ Setup

### Prerequisites
- Python 3.8+
- FFmpeg installed and in your PATH
- Discord bot token
- (Optional) Spotify API credentials

### Installation
```sh
git clone https://github.com/Karunesh-18/MUSICBOT.git
cd MUSICBOT
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
python discord_music_bot.py
```

## 💡 Usage

### Basic Commands
- `!join` — Join your voice channel
- `!leave` — Leave the voice channel
- `!play <song/url>` — Play a song from YouTube or Spotify
- `!pause` — Pause current song
- `!resume` — Resume paused song
- `!skip` — Skip to next song
- `!stop` — Stop playback and clear queue
- `!queue` — Show current queue
- `!clear` — Clear the queue
- `!remove <position>` — Remove song at position from queue
- `!nowplaying` — Show currently playing song
- `!volume <0-100>` — Set playback volume
- `!shuffle` — Toggle shuffle mode
- `!loop [off/single/queue]` — Set loop mode

### Interactive Buttons
- ⏯️ Play/Pause
- ⏮️ Previous
- ⏭️ Skip
- ⏹️ Stop
- 🔀 Shuffle
- 🔁 Loop
- 📋 Show queue

## ⚙️ Environment Variables

| Variable                | Description                  | Required |
|-------------------------|------------------------------|----------|
| `DISCORD_TOKEN`         | Discord bot token            | Yes      |
| `SPOTIFY_CLIENT_ID`     | Spotify app client ID        | No       |
| `SPOTIFY_CLIENT_SECRET` | Spotify app client secret    | No       |

## 🧩 Troubleshooting
- Make sure FFmpeg is installed and in your PATH
- Check your Discord bot token and permissions
- For Spotify features, ensure credentials are correct

## 📄 License
MIT
