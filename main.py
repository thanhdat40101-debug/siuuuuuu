import os
import json
import time
import re
import threading
import requests
from flask import Flask
from telebot import TeleBot, types

# ==================== WEB SERVER GIẢ (Chạy 24/7 trên Render/Replit) ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot HitClub MD5 độc lập đang chạy 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ==================== CẤU HÌNH BOT TELEGRAM ====================
BOT_TOKEN = "8935712977:AAHiPMo3dq16NzUnq2reuUw_UD0s1sPvQYs"
bot = TeleBot(BOT_TOKEN, threaded=True)

USER_SETTINGS = {}
HISTORY_MD5 = []
LAST_PHIEN_MD5 = None

# Thống kê mặc định theo đúng số liệu trong ảnh mẫu
STATS_MD5 = {"win": 5358, "loss": 5341}

# API URLS
KWIN_KEY = "8167b2c16888dae174a454f493022e22242f35288df59f41"
URL_KWIN_REALTIME = f"https://kwinstore.com/hitclub/md5/{KWIN_KEY}"
URL_KWIN_HISTORY = f"https://kwinstore.com/hitclub/md5/history/{KWIN_KEY}"
URL_PREDICT_TOMDAYY = "https://tool.tomdayy.site/dashboard.php?ajax_predict=1&source=hitclub_md5"

def get_user_setting(chat_id):
    if chat_id not in USER_SETTINGS:
        USER_SETTINGS[chat_id] = {"auto_md5": True}
    return USER_SETTINGS[chat_id]

def fetch_api_data(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            try:
                return response.json()
            except:
                return response.text
    except Exception as e:
        print(f"❌ Lỗi truy cập API ({url}): {e}")
    return None

def fetch_prediction_tomdayy():
    """Lấy dự đoán từ API tomdayy"""
    raw_response = fetch_api_data(URL_PREDICT_TOMDAYY)
    
    dudoan = "Tài"
    confidence = 55
    analysis = "Mã MD5 chưa cập nhật từ API - Dùng xác suất mặc định"

    if not raw_response:
        return dudoan, confidence, analysis

    if isinstance(raw_response, str):
        json_match = re.search(r'\{.*\}', raw_response)
        if json_match:
            try:
                raw_response = json.loads(json_match.group(0))
            except Exception as e:
                pass

    if isinstance(raw_response, dict):
        pred_raw = str(raw_response.get("prediction", raw_response.get("predict", raw_response.get("dudoan", "TÀI")))).upper()
        dudoan = "Tài" if ("TÀI" in pred_raw or "TAI" in pred_raw) else "Xỉu"
        
        conf_raw = str(raw_response.get("confidence", raw_response.get("rate", "55"))).replace("%", "")
        try:
            confidence = int(float(conf_raw))
        except:
            confidence = 55
            
        analysis = raw_response.get("analysis", raw_response.get("lydo", analysis))

    return dudoan, confidence, analysis

def parse_dice_and_result(item):
    """Trích xuất thông tin phiên từ API Kwin"""
    if not isinstance(item, dict):
        return "0", "Chưa cập nhật", "Chưa có", "Chưa cập nhật"

    # Phiên
    phien = "0"
    for p_key in ["phien", "phien_cu", "session", "sid", "id", "phien_id"]:
        if p_key in item and item[p_key] is not None:
            digits = re.sub(r'\D', '', str(item[p_key]))
            if digits:
                phien = digits
                break

    # Mã MD5
    md5_code = item.get("md5", item.get("hash", "Chưa  cập  nhật"))

    # Xúc xắc
    d1 = d2 = d3 = None
    for d_key in ["dice", "dices", "xucxac", "xuc_xac", "results"]:
        if d_key in item and isinstance(item[d_key], list) and len(item[d_key]) >= 3:
            try:
                d1, d2, d3 = int(item[d_key][0]), int(item[d_key][1]), int(item[d_key][2])
                break
            except:
                pass

    if d1 is None:
        pairs = [("dice1", "dice2", "dice3"), ("d1", "d2", "d3"), ("xucxac1", "xucxac2", "xucxac3")]
        for p1, p2, p3 in pairs:
            if all(k in item and item[k] is not None for k in [p1, p2, p3]):
                try:
                    d1, d2, d3 = int(item[p1]), int(item[p2]), int(item[p3])
                    break
                except:
                    pass

    if d1 is not None and d2 is not None and d3 is not None:
        total = d1 + d2 + d3
        dice_str = f"{d1} · {d2} · {d3} ➔ Tổng {total}"
        actual = "Tài" if total >= 11 else "Xỉu"
    else:
        actual = "Chưa có"
        for r_key in ["ketqua", "result", "tai_xiu", "taixiu"]:
            if r_key in item and item[r_key] is not None:
                r_val = str(item[r_key]).upper()
                if "TÀI" in r_val or "TAI" in r_val or r_val == "1":
                    actual = "Tài"
                    break
                elif "XỈU" in r_val or "XIU" in r_val or r_val == "2" or r_val == "0":
                    actual = "Xỉu"
                    break
        dice_str = "Chưa cập nhật" if actual == "Chưa có" else f"Tự động tính ➔ {actual}"

    return phien, dice_str, actual, md5_code

def parse_kwin_item(data):
    item = data
    if isinstance(item, dict):
        for key in ["data", "result", "list", "items"]:
            if key in item and isinstance(item[key], (list, dict)):
                item = item[key]
                break

    if isinstance(item, list) and len(item) > 0:
        item = item[0]

    if not isinstance(item, dict):
        return None

    phien, dice_str, actual, md5_code = parse_dice_and_result(item)
    dudoan, confidence, analysis = fetch_prediction_tomdayy()

    return {
        "phien": phien,
        "dice_str": dice_str,
        "actual": actual,
        "md5": md5_code,
        "dudoan": dudoan,
        "confidence": confidence,
        "analysis": analysis
    }

def generate_cau_string():
    if not HISTORY_MD5:
        return "🔴🔴🔴🔵🔵🔴"
    cau_icons = []
    for item in HISTORY_MD5[-6:]:
        res = str(item.get("actual", "Tài")).upper()
        cau_icons.append("🔴" if "TÀI" in res else "🔵")
    return "".join(cau_icons)

def format_beauty_message(kwin_json):
    """Định dạng tin nhắn GIỐNG 100% ẢNH MẪU"""
    parsed = parse_kwin_item(kwin_json)
    if not parsed or parsed["phien"] == "0":
        return "❌ Không thể phân tích dữ liệu API!"

    prev_phien = parsed["phien"]
    try:
        curr_phien = str(int(prev_phien) + 1)
    except:
        curr_phien = "2582651"

    actual_result = parsed["actual"]
    dice_str = parsed["dice_str"]
    md5_str = parsed.get("md5", "Chưa  cập  nhật")

    # Đánh giá Thắng/Thua
    last_status = "THẮNG"
    if len(HISTORY_MD5) > 1:
        prev_item = HISTORY_MD5[-2]
        if prev_item.get("dudoan", "").upper() != actual_result.upper():
            last_status = "THUA"
            
    eval_icon = "✅" if last_status == "THẮNG" else "❌"

    # Phần 1: Khung KẾT QUẢ SẢNH MD5
    result_block = (
        f"╭━━━━ KẾT QUẢ SẢNH MD5 ━━━━╮\n"
        f"📌 Phiên: {prev_phien}\n"
        f"🎲 Xúc xắc: {dice_str}\n"
        f"🔑 Mã MD5: {md5_str}\n"
        f"🎯 Kết quả: {actual_result}\n"
        f"{eval_icon} ĐÁNH GIÁ: {last_status}\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
    )

    dudoan = parsed["dudoan"]
    conf_num = parsed["confidence"]
    analysis = parsed["analysis"]
    win_icon = "🔴" if dudoan == "Tài" else "🔵"
    other_conf = round(100 - conf_num, 1)

    wins = STATS_MD5["win"]
    losses = STATS_MD5["loss"]
    total = wins + losses
    win_pct = round((wins / total * 100), 1) if total > 0 else 50.1

    cau_str = generate_cau_string()

    # Phần 2: Khung DỰ ĐOÁN THÔNG MINH
    msg = (
        f"{result_block}"
        f"╭━━━━ 🤖 DỰ ĐOÁN THÔNG MINH 🤖 ━━━━╮\n"
        f"1️⃣2️⃣ Phiên kế tiếp: {curr_phien}\n\n"
        f"🎯 Dự đoán: {dudoan} {win_icon}\n"
        f"📊 Độ tin cậy: {conf_num}%\n"
        f"⚖️ Trọng số MD5: Tài {conf_num}% · Xỉu {other_conf}%\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 Cơ sở phân tích:\n"
        f"• {analysis}\n\n"
        f"🌐 Cầu: {cau_str}\n"
        f"📊 Thành tích: {wins} Thắng · {losses} Thua ({win_pct}%)\n"
        f"💬 Nhập /thongke để xem chi tiết 10 tay gần nhất."
    )
    return msg

def get_thongke_text(limit=10):
    if not HISTORY_MD5:
        return "📊 **THỐNG KÊ DỰ ĐOÁN HITCLUB MD5**\nChưa có dữ liệu phiên gần đây."
    
    sub_list = HISTORY_MD5[-limit:]
    wins = sum(1 for item in sub_list if item.get('status_text') == 'THẮNG')
    total = len(sub_list)
    win_rate = round((wins / total * 100), 1) if total > 0 else 0.0

    msg = f"📊 **THỐNG KÊ {total} PHIÊN GẦN ĐÂY - HITCLUB MD5**\n"
    msg += f"📈 **Tỷ lệ Thắng:** `{wins}/{total}` (`{win_rate}%`)\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    
    for item in sub_list:
        status_str = f"{item.get('status_icon', '🟢')} {item.get('status_text', 'THẮNG')}"
        msg += f"🔹 `# {item['phien']}`: Dự đoán **{item.get('dudoan', 'Tài')}** ➡️ {status_str}\n"
    msg += "━━━━━━━━━━━━━━━━━━"
    return msg

# ==================== LUỒNG TỰ ĐỘNG CHẠY ====================
def auto_checker():
    global LAST_PHIEN_MD5
    
    while True:
        try:
            api_json = fetch_api_data(URL_KWIN_REALTIME)
            parsed = parse_kwin_item(api_json)
            
            if parsed and parsed["phien"] != "0" and parsed["actual"] != "Chưa có":
                curr_phien = parsed["phien"]
                
                if curr_phien != LAST_PHIEN_MD5:
                    LAST_PHIEN_MD5 = curr_phien

                    status_icon = "🟢"
                    status_text = "THẮNG"
                    if parsed["dudoan"].upper() == parsed["actual"].upper():
                        STATS_MD5["win"] += 1
                    else:
                        status_icon = "🔴"
                        status_text = "THUA"
                        STATS_MD5["loss"] += 1

                    parsed["status_icon"] = status_icon
                    parsed["status_text"] = status_text
                    
                    HISTORY_MD5.append(parsed)
                    if len(HISTORY_MD5) > 100:
                        HISTORY_MD5.pop(0)

                    msg = format_beauty_message(api_json)
                    
                    for chat_id, settings in list(USER_SETTINGS.items()):
                        if settings.get("auto_md5", True):
                            try:
                                bot.send_message(chat_id, msg)
                            except Exception as send_err:
                                print(f"⚠️ Không thể gửi tới {chat_id}: {send_err}")
        except Exception as e:
            print(f"❌ Lỗi Auto Checker: {e}")
        
        time.sleep(5)

# ==================== LỆNH BOT TELEGRAM ====================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    chat_id = message.chat.id
    get_user_setting(chat_id)
    bot.reply_to(
        message, 
        "🤖 **BOT TRA CỨU HITCLUB MD5 KWIN AUTOMATIC**\n\n"
        "Bot sẽ tự động báo kết quả phiên mới 24/7.\n"
        "Nhập `/thongke` hoặc `/11` để xem danh sách lịch sử!"
    )

@bot.message_handler(commands=['11', 'thongke'])
def send_thongke_command(message):
    msg = get_thongke_text(10)
    bot.reply_to(message, msg, parse_mode="Markdown")

def run_bot():
    print("🚀 Bot HitClub MD5 độc lập đã khởi động...")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=30)
        except Exception as e:
            print(f"⚠️ Khôi phục kết nối Bot sau 5s... Lỗi: {e}")
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    threading.Thread(target=auto_checker, daemon=True).start()
    run_bot()
