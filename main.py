import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
import asyncio
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import youtube_dl
import os

# -------------------------
# Environment Variables
# -------------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")

# -------------------------
# Spotify Setup
# -------------------------
spotify = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET
))

# -------------------------
# Bot Setup
# -------------------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Music Queue
queues = {}

# -------------------------
# YouTube Download Options
# -------------------------
ydl_opts = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'extractaudio': True,
    'audioformat': "mp3",
    'outtmpl': 'downloads/%(title)s.%(ext)s',
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'cachedir': False,
}

# -------------------------
# Music Controls
# -------------------------
class MusicView(View):
    def __init__(self, ctx):
        super().__init__(timeout=None)
        self.ctx = ctx

    @discord.ui.button(label="⏯ Pause/Resume", style=discord.ButtonStyle.blurple)
    async def pause_resume(self, interaction: discord.Interaction, button: Button):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_connected():
            await interaction.response.send_message("Not connected to VC", ephemeral=True)
            return
        if vc.is_paused():
            vc.resume()
            await interaction.response.send_message("Resumed ▶️", ephemeral=True)
        else:
            vc.pause()
            await interaction.response.send_message("Paused ⏸", ephemeral=True)

    @discord.ui.button(label="⏭ Skip", style=discord.ButtonStyle.green)
    async def skip(self, interaction: discord.Interaction, button: Button):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("Skipped ⏭", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing playing", ephemeral=True)

    @discord.ui.button(label="⏹ Stop", style=discord.ButtonStyle.red)
    async def stop(self, interaction: discord.Interaction, button: Button):
        vc = interaction.guild.voice_client
        if vc:
            vc.stop()
            await vc.disconnect()
            queues[interaction.guild.id] = []
            await interaction.response.send_message("Stopped ⏹", ephemeral=True)
        else:
            await interaction.response.send_message("Not connected", ephemeral=True)

# -------------------------
# Play Command
# -------------------------
@bot.command()
async def play(ctx, *, search: str):
    if ctx.author.voice is None:
        await ctx.send("You must be in a voice channel first!")
        return

    channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        await channel.connect()

    # Initialize queue
    if ctx.guild.id not in queues:
        queues[ctx.guild.id] = []

    # Spotify Link
    if "spotify.com" in search:
        track = spotify.track(search)
        search = f"{track['name']} {track['artists'][0]['name']}"

    # Download from YouTube
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch:{search}", download=True)['entries'][0]
        url2 = info['url']
        source = discord.FFmpegPCMAudio(url2, executable="ffmpeg")

    # Add to queue
    queues[ctx.guild.id].append(source)

    vc = ctx.voice_client
    if not vc.is_playing():
        play_next(ctx.guild, vc)

    # Send embed with buttons
    embed = discord.Embed(title="Now Playing", description=search, color=discord.Color.green())
    view = MusicView(ctx)
    await ctx.send(embed=embed, view=view)

def play_next(guild, vc):
    if queues[guild.id]:
        source = queues[guild.id].pop(0)
        vc.play(source, after=lambda e: play_next(guild, vc))
    else:
        asyncio.create_task(vc.disconnect())

# -------------------------
# Stop Bot Cleanly
# -------------------------
@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        queues[ctx.guild.id] = []
        await ctx.send("Disconnected!")
    else:
        await ctx.send("Not connected!")

# -------------------------
# Run Bot
# -------------------------
bot.run(DISCORD_TOKEN)
