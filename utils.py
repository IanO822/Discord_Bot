import json
import os
import requests
import re
import google.generativeai as genai
from urllib.parse import urlparse, parse_qs


def update_item_data():
    url = "https://api.playmonumenta.com/items"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        with open("item_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print("✅ 成功更新 item_data.json！")
        return True

    except requests.RequestException as e:
        print(f"❌ 無法連線 API：{e}")
        return False
    
def build_index(data):
    #將資料名稱轉成小寫後儲存
    index = []
    for item_key, item in data.items():
        masterwork = int(item.get("masterwork", -1))
        if masterwork == -1 or masterwork >= 4:
            name = item.get("name", item_key).lower()
            index.append((item, name))
    return index

def search_items(query, index):
    #查詢時直接比對是否為子字串
    query_string = query.lower().strip()
    results = []
    for item, name in index:
        if query_string in name:
            results.append(item)
    return results

def format_stat_key(key: str) -> str:
    # 移除 _percent 或 _flat
    for suffix in ["_percent", "_flat"]:
        if key.endswith(suffix):
            key = key[:-len(suffix)]
            break
    # 每個詞首字母大寫
    return " ".join(word.capitalize() for word in key.split("_"))

def format_stat_value(value, locked: bool, is_percent: bool) -> str:
    if isinstance(value, float):
        value = round(value, 2)
    result = f"+ {value}" if value > 0 else  f"- {-value}"
    if is_percent:
        result += "%"
    if locked:
        result += "🔒"
    return result

def format_item_short(item):
    lines = []

    # 第一行：名稱
    name = item.get("name", "")
    masterwork = item.get("masterwork", -1)
    lines.append(name + " " + (masterwork + "★") if masterwork != -1 else name)

    # 第二行：類型與基底物品
    item_type = item.get("type")
    base_item = item.get("base_item")
    if item_type and base_item:
        lines.append(f"{item_type} - {base_item}")
    elif item_type:
        lines.append(item_type)

    # 第三行：Charm Power + Class
    if item_type and "charm" in item_type.lower():
        power = item.get("power")
        class_name = item.get("class_name")
        power_str = f"Charm Power: {'★' * power}" if power else None
        class_str = f"{class_name}" if class_name else None
        if power_str or class_str:
            lines.append(" - ".join(filter(None, [power_str, class_str])))

    # 第四行：stat
    stats = item.get("stats", {})
    for key, stat_value in stats.items():
        # 是否為 dict 結構（有 locked / value）
        if isinstance(stat_value, dict):
            value = stat_value.get("value")
            locked = stat_value.get("locked", False)
        else:
            value = stat_value
            locked = False

        is_percent = key.endswith("_percent")
        stat_name = format_stat_key(key)
        value_str = format_stat_value(value, locked, is_percent)
        lines.append(f"└ {stat_name} {value_str}")

    # 最後一行 : 地區、稀有度、類型、位置
    region = item.get("region")
    tier = item.get("tier")
    location = item.get("location")
    meta = " ".join(filter(None, [region, location, tier]))
    if meta:
        lines.append(meta)

    return "\n".join(lines)

def regular_expression(log_line):
    action_pattern = r'^\[\d{2}:\d{2}:\d{2}\] \[Render thread/INFO\]: \[System\] \[CHAT\] \d+\.\d+/(h|d|m) ago\s+[ac][+-]\s+(\w+)\s+f\s+(added|removed) x(\d+) (\w+)\s+f\.$'
    page_pattern = r'f(\d+)/(\d+)'
    action_match = re.search(action_pattern, log_line)
    page_match = re.search(page_pattern, log_line)
    if action_match:
        time_unit, username, action, count, item = action_match.groups()
        action = 1 if action == "added" else -1
        return {"user":username, "action":action, "item":item, "count":count}
    elif page_match:
        current_page = int(page_match.group(1))
        #total_pages = int(page_match.group(2))
        return current_page
    else:
        return False

def mistrade_calculator(filtered):
    amountChange = {"experience_bottle":0, "dragon_breath":0, "sunflower":0, "prismarine_crystals":0, "prismarine_shard":0, "nether_star":0, "gray_dye":0, "firework_star":0}
    CURRENCYMAP = {"experience_bottle":"XP", "dragon_breath":"CXP", "sunflower":"HXP", "prismarine_shard":"CS", "prismarine_crystals":"CCS", "nether_star":"HCS", "gray_dye":"AR", "firework_star":"HAR"}
    result = ""

    for action in filtered:
        if action["item"] in amountChange:
            amountChange[action["item"]] += int(action["count"]) * action["action"]

    for currency, amount in amountChange.items():
        if amount != 0:
            result += str(amount) + " " + CURRENCYMAP[currency] + "\n" 
    
    return result if result else "貨幣數量無變動"

def ai_calculate_mistrade(user_input: str):
    api_key = os.getenv('GOOGLE_TOKEN')
    genai.configure(api_key=api_key)

    # 指定模型為 gemini-2.0-flash-001
    model = genai.GenerativeModel(model_name="gemini-2.0-flash-001")

    prompt = f"""
    你是一個專門解析 Minecraft CoreProtect 外掛訊息的分析工具。

    請依據以下規則分析用戶輸入的聊天記錄，輸出格式為：
    {{玩家1: {{"物品名稱1": 數量, "物品名稱2": 數量}}, 玩家2: {{...}}}}

    ### 分析任務：
    1. 僅分析 CoreProtect 插件輸出的訊息，忽略非插件訊息。
    2. 辨識交易雙方的玩家名稱與物品變動數量。
    3. 統計每位玩家持有物品的最終變動數量（只記錄不為 0 的項目）。

    ### 替代詞規則（NBT → 名稱）：
    - experience_bottle → XP
    - dragon_breath → CXP
    - sunflower → HXP
    - prismarine_shard → CS
    - prismarine_crystals → CCS
    - nether_star → HCS
    - gray_dye → AR
    - firework_star → HAR
    - 若為其他 NBT，使用原始 NBT 名稱。


    ### 現在請依據以上規則，分析以下聊天紀錄：

    {user_input}
    """

    # 使用模型生成回應
    response = model.generate_content(prompt)

    return response.text

def manage_build(buildCommand, sender):
    # 解析名稱與連結
    if len(buildCommand) >= 3:
        build_name = buildCommand[2]
    op = ""
    if buildCommand[1] == "add" and len(buildCommand) >= 4:
        build_link = " ".join(buildCommand[3:])
        #檢查連結是否合法
        parsed = urlparse(build_link)
        if not parsed.netloc in ["odetomisery.vercel.app", "ohthemisery-psi.vercel.app"] or parsed.scheme != "https":
            return "build連結錯誤"
        # 建立新的 build 資料
        new_build = {
            build_name: {
                "連結": build_link,
                "作者": sender,
                "資訊": ""
            }
        }
    
        # 嘗試讀取已存在的 JSON 資料
        if os.path.exists("build.json"):
            with open("build.json", "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = {}
        else:
            data = {}
        # 更新資料
        if build_name not in data:
            data.update(new_build)
            op = "儲存"
        else:
            return "存在相同名稱build!"

    # 刪除舊的 build 資料
    elif buildCommand[1] == "remove":
        with open("build.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        if not os.path.exists("build.json"):
            return "❌ 找不到 build.json 檔案。"
        if build_name in data:
            if data[build_name]["作者"] == sender:
                del data[build_name]
                op = "刪除"
            else:
                return f"⛔ {sender} 不是作者。"
        else:
            return f"⚠️ 沒有找到名稱為「{build_name}」的 build。"
    
    #搜尋已存在build
    elif buildCommand[1] == "find" and len(buildCommand) >= 3:
        keyword = buildCommand[2].lower()
        with open("build.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        matched = []
        for name, info in data.items():
            if keyword in name.lower():
                matched.append((name, info))
        if not matched:
            return "🔍 沒有找到符合的 build 名稱。"
        else:
            top_results = matched[:5]
            # 建立結果訊息
            result_lines = ["🔎 找到以下符合的 build："]
            for name, info in top_results:
                result_lines.append(
                    f"# **{name}**\n"
                    f"└🔗 連結：[{name}]({info['連結']})\n"
                    f"└👤 作者：{info['作者']}\n"
                    f"└📝 資訊：{info.get('資訊', '（無）')}"
                )

            return "\n".join(result_lines)

    else:
        return f"❌ 指令格式錯誤!"
    # 寫回 JSON 檔案
    with open("build.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    if op == "儲存":
        return f"✅ 已成功{op}Build「 [{build_name}]({build_link}) 」！"
    elif op == "刪除":
        return f"✅ 已成功{op}Build「 {build_name} 」！"