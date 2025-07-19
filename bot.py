import discord
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'🤖 機器人已登入：{client.user}')

@client.event
async def on_message(message):
    print(f'收到訊息：{message.content}')
    if message.author == client.user:
        return

    if message.content.startswith('!查道具'):
        await message.channel.send('🔍 ')

client.run(TOKEN)