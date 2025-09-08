
import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv
import json
import logging
from collections import deque
import random
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import aiohttp
import subprocess
load_dotenv()

## logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

## bot config
class Config:
    def __init__(self):
        self.DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
        self.SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
        self.SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
        self.COMMAND_PREFIX = '!'

## spotify client setup
config = Config()
spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(
    client_id=config.SPOTIFY_CLIENT_ID,
    client_secret=config.SPOTIFY_CLIENT_SECRET
))

## yt-dlp config
ytdl_format_options = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'cookiefile': 'cookies.txt',  ## for age-restricted stuff
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -filter:a "volume=0.8"'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class Song:
    def __init__(self, title, artist, url, duration, thumbnail, source='YouTube', requester=None):
        self.title = title
        self.artist = artist
        self.url = url
        self.duration = duration
        self.thumbnail = thumbnail
        self.source = source
        self.requester = requester

    def __str__(self):
        return f"{self.title} by {self.artist} ({self.source})"

class MusicQueue:
    def __init__(self):
        self.queue = deque()
        self.history = deque(maxlen=10)
        self.current = None
    self.loop_mode = 'off'  ## can be 'off', 'single', 'queue'
        self.shuffle = False

    def add(self, song):
        self.queue.append(song)

    def get_next(self):
        if self.loop_mode == 'single' and self.current:
            return self.current

        if not self.queue:
            return None

        if self.shuffle:
            ## shuffle logic
            queue_list = list(self.queue)
            song = random.choice(queue_list)
            self.queue.remove(song)
        else:
            song = self.queue.popleft()

        if self.current:
            self.history.append(self.current)

        self.current = song

        if self.loop_mode == 'queue':
            self.queue.append(song)

        return song

    def get_previous(self):
        if self.history:
            prev_song = self.history.pop()
            if self.current:
                self.queue.appendleft(self.current)
            self.current = prev_song
            return prev_song
        return None

    def clear(self):
        self.queue.clear()
        self.current = None

class MusicPlayer:
    def __init__(self, bot):
        self.bot = bot
        self.voice_clients = {}
        self.queues = {}
        self.volumes = {}

    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = MusicQueue()
        return self.queues[guild_id]

    def get_voice_client(self, guild_id):
        return self.voice_clients.get(guild_id)

    async def extract_info(self, query, search=True):
        """Extract information from YouTube or Spotify"""
        try:
            loop = asyncio.get_event_loop()

            if 'spotify' in query:
                return await self.extract_spotify_info(query)
            else:
                ## yt-dlp for youtube
                data = await loop.run_in_executor(
                    None, 
                    lambda: ytdl.extract_info(
                        f"ytsearch:{query}" if search and not query.startswith('http') else query,
                        download=False
                    )
                )

                if 'entries' in data:
                    data = data['entries'][0]

                return Song(
                    title=data.get('title', 'Unknown Title'),
                    artist=data.get('uploader', 'Unknown Artist'),
                    url=data.get('url'),
                    duration=data.get('duration', 0),
                    thumbnail=data.get('thumbnail', ''),
                    source='YouTube'
                )
        except Exception as e:
            logger.error(f"Error extracting info: {e}")
            return None

    async def extract_spotify_info(self, spotify_url):
        """Extract Spotify track info and find YouTube equivalent"""
        try:
            if 'track' in spotify_url:
                track_id = spotify_url.split('/')[-1].split('?')[0]
                track = spotify.track(track_id)

                query = f"{track['name']} {track['artists'][0]['name']}"
                ## search for youtube version
                youtube_song = await self.extract_info(query, search=True)

                if youtube_song:
                    youtube_song.title = track['name']
                    youtube_song.artist = ', '.join([artist['name'] for artist in track['artists']])
                    youtube_song.source = 'Spotify → YouTube'
                    youtube_song.thumbnail = track['album']['images'][0]['url'] if track['album']['images'] else ''

                return youtube_song

            elif 'playlist' in spotify_url:
                playlist_id = spotify_url.split('/')[-1].split('?')[0]
                playlist = spotify.playlist(playlist_id)

                songs = []
                for item in playlist['tracks']['items'][:50]:  ## only first 50 songs
                    track = item['track']
                    if track:
                        query = f"{track['name']} {track['artists'][0]['name']}"
                        youtube_song = await self.extract_info(query, search=True)
                        if youtube_song:
                            youtube_song.title = track['name']
                            youtube_song.artist = ', '.join([artist['name'] for artist in track['artists']])
                            youtube_song.source = 'Spotify → YouTube'
                            songs.append(youtube_song)

                return songs

        except Exception as e:
            logger.error(f"Error extracting Spotify info: {e}")
            return None

    async def play_next(self, guild_id):
        """Play the next song in queue"""
        voice_client = self.get_voice_client(guild_id)
        queue = self.get_queue(guild_id)

        if not voice_client:
            return

        song = queue.get_next()
        if not song:
            return

        try:
            ## ffmpeg source
            source = discord.FFmpegPCMAudio(song.url, **ffmpeg_options)

            ## set volume
            volume = self.volumes.get(guild_id, 0.5)
            source = discord.PCMVolumeTransformer(source, volume=volume)

            ## play and callback for next
            voice_client.play(
                source,
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    self.play_next(guild_id), self.bot.loop
                ) if not e else logger.error(f"Player error: {e}")
            )

            logger.info(f"Now playing: {song}")

        except Exception as e:
            logger.error(f"Error playing song: {e}")
            await self.play_next(guild_id)

class MusicView(discord.ui.View):
    """UI View with music control buttons"""

    def __init__(self, player, guild_id):
        super().__init__(timeout=300)
        self.player = player
        self.guild_id = guild_id

    @discord.ui.button(emoji='⏯️', style=discord.ButtonStyle.primary, row=0)
    async def play_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice_client = self.player.get_voice_client(self.guild_id)
        if voice_client:
            if voice_client.is_playing():
                voice_client.pause()
                await interaction.response.send_message("⏸️ Paused", ephemeral=True)
            elif voice_client.is_paused():
                voice_client.resume()
                await interaction.response.send_message("▶️ Resumed", ephemeral=True)

    @discord.ui.button(emoji='⏮️', style=discord.ButtonStyle.secondary, row=0)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        queue = self.player.get_queue(self.guild_id)
        voice_client = self.player.get_voice_client(self.guild_id)

        if voice_client and voice_client.is_playing():
            voice_client.stop()

        prev_song = queue.get_previous()
        if prev_song:
            await self.player.play_next(self.guild_id)
            await interaction.response.send_message(f"⏮️ Playing previous: {prev_song.title}", ephemeral=True)
        else:
            await interaction.response.send_message("No previous song", ephemeral=True)

    @discord.ui.button(emoji='⏭️', style=discord.ButtonStyle.secondary, row=0)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice_client = self.player.get_voice_client(self.guild_id)
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            await interaction.response.send_message("⏭️ Skipped", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing playing", ephemeral=True)

    @discord.ui.button(emoji='⏹️', style=discord.ButtonStyle.danger, row=0)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice_client = self.player.get_voice_client(self.guild_id)
        queue = self.player.get_queue(self.guild_id)

        if voice_client:
            voice_client.stop()
            queue.clear()
            await interaction.response.send_message("⏹️ Stopped and cleared queue", ephemeral=True)

    @discord.ui.button(emoji='🔀', style=discord.ButtonStyle.secondary, row=1)
    async def shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        queue = self.player.get_queue(self.guild_id)
        queue.shuffle = not queue.shuffle
        status = "enabled" if queue.shuffle else "disabled"
        await interaction.response.send_message(f"🔀 Shuffle {status}", ephemeral=True)

    @discord.ui.button(emoji='🔁', style=discord.ButtonStyle.secondary, row=1)
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        queue = self.player.get_queue(self.guild_id)
        loop_modes = ['off', 'single', 'queue']
        current_index = loop_modes.index(queue.loop_mode)
        queue.loop_mode = loop_modes[(current_index + 1) % len(loop_modes)]

        emojis = {'off': '❌', 'single': '🔂', 'queue': '🔁'}
        await interaction.response.send_message(
            f"{emojis[queue.loop_mode]} Loop mode: {queue.loop_mode}", 
            ephemeral=True
        )

    @discord.ui.button(label='Queue', emoji='📋', style=discord.ButtonStyle.secondary, row=1)
    async def show_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        queue = self.player.get_queue(self.guild_id)

        if not queue.queue and not queue.current:
            await interaction.response.send_message("Queue is empty", ephemeral=True)
            return

        embed = discord.Embed(title="Music Queue", color=0x7289da)

        if queue.current:
            embed.add_field(
                name="Now Playing",
                value=f"🎵 {queue.current.title} by {queue.current.artist}",
                inline=False
            )

        if queue.queue:
            queue_list = []
            for i, song in enumerate(list(queue.queue)[:10], 1):
                queue_list.append(f"{i}. {song.title} by {song.artist}")

            embed.add_field(
                name=f"Up Next ({len(queue.queue)} songs)",
                value="\n".join(queue_list),
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True

        super().__init__(
            command_prefix=config.COMMAND_PREFIX,
            intents=intents,
            help_command=None
        )

        self.player = MusicPlayer(self)

    async def on_ready(self):
        logger.info(f'{self.user} has connected to Discord!')

    ## sync slash commands
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

## bot instance
bot = MusicBot()

## music commands
@bot.hybrid_command(name='join', description='Join a voice channel')
async def join(ctx):
    """Join the user's voice channel"""
    if not ctx.author.voice:
        return await ctx.send("❌ You need to be in a voice channel!")

    channel = ctx.author.voice.channel
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    if voice_client and voice_client.is_connected():
        await voice_client.move_to(channel)
        await ctx.send(f"✅ Moved to **{channel.name}**")
    else:
        voice_client = await channel.connect()
        bot.player.voice_clients[ctx.guild.id] = voice_client
        await ctx.send(f"✅ Joined **{channel.name}**")

@bot.hybrid_command(name='leave', description='Leave the voice channel')
async def leave(ctx):
    """Leave the voice channel"""
    voice_client = bot.player.get_voice_client(ctx.guild.id)

    if voice_client:
        await voice_client.disconnect()
        del bot.player.voice_clients[ctx.guild.id]
        bot.player.get_queue(ctx.guild.id).clear()
        await ctx.send("👋 Left the voice channel")
    else:
        await ctx.send("❌ I'm not in a voice channel")

@bot.hybrid_command(name='play', description='Play a song from YouTube or Spotify')
async def play(ctx, *, query: str):
    """Play a song from YouTube or Spotify"""
    ## join voice channel if needed
    if not bot.player.get_voice_client(ctx.guild.id):
        await join(ctx)

    ## typing indicator
    async with ctx.typing():
    ## get song info
        if 'playlist' in query and 'spotify' in query:
            songs = await bot.player.extract_info(query, search=False)
            if songs:
                queue = bot.player.get_queue(ctx.guild.id)
                for song in songs:
                    song.requester = ctx.author
                    queue.add(song)

                embed = discord.Embed(
                    title="Playlist Added to Queue",
                    description=f"Added {len(songs)} songs to the queue",
                    color=0x1db954
                )
                view = MusicView(bot.player, ctx.guild.id)
                await ctx.send(embed=embed, view=view)
            else:
                await ctx.send("❌ Could not process playlist")
        else:
            song = await bot.player.extract_info(query)
            if song:
                song.requester = ctx.author
                queue = bot.player.get_queue(ctx.guild.id)
                queue.add(song)

                embed = discord.Embed(
                    title="Added to Queue",
                    description=f"**{song.title}** by {song.artist}",
                    color=0x7289da
                )
                embed.add_field(name="Source", value=song.source, inline=True)
                embed.add_field(name="Requested by", value=ctx.author.mention, inline=True)

                if song.thumbnail:
                    embed.set_thumbnail(url=song.thumbnail)

                view = MusicView(bot.player, ctx.guild.id)
                await ctx.send(embed=embed, view=view)

                ## start playing if not already
                voice_client = bot.player.get_voice_client(ctx.guild.id)
                if voice_client and not voice_client.is_playing():
                    await bot.player.play_next(ctx.guild.id)
            else:
                await ctx.send("❌ Could not find the song")

@bot.hybrid_command(name='pause', description='Pause the current song')
async def pause(ctx):
    """Pause the current song"""
    voice_client = bot.player.get_voice_client(ctx.guild.id)
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await ctx.send("⏸️ Paused")
    else:
        await ctx.send("❌ Nothing is playing")

@bot.hybrid_command(name='resume', description='Resume the current song')
async def resume(ctx):
    """Resume the current song"""
    voice_client = bot.player.get_voice_client(ctx.guild.id)
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await ctx.send("▶️ Resumed")
    else:
        await ctx.send("❌ Nothing is paused")

@bot.hybrid_command(name='skip', description='Skip the current song')
async def skip(ctx):
    """Skip the current song"""
    voice_client = bot.player.get_voice_client(ctx.guild.id)
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await ctx.send("⏭️ Skipped")
    else:
        await ctx.send("❌ Nothing is playing")

@bot.hybrid_command(name='stop', description='Stop playing and clear the queue')
async def stop(ctx):
    """Stop playing and clear the queue"""
    voice_client = bot.player.get_voice_client(ctx.guild.id)
    queue = bot.player.get_queue(ctx.guild.id)

    if voice_client:
        voice_client.stop()
        queue.clear()
        await ctx.send("⏹️ Stopped and cleared queue")
    else:
        await ctx.send("❌ Nothing is playing")

@bot.hybrid_command(name='queue', description='Show the current queue')
async def show_queue(ctx):
    """Show the current queue"""
    queue = bot.player.get_queue(ctx.guild.id)

    if not queue.queue and not queue.current:
        return await ctx.send("❌ Queue is empty")

    embed = discord.Embed(title="Music Queue", color=0x7289da)

    if queue.current:
        embed.add_field(
            name="Now Playing",
            value=f"🎵 **{queue.current.title}** by {queue.current.artist}\n"
                  f"Source: {queue.current.source}",
            inline=False
        )

    if queue.queue:
        queue_list = []
        for i, song in enumerate(list(queue.queue)[:10], 1):
            queue_list.append(f"`{i}.` **{song.title}** by {song.artist}")

        embed.add_field(
            name=f"Up Next ({len(queue.queue)} songs)",
            value="\n".join(queue_list),
            inline=False
        )

        if len(queue.queue) > 10:
            embed.add_field(
                name="",
                value=f"... and {len(queue.queue) - 10} more songs",
                inline=False
            )

    embed.add_field(
        name="Settings",
        value=f"Loop: {queue.loop_mode} | Shuffle: {'On' if queue.shuffle else 'Off'}",
        inline=False
    )

    view = MusicView(bot.player, ctx.guild.id)
    await ctx.send(embed=embed, view=view)

@bot.hybrid_command(name='nowplaying', description='Show the currently playing song')
async def nowplaying(ctx):
    """Show the currently playing song"""
    queue = bot.player.get_queue(ctx.guild.id)
    voice_client = bot.player.get_voice_client(ctx.guild.id)

    if not queue.current:
        return await ctx.send("❌ Nothing is playing")

    song = queue.current
    embed = discord.Embed(
        title="Now Playing",
        description=f"**{song.title}**\nby {song.artist}",
        color=0x7289da
    )

    embed.add_field(name="Source", value=song.source, inline=True)
    embed.add_field(name="Requested by", value=song.requester.mention if song.requester else "Unknown", inline=True)

    if song.duration:
        duration_str = f"{song.duration // 60}:{song.duration % 60:02d}"
        embed.add_field(name="Duration", value=duration_str, inline=True)

    if song.thumbnail:
        embed.set_thumbnail(url=song.thumbnail)

    status = "⏸️ Paused" if voice_client and voice_client.is_paused() else "▶️ Playing"
    embed.add_field(name="Status", value=status, inline=True)

    view = MusicView(bot.player, ctx.guild.id)
    await ctx.send(embed=embed, view=view)

@bot.hybrid_command(name='volume', description='Set the volume (0-100)')
async def volume(ctx, volume: int):
    """Set the volume"""
    if not 0 <= volume <= 100:
        return await ctx.send("❌ Volume must be between 0 and 100")

    bot.player.volumes[ctx.guild.id] = volume / 100

    ## set volume for current song
    voice_client = bot.player.get_voice_client(ctx.guild.id)
    if voice_client and hasattr(voice_client.source, 'volume'):
        voice_client.source.volume = volume / 100

    await ctx.send(f"🔊 Volume set to {volume}%")

@bot.hybrid_command(name='clear', description='Clear the queue')
async def clear_queue(ctx):
    """Clear the queue"""
    queue = bot.player.get_queue(ctx.guild.id)
    queue.queue.clear()
    await ctx.send("🗑️ Queue cleared")

@bot.hybrid_command(name='shuffle', description='Toggle shuffle mode')
async def shuffle(ctx):
    """Toggle shuffle mode"""
    queue = bot.player.get_queue(ctx.guild.id)
    queue.shuffle = not queue.shuffle
    status = "enabled" if queue.shuffle else "disabled"
    await ctx.send(f"🔀 Shuffle {status}")

@bot.hybrid_command(name='loop', description='Toggle loop mode (off/single/queue)')
async def loop(ctx, mode: str = None):
    """Toggle loop mode"""
    queue = bot.player.get_queue(ctx.guild.id)

    if mode and mode.lower() in ['off', 'single', 'queue']:
        queue.loop_mode = mode.lower()
    else:
        loop_modes = ['off', 'single', 'queue']
        current_index = loop_modes.index(queue.loop_mode)
        queue.loop_mode = loop_modes[(current_index + 1) % len(loop_modes)]

    emojis = {'off': '❌', 'single': '🔂', 'queue': '🔁'}
    await ctx.send(f"{emojis[queue.loop_mode]} Loop mode: {queue.loop_mode}")

@bot.hybrid_command(name='remove', description='Remove a song from the queue')
async def remove(ctx, position: int):
    """Remove a song from the queue"""
    queue = bot.player.get_queue(ctx.guild.id)

    if not queue.queue:
        return await ctx.send("❌ Queue is empty")

    if not 1 <= position <= len(queue.queue):
        return await ctx.send(f"❌ Position must be between 1 and {len(queue.queue)}")

    queue_list = list(queue.queue)
    removed_song = queue_list[position - 1]

    # Remove from queue
    new_queue = deque()
    for i, song in enumerate(queue_list):
        if i != position - 1:
            new_queue.append(song)

    queue.queue = new_queue
    await ctx.send(f"🗑️ Removed **{removed_song.title}** from queue")

# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing required argument: {error.param}")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Invalid argument: {error}")
    else:
        logger.error(f"Unexpected error: {error}")
        await ctx.send("❌ An unexpected error occurred")

# Run the bot
if __name__ == "__main__":
    # Check for required environment variables
    if not config.DISCORD_TOKEN:
        print("❌ DISCORD_TOKEN environment variable is required")
        exit(1)

    if not config.SPOTIFY_CLIENT_ID or not config.SPOTIFY_CLIENT_SECRET:
        print("⚠️  Spotify credentials not found. Spotify features will be disabled.")

    print("🤖 Starting Discord Music Bot...")
    print("📋 Available commands:")
    print("  !join - Join voice channel")
    print("  !play <query> - Play a song")
    print("  !pause/!resume - Control playback")
    print("  !skip - Skip current song")
    print("  !stop - Stop and clear queue")
    print("  !queue - Show queue")
    print("  !volume <0-100> - Set volume")
    print("  !shuffle - Toggle shuffle")
    print("  !loop [off/single/queue] - Set loop mode")
    print("  !clear - Clear queue")
    print("  !remove <position> - Remove song from queue")
    print("\n🚀 Bot is ready! Use the commands in Discord.")

    try:
        bot.run(config.DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
