import json
import requests

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