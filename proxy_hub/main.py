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

# ==================== دریافت تنظیمات از سکرت‌های گیت‌هاب ====================
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

# ==================== گنجینه متن‌های فاخر و جذاب ====================
CURATED_QUOTES = [
    "«در میان زمستان دریافتم که در وجود من، تابستانی شکست‌ناپذیر پنهان است.» — آلبر کامو 🌿",
    "«آب اگر راکد بماند بو می‌گیرد؛ روان باش و از هر سنگلاخی راهی بساز.» ✨",
    "«بزرگ‌ترین شجاعت این است که در دنیایی پر از تکرار، خودت باشی و مسیرت را بسازی.» 💫",
    "«هیچ تاریکی آن‌قدر ماندگار نیست که بتواند از طلوع خورشید جلوگیری کند.» ☀️",
    "«زندگی یا یک ماجراجویی جسورانه است، یا هیچ چیز دیگری نیست.» — هلن کلر 🚀",
    "«پرواز بال نمی‌خواهد؛ رهایی از حصار باورهای محدود کافی است.» 🕊",
    "«گاه برای آغاز دوباره، تنها نیاز است تمام درهای دیروز را شجاعانه ببندی.» 🔑",
    "«نور از میان زخم‌ها وارد روح آدمی می‌شود؛ سختی‌ها زادگاه روشنایی‌اند.» — مولانا 🕯",
    "«صبر تلخ است، ولیکن بَرِ شیرین دارد؛ پایدار باش بر اهدافی که به آن‌ها باور داری.» 💎",
    "«آنچه در جستجوی آنی، خود در جستجوی توست.» — شمس تبریزی 🌌",
    "«قدرت واقعی در آرامش نهفته است؛ طوفان‌ها همیشه زودگذرند.» 🌊",
    "«برای دیدن افق‌های تازه، گاه باید شهامت دور شدن از ساحل‌های امن را داشت.» ⛵️",
    "«محدودیت‌ها تنها در ذهن ما نفس می‌کشند؛ از مرز اندیشه‌ات فراتر برو.» 🧠⚡️",
    "«جهان آینه‌ای است که بازتاب باورهای تو را به نمایش می‌گذارد؛ زیبا بیندیش.» 🪞",
    "«ارزش انسان به اندازه آرزوهای بلند و اراده بی‌پایان اوست.» 🏔",
    "«رویاهایت را در سکوت بساز؛ بگذار موفقیتت بلندترین صدا باشد.» 🎯",
    "«ریشه‌های قوی از طوفان‌های سهمگین هراسی ندارند؛ عمیق شو و ماندگار بمان.» 🌳",
    "«ارتباط بی‌پایان، جریان بی‌پایان زندگی در رگ‌های زمان است؛ آزاد و متصل بمانید.» 🌐"
]

# ==================== پرامپت‌های چندگانه و هنری هوش مصنوعی ====================
# هر پرامپت سبک متفاوتی را خلق می‌کند تا عکس‌ها فوق‌العاده متنوع و جذاب باشند
ARTISTIC_PROMPTS = [
    # ۱. سبک کیهانی و شفق قطبی ماورایی
    "surreal cosmic aurora borealis over mystical glowing mountains, starry galaxy sky, nebula reflections, ethereal lighting, highly detailed 8k wallpaper, award winning nature photography",
    
    # ۲. نئون سایبرپانک بارانی و آینده‌نگرانه
    "aesthetic cyberpunk city at night with neon reflections on wet street, glowing lanterns, futuristic flying drones, deep cinematic mood, blade runner style, octane render 8k",
    
    # ۳. انتزاعی کریستالی و مایع سه‌بعدی
    "hyper-realistic 3D abstract floating iridescent glass crystals, flowing liquid gold ribbons, smooth gradient backdrop, luxury aesthetic, clean octane render, 8k resolution, minimalist masterpiece",
    
    # ۴. منظره جادویی و رویایی جنگل بیولومینسنت
    "enchanted bioluminescent fantasy forest, glowing ethereal trees and flowers, misty magical atmosphere, fairytale landscape, cinematic depth of field, ghibli aesthetics hyper-detailed",
    
    # ۵. تکنولوژی شبکه نورانی و مینیمال
    "sleek futuristic abstract technology lines, glowing turquoise and golden fiber optics, subtle dark background, elegant composition, wallpaper worthy, clean high-tech concept art 8k",
    
    # ۶. معماری مینیمال کویری زیر آسمان پرستاره
    "minimalist modern glass architecture under vast starry milky way, warm interior glow, architectural photography, hyper-detailed, peaceful and majestic"
]

PROXY_REGEX = re.compile(
    r'(?:https?:\/\/t\.me\/(?:proxy\?|socks\?)|tg:\/\/(?:proxy\?|socks\?))[^\s"\'<>]+',
    re.IGNORECASE
)

# ==================== توابع کمکی ====================
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

def get_unique_artistic_image() -> str:
    """انتخاب تصادفی یک سبک هنری خیره‌کننده و تولید با هوش مصنوعی با Seed اختصاصی"""
    unique_seed = random.randint(1000000, 99999999) + int(time.time() % 10000)
    selected_theme = random.choice(ARTISTIC_PROMPTS)
    
    encoded_prompt = urllib.parse.quote(selected_theme)
    # کیفیت 1280x720 بدون لوگو و واترمارک
    ai_image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1280&height=720&seed={unique_seed}&nologo=true"

    # ثبت سابقه در دیتابیس sent_images.json
    history_file = "sent_images.json"
    sent_records = []
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                sent_records = json.load(f)
        except Exception:
            sent_records = []

    sent_records.append({"time": get_tehran_time(), "seed": unique_seed, "prompt": selected_theme[:40]})
    sent_records = sent_records[-150:]  # نگه‌داری ۱۵۰ رکورد اخیر

    try:
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(sent_records, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[!] خطا در ذخیره سابقه عکس: {e}")

    return ai_image_url

def collect_proxies():
    """استخراج پروکسی‌ها از وب عمومی تلگرام"""
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
    """ارسال فایل با ۳ دکمه شیشه‌ای"""
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
    """ارسال عکس جذاب با ۱۷ هایپرلینک و ۳ دکمه شیشه‌ای"""
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

# ==================== اجرای برنامه ====================
def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("[X] مقادیر BOT_TOKEN یا CHAT_ID خالی است!")
        return

    print("[*] در حال جمع‌آوری پروکسی‌ها...")
    proxies = collect_proxies()
    total = len(proxies)
    print(f"[✓] تعداد پروکسی‌های یکتا: {total}")

    if total == 0:
        print("[!] پروکسی جدیدی یافت نشد.")
        return

    time_str = get_tehran_time()
    filename = "Proxies_Daily.txt"

    # ذخیره فایل کامل پروکسی‌ها
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# Telegram MTProto & SOCKS5 Proxies\n# Time: {time_str}\n# Count: {total}\n\n")
        f.write("\n".join(proxies))

    # ۱. پیام اول (فایل کامل با کپشن شکیل)
    file_caption = (
        f"📁 <b>بسته جامع پروکسی‌های ضدفیلتر تلگرام</b>\n\n"
        f"📊 <b>تعداد کل پروکسی‌های یکتا:</b> <code>{total}</code> عدد\n"
        f"⏰ <b>زمان به‌روزرسانی:</b> <code>{time_str}</code>\n"
        f"🛡 <b>پروتکل‌ها:</b> MTProto & SOCKS5\n\n"
        f"📌 <b>راهنما:</b>\n"
        f"▫️ هنگام اتصال به پروکسی، وی‌پی‌ان خود را خاموش کنید.\n"
        f"▫️ فایل را دانلود و درون تلگرام اجرا نمایید."
    )
    print("[*] در حال ارسال فایل به کانال...")
    res_file = send_file_to_channel(filename, file_caption)
    print("نتیجه ارسال فایل:", res_file.get("ok"))

    # ۲. پیام دوم (عکس اختصاصی + ۱۷ پروکسی با چیدمان دقیق تصویر شما)
    top_17 = proxies[:17]
    while len(top_17) < 17 and len(proxies) > 0:
        top_17.append(proxies[len(top_17) % len(proxies)])

    # چیدمان: خط اول ۲ تایی، ۵ خط بعدی ۳ تایی (مجموعاً ۱۷ عدد)
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
        f"💎 <b>منتخب ۱۷ پروکسی پرسرعت و پایدار</b>\n"
        f"⏰ <code>{time_str}</code>\n\n"
        f"{selected_quote}\n\n"
        f"👇 <b>جهت اتصال، لمس کنید:</b>\n\n"
        f"{layout_block}\n\n"
        f"🌐 <i>اتصال آزاد، پایدار و با بالاترین امنیت</i>"
    )

    print("[*] در حال ارسال تصویر هنری و هایپرلینک‌ها...")
    res_photo = send_photo_to_channel(ai_photo, photo_caption)
    print("نتیجه ارسال تصویر:", res_photo.get("ok"))

    if os.path.exists(filename):
        os.remove(filename)

if __name__ == "__main__":
    main()
