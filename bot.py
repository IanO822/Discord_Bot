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
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3
from utils import update_item_data
from utils import build_index
from utils import search_items
from utils import format_item_short
from utils import mistrade_calculator
from utils import check_changed_item
from utils import check_parameter
from utils import manage_build
from utils import regular_expression
from utils import split_log_result

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True
PREFIX = "!"
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

BOT_ADMIN = {
    "ian0822", "1an0822", #擁有者
    ".ssusus.", "curtis_5566", "xmas__" #管理員
            } 

# ----------------- 載入資料並建立索引 -----------------
ITEM_DATA_PATH = "item_data.json"
item_data = {}
search_index = []
CURRENCYMAP = {
    "experience_bottle": "<:experience_bottle:1397875984484798475> XP",
    "dragon_breath": "<:concentrated_experience:1397875964796469389> CXP",
    "sunflower": "<:hyperexperience:1397875942000558223> HXP",
    "prismarine_shard": "<:crystalline_shard:1397875907338960986> CS",
    "prismarine_crystals": "<:compressed_crystalline_shard:1397875885146640404> CCS",
    "nether_star": "<:hyper_crystalline_shard:1397875853693554688> HCS",
    "gray_dye": "<:archos_ring:1397875715105624145> AR",
    "firework_star": "<:hyperchromatic_archos_ring:1397875820386848852> HAR"
}

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
    print(f"🟢 Bot 啟動於：{socket.gethostname()} | PID: {os.getpid()}")

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
        doCalculateMistrader = False
        parameter = None
        if bool(re.search(r"(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+(XP|CXP|HXP|CS|CCS|HCS|AR|HAR)(?:\s+(0|1))?(?:\s+(0|1))?(?:\s+(.+))?", message.content, re.IGNORECASE)):
            start = message.content.rfind("<") + 1
            end = message.content.rfind(">")
            parameter = check_parameter(message.content[start:end])
            if parameter:
                doCalculateMistrader = True
            else:
                doCalculateMistrader = False
        originMessage = None
        # 1. 檢查附件
        if message.attachments:
            attachment = message.attachments[0]
            if attachment.filename.endswith('.txt'):
                async with aiohttp.ClientSession() as session:
                    async with session.get(attachment.url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            with open(f'tradelog.txt', 'wb') as f:
                                f.write(data)
                            originMessage = "DONE"
        # 2. 沒有附件的情況：取 !mistrade 後面的文字
        else:
            originMessage = message.content[len("!mistrade "):].strip()
            with open("tradelog.txt", "w", encoding="utf-8") as f:
                f.write(originMessage)
        if not originMessage:
            await message.reply("<:ghost_technology_4:1293185676086481039> 請提供有效的內容或 .txt 附件。")
            return
        #過濾訊息
        filtered = {}
        pageDataTemp = []
        originMessage = ""
        with open("tradelog.txt", mode="r", encoding="utf-8") as file:
            lines = file.readlines()
            for i in range(len(lines)):
                regexResult = regular_expression(lines[i])
                if isinstance(regexResult, dict):
                    pageDataTemp.append(regexResult)
                elif isinstance(regexResult, tuple) and regexResult[0] > 0:
                    pageNumber = regexResult[0]
                    maxPageNumber = regexResult[1]
                    filtered.update({pageNumber:pageDataTemp})
                    pageDataTemp = []
        #計算結果
        if filtered and parameter:
            parameter_setting = (
    f'**:gear:參數 (Parameters):** \n'
    f'└ 買價(Buy Price): {parameter["buyPrice"]} {parameter["unit"]}\n'
    f'└ 賣價(Sell Price): {parameter["sellPrice"]} {parameter["unit"]}\n'
    f'└ 忽略店主(Ignore Owner): {parameter["ignore_owner"]} \n'
    f'└ 忽略正確交易(Ignore Correct Trade): {parameter["ignore_correct_trade"]} \n'
    f'└ NBT 標籤(NBT tag): {parameter["nbt"] if parameter["nbt"] else "無 (None)"} \n')
            for log in split_log_result(("<:ghost_technology_4:1293185676086481039> 參數格式錯誤，將不計算錯誤交易者。\n" if (not doCalculateMistrader and parameter != None) else "") + '<:ghost_technology:1292853415465975849> 正在計算交易結果...\n' + parameter_setting):   
                await message.reply(log)
            #清除tradelog.txt
            with open("tradelog.txt", "w", encoding="utf-8") as f:
                f.write("")
            playerLog = {}
            doIgnoreShopkeeper = parameter.get("ignore_owner", False) if isinstance(parameter, dict) else False
            #pageResult = ""
            for pageNumber, pageData in filtered.items():
                result = check_changed_item(pageData, playerLog, doIgnoreShopkeeper, parameter["nbt"])
                playerLog = result[1]
            #     pageResult += ("📄 以下是第**" + str(pageNumber) + "/" + str(maxPageNumber) + "**頁的結果: \n" + result[0])
            # for log in split_log_result(pageResult):
            #     await message.channel.send(log)
            logResult = ""
            mistradeMessage = ""
            wrongPayment = {}
            wrongUsage = {}
            userMistraded = False
            #建立錯誤交易名單
            if doCalculateMistrader:
                wrongPayment, wrongUsage = mistrade_calculator(playerLog, parameter["unit"], parameter["buyPrice"], parameter["sellPrice"])
            
            for playerName, changedItems in playerLog.items():
                fixedName = playerName.replace("_", "\\_")
                userMistraded = False
                mistradeMessage = ""
                if any(value != 0 for value in changedItems.values()):
                    #檢測玩家是否支付錯數量
                    if wrongPayment.get(playerName, False):
                        userMistraded = True
                        if wrongPayment[playerName] > 0:
                            mistradeMessage +=  f"@{fixedName} 多支付了 (overpaid) {wrongPayment[playerName]} {parameter['unit']} \n"
                        elif wrongPayment[playerName] < 0:
                            mistradeMessage += f"@{fixedName} 欠了 (underpaid) {-wrongPayment[playerName]} {parameter['unit']} \n"
                    #檢測玩家是否支付錯貨幣
                    if wrongUsage.get(playerName, False):
                        userMistraded = True
                        mistradeMessage += f"@{fixedName} 支付了錯誤的貨幣 (paid with the wrong currency): {wrongUsage[playerName]} \n"
                    
                    #是否顯示正確交易者
                    if parameter["ignore_correct_trade"] and userMistraded:
                        logResult += ":warning: <:ghost_technology_5:1293185945461461013> " + "**" + fixedName + "**: \n"
                    elif parameter["ignore_correct_trade"] == False:
                        logResult += (":warning: <:ghost_technology_5:1293185945461461013> " if userMistraded else "") + "**" + fixedName + "**: \n"
                    
                    for itemName, count in changedItems.items():
                        if count != 0 and not (parameter["ignore_correct_trade"] and not userMistraded):
                            logResult += " └ " + CURRENCYMAP.get(itemName, " ".join(word.capitalize() for word in itemName.split("_"))) + " " + str(count) + "\n"
                    if userMistraded:
                        logResult += "\n" + mistradeMessage
                    logResult += "\n"
            if logResult == "": logResult = "<:ghost_technology_4:1293185676086481039> 物品無變動 (No item changes were made)"
            for log in split_log_result(f"# 📜 交易結果 (Trade result) \n {logResult}"):
                await message.channel.send(log)
        else:
            await message.reply('<:ghost_technology_4:1293185676086481039> 格式錯誤，應為!mistrade 紀錄(或.txt) <買價 賣價 單位 [忽略店主] [忽略正確交易] [尋找特定nbt]>')

    # ----------------- Menta職業建構者 -----------------
    if message.content.startswith(f'{PREFIX}build '):
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