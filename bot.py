import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import json
import aiohttp
import asyncio
import socket
import re
import random
import logging
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3
from utils import update_item_data
from utils import build_index
from utils import search_items
from utils import format_item_short
from utils import manage_build
from utils import split_log_result
from utils import handle_trade_log
from utils import manage_pig_vip
from utils import mouse_click_safe
from utils import mouse_move_safe
from utils import screenshot_with_cursor
from utils import parse_duration
from utils import press_key_safe
from collections import defaultdict

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("safe_control_bot")

TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True
PREFIX = os.getenv("BOT_PREFIX")
ADMIN_IDS = [i for i in os.getenv("ADMIN_IDS").split()]
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

BOT_ADMIN = {
    "ian0822", "1an0822", #擁有者
    ".ssusus.", "curtis_5566", "xmas__" #管理員
            } 

# ----------------- 載入資料並建立索引 -----------------
ITEM_DATA_PATH = "item_data.json"
item_data = {}
search_index = []

current_folder = os.path.dirname(os.path.abspath(__file__))
music_folder = os.path.join(current_folder, "music")
metadata_list = []
for song_file in os.listdir(music_folder):
    if song_file.endswith(".mp3"):
        path = os.path.join(music_folder, song_file)
        try:
            audio = MP3(path, ID3=EasyID3)
            song_name = song_file[:-4]
            metadata_list.append({
                "檔名": song_name,
                "演出者": audio.get("artist", ["未知"])[0],
                "專輯": audio.get("album", ["無"])[0],
            })
        except Exception as e:
            print(f"⚠️ 無法讀取 {song_file}: {e}")
all_songs = [song["檔名"] for song in metadata_list]
kano_songs = [song["檔名"] for song in metadata_list if "鹿乃" in song["演出者"]]
random.shuffle(all_songs)
random.shuffle(kano_songs)

MUTED_ROLE_NAME = "Muted"

ALLOWED_KEYS = {
    "0","1","2","3","4","5","6","7","8","9",
    "a","b","c","d","e","f","g","h","i","j","k","l","m","n","o","p","q","r","s","t","u","v","w","x","y","z",
    "up","down","left","right",
    "space","enter","esc","tab","shift","ctrl","alt",
    "f1","f2","f3","f4","f5","f6","f7","f8","f9","f10","f11","f12"
}
MAX_DURATION = 10
control_lock = asyncio.Lock()

def load_and_index_data():
    global item_data, search_index
    with open(ITEM_DATA_PATH, "r", encoding="utf-8") as f:
        item_data = json.load(f)
    search_index = build_index(item_data)
    print("📦 物品資料載入完成，共載入", len(item_data), "筆資料")


load_and_index_data()

# ----------------- 主程式 -----------------
@bot.event
async def on_ready():
    print(f'🤖 機器人已登入：{bot.user}')
    try:
        user = await bot.fetch_user(ADMIN_IDS[0])
        await user.send(f"🟢 Bot 啟動於：{socket.gethostname()} | PID: {os.getpid()}")
    except:
        print(f"🟢 Bot 啟動於：{socket.gethostname()} | PID: {os.getpid()}")

@bot.event
async def on_member_join(member):
    
    GUILD_ID = 1261321655116890283
    ROLE_NAME = "member"
    if member.guild.id == GUILD_ID:
        role = discord.utils.get(member.guild.roles, name=ROLE_NAME)
        print(f"{member} 加入伺服器")
    
        role = discord.utils.get(member.guild.roles, name="member")
        print("找到角色:", role)

        # 檢查是不是機器人自己
        if member.bot:
            print("成員是機器人，跳過。")
            return

        # 檢查是否已有角色
        if role in member.roles:
            print("成員已經有該角色。")
            return

        try:
            await member.add_roles(role)
            print(f"成功給予 {member} 角色 {role}")
        except discord.Forbidden:
            print("❌ Forbidden! 機器人沒有權限加這個角色。")
        except discord.HTTPException as e:
            print("❌ 其他錯誤:", e)
        if role:
            await member.add_roles(role)
            print(f"已將 {ROLE_NAME} 分配給 {member.name}")
        else:
            print("找不到指定的身分組！")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # ----------------- 查詢指令 -----------------
    if message.content.startswith(f'{PREFIX}find '):
        itemsToFind = message.content[len(f"{PREFIX}find"):].strip()
        if not itemsToFind:
            await message.channel.send("<:ghost_technology_4:1293185676086481039> 請提供要查詢的名稱。")
            return
        await message.channel.send('🔍 正在搜尋 ' + str(itemsToFind) + "...")

        results = search_items(itemsToFind, search_index)

        if not results:
            await message.channel.send("<:ghost_technology_4:1293185676086481039> 找不到符合物品。")
            return
        
        msg_lines = []
        for item in results[:5]:
            msg_lines.append( "\n ----------------------------------"  + "\n" + format_item_short(item))

        if len(results) > 5:
            msg_lines.append(f"...以及其他 {len(results)-5} 筆結果，請嘗試更精確的關鍵字。")

        await message.channel.send("\n".join(msg_lines))

    # ----------------- 尋找錯誤交易 -----------------
    if message.content.startswith(f'{PREFIX}mistrade'):
        file_lines = []
        # 1. 檢查附件
        if message.attachments:
            attachment = message.attachments[0]
            if attachment.filename.endswith('.txt'):
                async with aiohttp.ClientSession() as session:
                    async with session.get(attachment.url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            text = data.decode('utf-8')
                            file_lines = text.splitlines()
                            originMessage = "DONE"
        
        # 2. 沒有附件的情況：取 !mistrade 後面的文字
        else:
            originMessage = message.content[len("!mistrade "):].strip()
            file_lines.append(originMessage)
        
        if not originMessage:
            await message.reply("<:ghost_technology_4:1293185676086481039> 請提供有效的內容或 .txt 附件。")
            return

        # 3. 處理交易紀錄
        pattern_1 = re.compile(r'\(x(-?\d+)/y(-?\d+)/z(-?\d+)\)(?!/)')
        pattern_2 = re.compile(r'\(x(-?\d+)/y(-?\d+)/z(-?\d+)/Project_Epic-plots\)')

        current_coords = None
        auto_detect = False
        trade_log = {}

        for i, line in enumerate(file_lines):
            match_2 = pattern_2.search(line)
            match_1 = pattern_1.search(line)
            page_pattern = re.compile(r'f\d+/\d+')
            #自動
            if match_2:
                x, y, z = map(int, match_2.groups())
                current_coords = (x, y, z)
                auto_detect = True

            #手動
            elif match_1:
                x, y, z = map(int, match_1.groups())
                current_coords = (x, y, z)
                auto_detect = False
        
            if auto_detect:
                previous_line = file_lines[i - 1] if i > 0 else "<無法取得前一行>"
                if not page_pattern.search(previous_line):
                    if current_coords in trade_log:
                        trade_log[current_coords].append(previous_line)
                    elif current_coords != None:
                        trade_log[current_coords] = [previous_line]
        
            elif not auto_detect:
                if current_coords in trade_log:
                    trade_log[current_coords].append(line)
                elif current_coords != None:
                    trade_log[current_coords] = []

        if auto_detect:
            for key, value in trade_log.items():
                value.append("f1/1")
        
        fianl_message = f"# 📜 交易結果 (Trade result) \n"

        for coord, log in trade_log.items():
            result = handle_trade_log(message.content, log, coord, auto_detect)
            fianl_message += result[0]
            auto_detect = result[1]
        
        for log_line in split_log_result(fianl_message):
            await message.channel.send(log_line)

    # ----------------- Menta職業建構者 -----------------
    if message.content.startswith(f'{PREFIX}build'):
        buildCommand = [word for word in message.content.split()]
        if len(buildCommand) >= 2:
            result = manage_build(buildCommand, message.author.name)
            for line in split_log_result(result):
                await message.channel.send(line)
        else:
            await message.channel.send('<:ghost_technology_4:1293185676086481039> 格式錯誤')
            
    # ----------------- 管理員功能 -----------------
    if message.content.startswith(f"{PREFIX}updateAPI"):
        username = message.author.name

        if username not in BOT_ADMIN:
            await message.channel.send(f"⛔ {username} 沒有權限更新資料。")
            return

        await message.channel.send(f"🔄 開始更新道具資料...")

        success = update_item_data()
        if success:
            load_and_index_data()
            await message.channel.send("✅ 成功更新道具資料！")
        else:
            await message.channel.send("<:ghost_technology_4:1293185676086481039> 更新失敗，請稍後再試。")
    
    if message.content.startswith(f"{PREFIX}pig"):
        username = message.author.name

        if username not in BOT_ADMIN:
            await message.channel.send(f"⛔ {username} 沒有權限更新資料。")
            return

        pig_vip_command = message.content.split()

        if len(pig_vip_command) >= 3:
            result = manage_pig_vip(pig_vip_command[1], pig_vip_command[2])
            await message.channel.send(result)
        
        elif len(pig_vip_command) == 2:
            if pig_vip_command[1] == "list":
                result = manage_pig_vip("list")
            elif pig_vip_command[1] in ["add", "remove"]:
                result = "❌ 請提供玩家ID!"
            await message.channel.send(result)

    content = message.content.strip()
    
    if content.startswith(f"{PREFIX}k"):
        user_id_str = str(message.author.id)
        username = message.author.name

        if user_id_str not in ADMIN_IDS:
            await message.channel.send(f"⛔ {username} 沒有權限執行操作。")
            return

        # 切分參數
        parts = content.split()
        # parts[0] == "!k"
        if len(parts) < 2:
            await message.channel.send("❌ 指令格式：`!k <key> [duration]`")
            return

        key_arg = parts[1].lower()
        duration_arg = parts[2] if len(parts) >= 3 else "0"

        # 驗證 key
        if key_arg not in ALLOWED_KEYS:
            await message.channel.send(f"❌ 按鍵 `{key_arg}` 未被允許。")
            return

        # 解析 duration
        try:
            duration = parse_duration(duration_arg)
        except ValueError:
            await message.channel.send("❌ 錯誤的 duration（例如: 2, 2s 或 500ms）。")
            return

        # enforce bounds
        if duration < 0:
            await message.channel.send("❌ duration 不能為負數。")
            return
        if duration > MAX_DURATION:
            await message.channel.send(f"❌ duration 超過最大限制 {MAX_DURATION} 秒。")
            return

        # 取得鎖並執行（避免併發）
        async with control_lock:
            await message.channel.send(f"⏳ 執行中:按下 `{key_arg}` 持續 {duration} 秒 ...")
            try:
                await press_key_safe(key_arg, duration)
            except Exception as e:
                logger.exception("press_key 失敗")
                await message.channel.send(f"❌ 執行失敗：{e}")
                return

            # 截圖並上傳（上傳完刪除檔案）
            try:
                path = await asyncio.to_thread(screenshot_with_cursor)
                file = discord.File(path)
                await message.channel.send("✅ 執行完畢", file=file)
            except Exception as e:
                logger.exception("截圖或上傳失敗")
                await message.channel.send(f"⚠️ 無法截圖或上傳：{e}")
            finally:
                # 清除檔案
                try:
                    if 'path' in locals() and os.path.exists(path):
                        os.remove(path)
                except Exception:
                    logger.exception("刪除截圖失敗")

    if content.startswith(f"{PREFIX}m") and "mistrade" not in content:
        parts = content.split()
        async with control_lock:
            try:
                if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
                    # 移動滑鼠
                    x, y = int(parts[1]), int(parts[2])
                    await mouse_move_safe(x, y)
                    info_msg = f"滑鼠已移動到 ({x}, {y})"
                elif len(parts) == 3 and parts[1].lower() in ("l","r"):
                    # 按滑鼠鍵
                    button = "left" if parts[1].lower() == "l" else "right"
                    duration = parse_duration(parts[2])
                    if duration < 0 or duration > MAX_DURATION:
                        await message.channel.send(f"❌ duration 必須在 0~{MAX_DURATION} 秒")
                        return
                    await mouse_click_safe(button, duration)
                    info_msg = f"{button} 鍵已按下 {duration} 秒"
                else:
                    await message.channel.send("❌ 指令格式錯誤。範例：\n`!m x y`\n`!m l 1`")
                    return

                # 截圖並上傳
                path = screenshot_with_cursor()
                await message.channel.send(info_msg, file=discord.File(path))
                os.remove(path)
            except Exception as e:
                await message.channel.send(f"❌ 執行錯誤：{e}")
    
    await bot.process_commands(message)

@bot.command()
async def join(ctx):
    if ctx.author.voice:
        await ctx.author.voice.channel.connect(self_deaf=False)
    else:
        await ctx.send("你必須先加入語音頻道")

@bot.command()
async def leave(ctx):
    if ctx.author.name == ".ssusus.":
        await ctx.reply("你以為這有用嗎，口合 口合，怎麼不去洗1洗?")
        return
    if ctx.voice_client:
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        await ctx.voice_client.disconnect()
    else:
        await ctx.send("機器人不在語音頻道")

@bot.command()
async def play(ctx, *, playlist: str = "all"):
    if not ctx.voice_client:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect(self_deaf=False)
        else:
            await ctx.send("你必須先加入語音頻道")
            return

    if playlist == "kano":
        current_playerlist = kano_songs.copy()
        await ctx.send(f"開始隨機撥放播放清單 : 鹿乃")
    elif playlist == "all":
        current_playerlist = all_songs.copy()
        await ctx.send(f"開始隨機撥放播放清單 : 全部歌曲")
    else:
        await ctx.send("未知撥放清單")
        return

    random.shuffle(current_playerlist)
    ctx.current_playerlist = current_playerlist
    ctx.song_index = 1
    song_name = current_playerlist[0]

    if ctx.voice_client.is_playing():
        ctx.voice_client.stop()

    await play_song(ctx, song_name)

async def play_song(ctx, song_name):
    if not ctx.voice_client or not ctx.voice_client.is_connected():
        print("目前未連接語音頻道，取消播放")
        return

    # 播放資訊
    artist, album = "無", "無"
    for song in metadata_list:
        if song.get("檔名") == song_name:
            artist = song.get("演出者", "無")
            album = song.get("專輯", "無")
            break

    try:
        await ctx.send(f"🎵 曲名：{song_name}   🎤 演出者: {artist}  💿 專輯: {album}")
    except Exception as e:
        print(f"訊息傳送失敗: {e}")

    current_folder = os.path.dirname(os.path.abspath(__file__))
    music_path = os.path.join(current_folder, "music", f"{song_name}.mp3")

    if not os.path.isfile(music_path):
        await ctx.send("找不到該歌曲")
        print(f"找不到音檔: {music_path}")
        return

    source = discord.FFmpegPCMAudio(music_path, executable="C:/ffmpeg/bin/ffmpeg.exe")
    player = discord.PCMVolumeTransformer(source, volume=0.1)

    def after_play(error):
        if error:
            print(f"播放錯誤: {error}")
        elif ctx.voice_client and ctx.voice_client.is_connected():
            if ctx.song_index >= len(ctx.current_playerlist):
                ctx.song_index = 0
                random.shuffle(ctx.current_playerlist)

            next_song = ctx.current_playerlist[ctx.song_index]
            ctx.song_index += 1
            fut = asyncio.run_coroutine_threadsafe(play_song(ctx, next_song), bot.loop)
        else:
            print("已離開語音頻道，不再自動播放")

    ctx.voice_client.play(player, after=after_play)
    ctx.voice_client.source = player

@bot.command()
async def volume(ctx, vol: int):
    if not ctx.voice_client or not ctx.voice_client.source:
        await ctx.send("目前沒有播放音樂")
        return

    if vol < 0 or vol > 100:
        await ctx.send("音量請設定 0~100")
        return

    volume_value = vol / 1000
    ctx.voice_client.source.volume = volume_value
    await ctx.send(f"🔊 音量已設定為 {vol}%")

@bot.command()
async def changenick(ctx, *, new_nick):
    try:
        await ctx.guild.me.edit(nick=new_nick)
    except discord.Forbidden:
        pass
    except Exception as e:
        print(e)

@bot.event
async def on_command_error(ctx, error):
    pass

bot.run(TOKEN)