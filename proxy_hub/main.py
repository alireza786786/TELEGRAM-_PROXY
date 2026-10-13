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

# ==================== دریافت تنظیمات از گیت‌هاب ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("CHAT_ID", "").strip()

# فایل حافظه برای ذخیره پروکسی‌های ارسال‌شده در دفعات قبل
HISTORY_FILE = "proxy_hub/sent_proxies.txt"

CHANNELS_LIST = [
    "TelMTProto", "ProxyMTProto", "iMTProto", "ProxyHagh",
    "proxies_free", "MTProtoProxies", "ProxyMTProto_Tel",
    "DailyMTProto", "VpnMTProto", "IR_Proxy", "ProxiesMTProto",
    "FreeProxyIran", "ProxyFast", "ProxyNational", "ProxySolid", "AlphaProxies"
]

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

CURATED_QUOTES = [
    "«در میان زمستان دریافتم که در وجود من، تابستانی شکست‌ناپذیر پنهان است.» — آلبر کامو 🌿",
    "«آب اگر راکد بماند بو می‌گیرد؛ روان باش و از هر سنگلاخی راهی بساز.» ✨",
    "«بزرگ‌ترین شجاعت این است که در دنیایی پر از تکرار، خودت باشی و مسیرت را بسازی.» 💫",
    "«هیچ تاریکی آن‌قدر ماندگار نیست که بتواند از طلوع خورشید جلوگیری کند.» ☀️",
    "«زندگی یا یک ماجراجویی جسورانه است، یا هیچ چیز دیگری نیست.» — هلن کلر 🚀",
    "«نور از میان زخم‌ها وارد روح آدمی می‌شود؛ سختی‌ها زادگاه روشنایی‌اند.» — مولانا 🕯",
    "«آنچه در جستجوی آنی، خود در جستجوی توست.» — شمس تبریزی 🌌",
    "«قدرت واقعی در آرامش نهفته است؛ طوفان‌ها همیشه زودگذرند.» 🌊",
    "«برای دیدن افق‌های تازه، گاه باید شهامت دور شدن از ساحل‌های امن را داشت.» ⛵️",
    "«ارتباط بی‌پایان، جریان بی‌پایان زندگی در رگ‌های زمان است؛ آزاد و متصل بمانید.» 🌐"
]

ARTISTIC_PROMPTS = [
    "surreal cosmic aurora borealis over mystical glowing mountains, starry galaxy sky, nebula reflections, ethereal lighting, highly detailed 8k wallpaper, award winning nature photography",
    "aesthetic cyberpunk city at night with neon reflections on wet street, glowing lanterns, futuristic flying drones, deep cinematic mood, blade runner style, octane render 8k",
    "hyper-realistic 3D abstract floating iridescent glass crystals, flowing liquid gold ribbons, smooth gradient backdrop, luxury aesthetic, clean octane render, 8k resolution, minimalist masterpiece",
    "enchanted bioluminescent fantasy forest, glowing ethereal trees and flowers, misty magical atmosphere, fairytale landscape, cinematic depth of field, ghibli aesthetics hyper-detailed",
    "sleek futuristic abstract technology lines, glowing turquoise and golden fiber optics, subtle dark background, elegant composition, wallpaper worthy, clean high-tech concept art 8k"
]

PROXY_REGEX = re.compile(
    r'(?:https?:\/\/t\.me\/(?:proxy\?|socks\?)|tg:\/\/(?:proxy\?|socks\?))[^\s"\'<>]+',
    re.IGNORECASE
)

def normalize_link(link: str) -> str:
    clean = link.strip().replace("http://", "https://")
    if clean.startswith("https://t.me/proxy?"):
        clean = clean.replace("https://t.me/proxy?", "tg://proxy?")
    elif clean.startswith("https://t.me/socks?"):
        clean = clean.replace("https://t.me/socks?", "tg://socks?")
    return clean

def get_tehran_time() -> str:
    tz = pytz.timezone('Asia/Tehran')
    return datetime.now(tz).strftime("%Y/%m/%d - %H:%M")

def load_sent_history() -> set:
    """خواندن لیست پروکسی‌های ارسال‌شده در دفعات قبل"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return set(line.strip() for line in f if line.strip())
        except Exception:
            return set()
    return set()

def save_sent_history(new_proxies: list):
    """ذخیره پروکسی‌های ارسالی جدید در تاریخچه دائم"""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    existing = list(load_sent_history())
    combined = existing + new_proxies
    # فقط ۳۰۰۰ پروکسی اخیر را نگه می‌دارد تا فایل سنگین نشود
    combined = combined[-3000:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(combined))

def get_unique_artistic_image() -> str:
    seed = random.randint(1000000, 99999999) + int(time.time() % 10000)
    prompt = random.choice(ARTISTIC_PROMPTS)
    encoded = urllib.parse.quote(prompt)
    return f"https://image.pollinations.ai/prompt/{encoded}?width=1280&height=720&seed={seed}&nologo=true"

def collect_proxies():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
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
            print(f"[!] خطا در {ch}: {e}")

    return proxies_list

def send_file_to_channel(filename: str, caption: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    with open(filename, "rb") as f:
        data = {
            "chat_id": CHAT_ID,
            "caption": caption,
            "parse_mode": "HTML",
            "reply_markup": json.dumps(INLINE_KEYBOARD)
        }
        r = requests.post(url, data=data, files={"document": f}, timeout=45)
        return r.json()

def send_photo_to_channel(photo_url: str, caption: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    data = {
        "chat_id": CHAT_ID,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "HTML",
        "reply_markup": json.dumps(INLINE_KEYBOARD)
    }
    r = requests.post(url, data=data, timeout=45)
    return r.json()

def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("[X] مقادیر BOT_TOKEN یا CHAT_ID خالی است!")
        return

    print("[*] در حال بررسی ۱۹ کانال مرجع...")
    scraped_proxies = collect_proxies()
    
    # مقایسه با تاریخچه: فیلتر کردن پروکسی‌هایی که قبلاً ارسال شده‌اند
    already_sent = load_sent_history()
    fresh_proxies = [p for p in scraped_proxies if p not in already_sent]

    print(f"📊 پروکسی‌های جمع‌آوری شده: {len(scraped_proxies)}")
    print(f"🆕 پروکسی‌های کاملاً جدید و دست‌اول: {len(fresh_proxies)}")

    # شرط هوشمند: اگر پروکسی‌های جدید به حداقل ۱۷ عدد نرسیده باشند، اصلاً پست ارسال نمی‌شود!
    if len(fresh_proxies) < 17:
        print("[⛔️] هیچ آپدیت جدیدی در کانال‌های مرجع مشاهده نشد. جهت جلوگیری از ارسال تکراری، پیامی به کانال فرستاده نشد.")
        return

    time_str = get_tehran_time()
    filename = "Fresh_Proxies.txt"

    # ذخیره فایل فقط با پروکسی‌های تازه
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# Brand New Telegram Proxies\n# Time: {time_str}\n# Count: {len(fresh_proxies)}\n\n")
        f.write("\n".join(fresh_proxies))

    # ۱. ارسال فایل جدید
    file_caption = (
        f"📁 <b>بسته پروکسی‌های دست‌اول و تازه تلگرام</b>\n\n"
        f"📊 <b>تعداد پروکسی‌های جدید این پارت:</b> <code>{len(fresh_proxies)}</code> عدد\n"
        f"⏰ <b>زمان دریافت آخرین آپدیت:</b> <code>{time_str}</code>\n"
        f"🛡 <b>پروتکل‌ها:</b> MTProto & SOCKS5\n\n"
        f"📌 <b>راهنما:</b>\n"
        f"▫️ این لیست حاوی جدیدترین پروکسی‌های لحظه‌ای است.\n"
        f"▫️ هنگام اتصال، فیلترشکن خود را خاموش کنید."
    )
    print("[*] در حال ارسال فایل...")
    send_file_to_channel(filename, file_caption)

    # ۲. ارسال ۱۷ پروکسی برتر با چیدمان اختصاصی
    top_17 = fresh_proxies[:17]

    row1 = f'<a href="{top_17[0]}">پروکسی</a> | <a href="{top_17[1]}">پروکسی</a>'
    row2 = f'<a href="{top_17[2]}">پروکسی</a> | <a href="{top_17[3]}">پروکسی</a> | <a href="{top_17[4]}">پروکسی</a>'
    row3 = f'<a href="{top_17[5]}">پروکسی</a> | <a href="{top_17[6]}">پروکسی</a> | <a href="{top_17[7]}">پروکسی</a>'
    row4 = f'<a href="{top_17[8]}">پروکسی</a> | <a href="{top_17[9]}">پروکسی</a> | <a href="{top_17[10]}">پروکسی</a>'
    row5 = f'<a href="{top_17[11]}">پروکسی</a> | <a href="{top_17[12]}">پروکسی</a> | <a href="{top_17[13]}">پروکسی</a>'
    row6 = f'<a href="{top_17[14]}">پروکسی</a> | <a href="{top_17[15]}">پروکسی</a> | <a href="{top_17[16]}">پروکسی</a>'

    layout_block = f"{row1}\n{row2}\n{row3}\n{row4}\n{row5}\n{row6}"
    selected_quote = random.choice(CURATED_QUOTES)
    ai_photo = get_unique_artistic_image()

    photo_caption = (
        f"💎 <b>منتخب ۱۷ پروکسی جدید و تازه‌نفس</b>\n"
        f"⏰ <code>{time_str}</code>\n\n"
        f"{selected_quote}\n\n"
        f"👇 <b>جهت اتصال، لمس کنید:</b>\n\n"
        f"{layout_block}\n\n"
        f"🌐 <i>اتصال آزاد، سریع و پایدار</i>"
    )

    print("[*] در حال ارسال تصویر و هایپرلینک‌ها...")
    send_photo_to_channel(ai_photo, photo_caption)

    # به‌روزرسانی حافظه دائم
    save_sent_history(fresh_proxies)

    if os.path.exists(filename):
        os.remove(filename)

if __name__ == "__main__":
    main()
