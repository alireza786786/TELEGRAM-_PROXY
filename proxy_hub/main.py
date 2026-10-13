import os
import re
import json
import time
import random
import urllib.parse
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz

# ==================== دریافت اطلاعات از Secrets گیت‌هاب ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("CHAT_ID", "").strip()

# منابع عمومی معتبر برای استخراج سریع پروکسی‌ها
CHANNELS_LIST = [
    "TelMTProto", "ProxyMTProto", "iMTProto", "ProxyHagh",
    "proxies_free", "MTProtoProxies", "ProxyMTProto_Tel",
    "DailyMTProto", "VpnMTProto", "IR_Proxy", "ProxiesMTProto",
    "FreeProxyIran", "ProxyFast", "ProxyNational", "ProxySolid", "AlphaProxies"
]

# دکمه‌های شیشه‌ای ۳ گانه
INLINE_KEYBOARD = {
    "inline_keyboard": [
        [
            {"text": "📢 کانال اصلی ضد فیلتر", "url": "https://t.me/Goodbaye_filtering"},
            {"text": "⭐️ کانال VIP کانفیگ", "url": "https://t.me/CONFIG_V2RAY_VIP"}
        ],
        [
            {"text": "🚀 اشتراک‌گذاری با دوستان", "url": "https://t.me/share/url?url=https://t.me/Goodbaye_filtering"}
        ]
    ]
}

# متن‌های انگیزشی و آموزنده
MOTIVATIONAL_QUOTES = [
    "«هیچ دیواری پایدار نیست؛ راه آگاهی و آزادی همواره گشوده خواهد شد.» ✨",
    "«ارتباط بی‌پایان، حق مسلم دنیای امروز است؛ متصل و مانا بمانید.» 🌐",
    "«محدودیت‌ها تنها اراده ما را برای ساختن مسیرهای نو استوارتر می‌کنند.» 💡",
    "«تاریک‌ترین ساعت شب، مژده‌بخش طلوع روشن‌ترین سپیده‌دم است.» ☀️",
    "«پشتکار یعنی تکرار امید و تلاش، حتی در سخت‌ترین شرایط ممکن.» 🚀",
    "«آگاهی بزرگ‌ترین سپر انسان در برابر تاریکی و ناامیدی است.» 🌿"
]

PROXY_REGEX = re.compile(
    r'(?:https?:\/\/t\.me\/(?:proxy\?|socks\?)|tg:\/\/(?:proxy\?|socks\?))[^\s"\'<>]+',
    re.IGNORECASE
)

# ==================== توابع کمکی ====================
def normalize_link(link: str) -> str:
    """استانداردسازی لینک برای حذف قطعی تکراری‌ها"""
    clean = link.strip().replace("http://", "https://")
    if clean.startswith("https://t.me/proxy?"):
        clean = clean.replace("https://t.me/proxy?", "tg://proxy?")
    elif clean.startswith("https://t.me/socks?"):
        clean = clean.replace("https://t.me/socks?", "tg://socks?")
    return clean

def get_tehran_time() -> str:
    tz = pytz.timezone('Asia/Tehran')
    return datetime.now(tz).strftime("%Y/%m/%d - %H:%M")

def get_unique_ai_image() -> str:
    """تولید تصویر با هوش مصنوعی و ذخیره در دیتابیس JSON برای عدم تکرار"""
    now = datetime.now()
    current_month = now.month
    current_year = now.year
    unique_seed = int(time.time())

    history_file = "sent_images.json"
    sent_seeds = []
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                sent_seeds = json.load(f)
        except Exception:
            sent_seeds = []

    # ساخت پرامپت اختصاصی و پویا بر اساس شبکه و ماه
    prompt = (
        f"futuristic digital network connection, cyber security glowing lights, "
        f"abstract telegram proxy speed background, 4k resolution, cinematic lighting, "
        f"ultra detailed, cyberpunk aesthetics, edition {current_year}_{current_month}"
    )
    encoded_prompt = urllib.parse.quote(prompt)
    ai_image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1280&height=720&seed={unique_seed}&nologo=true"

    # ذخیره شناسه جدید در تاریخچه
    sent_seeds.append({"time": get_tehran_time(), "seed": unique_seed, "url": ai_image_url})
    # نگه‌داری ۱۰۰ سابقه اخیر
    sent_seeds = sent_seeds[-100:]
    try:
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(sent_seeds, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[!] خطا در ذخیره تاریخچه تصاویر: {e}")

    return ai_image_url

def collect_proxies():
    """جمع‌آوری پروکسی‌ها از وب عمومی تلگرام"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    proxies_list = []
    seen = set()

    for ch in CHANNELS_LIST:
        url = f"https://t.me/s/{ch}"
        try:
            res = requests.get(url, headers=headers, timeout=12)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                matches = PROXY_REGEX.findall(res.text)
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if "proxy?" in href or "socks?" in href:
                        matches.append(href)

                for item in matches:
                    norm = normalize_link(item)
                    if norm not in seen and len(norm) > 15:
                        seen.add(norm)
                        proxies_list.append(norm)
        except Exception as e:
            print(f"[!] خطا در کانال {ch}: {e}")

    return proxies_list

def send_file_to_channel(filename: str, caption: str):
    """ارسال فایل جامع پروکسی‌ها به همراه دکمه‌های شیشه‌ای"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    with open(filename, "rb") as f:
        data = {
            "chat_id": CHAT_ID,
            "caption": caption,
            "parse_mode": "HTML",
            "reply_markup": json.dumps(INLINE_KEYBOARD)
        }
        r = requests.post(url, data=data, files={"document": f}, timeout=40)
        return r.json()

def send_photo_to_channel(photo_url: str, caption: str):
    """ارسال تصویر هوش مصنوعی + ۱۷ پروکسی با چیدمان اختصاصی"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    data = {
        "chat_id": CHAT_ID,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "HTML",
        "reply_markup": json.dumps(INLINE_KEYBOARD)
    }
    r = requests.post(url, data=data, timeout=40)
    return r.json()

# ==================== تابع اصلی ====================
def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("[X] مقادیر BOT_TOKEN یا CHAT_ID خالی است!")
        return

    print("[*] در حال جمع‌آوری پروکسی‌ها...")
    proxies = collect_proxies()
    total = len(proxies)
    print(f"[✓] تعداد پروکسی‌های یافت‌شده: {total}")

    if total == 0:
        print("[!] پروکسی جدیدی یافت نشد.")
        return

    time_str = get_tehran_time()
    filename = "Proxies_Daily.txt"

    # ذخیره فایل کامل پروکسی‌ها
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# Telegram Proxies Collection\n# Time: {time_str}\n# Count: {total}\n\n")
        f.write("\n".join(proxies))

    # ۱. آماده‌سازی پیام اول (فایل کامل)
    file_caption = (
        f"📁 <b>بسته جامع پروکسی‌های ضدفیلتر تلگرام</b>\n\n"
        f"📊 <b>تعداد کل پروکسی‌های یکتا:</b> <code>{total}</code> عدد\n"
        f"⏰ <b>زمان به‌روزرسانی:</b> <code>{time_str}</code>\n"
        f"🛡 <b>پروتکل‌ها:</b> MTProto & SOCKS5\n\n"
        f"📌 <b>راهنما:</b>\n"
        f"▫️ هنگام اتصال، فیلترشکن خود را خاموش کنید.\n"
        f"▫️ فایل را دانلود و درون تلگرام اجرا نمایید."
    )
    print("[*] در حال ارسال فایل به کانال...")
    res_file = send_file_to_channel(filename, file_caption)
    print("نتیجه ارسال فایل:", res_file.get("ok"))

    # ۲. آماده‌سازی ۱۷ پروکسی برتر با چیدمان دقیق تصویر شما:
    # ردیف اول: ۲ تایی
    # ردیف‌های دوم تا ششم: ۳ تایی
    top_17 = proxies[:17]
    while len(top_17) < 17 and len(proxies) > 0:
        top_17.append(proxies[len(top_17) % len(proxies)])

    row1 = f'<a href="{top_17[0]}">پروکسی</a> | <a href="{top_17[1]}">پروکسی</a>'
    row2 = f'<a href="{top_17[2]}">پروکسی</a> | <a href="{top_17[3]}">پروکسی</a> | <a href="{top_17[4]}">پروکسی</a>'
    row3 = f'<a href="{top_17[5]}">پروکسی</a> | <a href="{top_17[6]}">پروکسی</a> | <a href="{top_17[7]}">پروکسی</a>'
    row4 = f'<a href="{top_17[8]}">پروکسی</a> | <a href="{top_17[9]}">پروکسی</a> | <a href="{top_17[10]}">پروکسی</a>'
    row5 = f'<a href="{top_17[11]}">پروکسی</a> | <a href="{top_17[12]}">پروکسی</a> | <a href="{top_17[13]}">پروکسی</a>'
    row6 = f'<a href="{top_17[14]}">پروکسی</a> | <a href="{top_17[15]}">پروکسی</a> | <a href="{top_17[16]}">پروکسی</a>'

    layout_block = f"{row1}\n{row2}\n{row3}\n{row4}\n{row5}\n{row6}"

    quote = random.choice(MOTIVATIONAL_QUOTES)
    ai_photo = get_unique_ai_image()

    photo_caption = (
        f"💎 <b>منتخب ۱۷ پروکسی پرسرعت و پایدار</b>\n"
        f"⏰ <code>{time_str}</code>\n\n"
        f"{quote}\n\n"
        f"👇 <b>جهت اتصال، لمس کنید:</b>\n\n"
        f"{layout_block}\n\n"
        f"🌐 <i>اتصال آزاد، سریع و بدون قطعی</i>"
    )

    print("[*] در حال ارسال تصویر هوش مصنوعی و هایپرلینک‌ها...")
    res_photo = send_photo_to_channel(ai_photo, photo_caption)
    print("نتیجه ارسال تصویر:", res_photo.get("ok"))

    if os.path.exists(filename):
        os.remove(filename)

if __name__ == "__main__":
    main()
