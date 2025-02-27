
import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio

DISCORD_TOKEN = "your_token_goes_here"
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# YTDL options
ytdl_format_options = {
    "format": "bestaudio/best",
    "restrictfilenames": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    "source_address": "0.0.0.0"
}
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)
ffmpeg_options = {"options": "-vn"}

class MusicPlayer:
    def __init__(self):
        self.queue = []
        self.loop = False
        self.current_url = None

    async def get_audio_source(self, url):
        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

            if "entries" in data:
                data = data["entries"][0]

            return discord.FFmpegPCMAudio(data["url"], **ffmpeg_options), data["title"]
        except Exception as e:
            print(f"Error extracting audio: {e}")
            return None, None

player = MusicPlayer()

@bot.command(name="join", help="Bot joins your voice channel")
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        # Check if already connected to the same channel
        if ctx.voice_client and ctx.voice_client.channel.id == channel.id:
            await ctx.send(f"Already connected to {channel.name}")
            return

        if ctx.voice_client:
            await ctx.voice_client.move_to(channel)
        else:
            await channel.connect()
        await ctx.send(f"Connected to {channel.name}")
    else:
        await ctx.send("You must be in a voice channel for me to join.")

@bot.command(name="leave", help="Bot leaves the voice channel")
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Disconnected from voice channel")
    else:
        await ctx.send("I'm not in a voice channel.")

@bot.command(name="loop", help="Toggles loop mode")
async def toggle_loop(ctx):
    player.loop = not player.loop
    await ctx.send(f"Looping is now {'enabled' if player.loop else 'disabled'}.")

@bot.command(name="play", help="Plays a song from YouTube")
async def play(ctx, *, url: str):
    if not ctx.voice_client:
        await ctx.invoke(join)

    if not ctx.voice_client:
        return  # Join failed

    player.queue.append(url)
    await ctx.send(f"Added to queue: {url}")

    if not ctx.voice_client.is_playing():
        await play_next(ctx)

async def play_next(ctx):
    if not player.queue:
        await ctx.send("Queue is empty!")
        return

    url = player.queue[0]
    player.current_url = url

    source, title = await player.get_audio_source(url)
    if not source:
        await ctx.send(f"Failed to play: {url}. Skipping...")
        player.queue.pop(0)
        await play_next(ctx)
        return

    def after_playing(error):
        if error:
            print(f"Error: {error}")

        # Use a coroutine to handle the next song
        coro = handle_after_playing(ctx)
        fut = asyncio.run_coroutine_threadsafe(coro, bot.loop)
        try:
            fut.result()
        except Exception as e:
            print(f"Error in after_playing: {e}")

    ctx.voice_client.play(source, after=after_playing)
    await ctx.send(f"**Now playing:** {title}")

async def handle_after_playing(ctx):
    if player.loop and player.current_url:
        player.queue.append(player.current_url)

    if player.queue:
        player.queue.pop(0)

    if player.queue:
        await play_next(ctx)

@bot.command(name="skip", help="Skips the current song")
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Skipped the current song")
    else:
        await ctx.send("No song is playing.")

@bot.command(name="queue", help="Shows the current queue")
async def show_queue(ctx):
    if not player.queue:
        await ctx.send("Queue is empty!")
        return

    queue_list = "\n".join([f"{i+1}. {url}" for i, url in enumerate(player.queue)])
    await ctx.send(f"**Current Queue:**\n{queue_list}")

@bot.command(name="pause", help="Pauses the current song")
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Paused the current song")
    else:
        await ctx.send("No audio is playing.")

@bot.command(name="resume", help="Resumes a paused song")
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Resumed the current song")
    else:
        await ctx.send("Nothing is paused.")

@bot.command(name="stop", help="Stops the song and clears the queue")
async def stop(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop()
        player.queue.clear()
        await ctx.send("Music stopped and queue cleared.")
    else:
        await ctx.send("I'm not in a voice channel.")

@bot.event
async def on_ready():
    print(f"Bot is ready! Logged in as {bot.user}")
    activity = discord.Activity(type=discord.ActivityType.listening, name="!play commands")
    await bot.change_presence(activity=activity)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)