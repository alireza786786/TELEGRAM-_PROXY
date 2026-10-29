import os
import re
import json
import socket
import base64
import urllib.parse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import requests
import pytz
import jdatetime

# دریافت متغیرهای محرمانه از گیت‌هاب
BOT_TOKEN = os.getenv("BOT_TOKEN2")
CHAT_ID = os.getenv("CHAT_ID")
SOURCE_1 = os.getenv("SOURCE_1", "")

GEO_CACHE = {}

def get_country_flag(country_code):
    """تبدیل کد دو حرفی کشور به ایموجی پرچم"""
    if not country_code or len(country_code) != 2:
        return "🌐"
    return "".join(chr(127397 + ord(c.upper())) for c in country_code)

def resolve_and_ping(host, port, timeout=1.8):
    """تست پینگ اتصال TCP واقعی، بررسی دسترسی و نسخه IP"""
    try:
        start_time = datetime.now()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, int(port)))
        sock.close()
        latency = int((datetime.now() - start_time).total_seconds() * 1000)
        
        ip = socket.gethostbyname(host)
        ip_ver = "IPv6" if ":" in ip else "IPv4"
        return latency, ip, ip_ver
    except Exception:
        return None, None, None

def get_geo_info(ip):
    """دریافت اطلاعات جغرافیایی، کشور و نام دیتاسنتر با کش داخلی"""
    if not ip:
        return "🇷🇺", "Russia", "DC"
    if ip in GEO_CACHE:
        return GEO_CACHE[ip]
    try:
        url = f"http://ip-api.com/json/{ip}?fields=status,country,countryCode,city,org"
        res = requests.get(url, timeout=3).json()
        if res.get("status") == "success":
            flag = get_country_flag(res.get("countryCode", "RU"))
            country = res.get("country", "Russia")
            city = res.get("city") or res.get("org", "Cloud")
            city = city.split()[0] if city else "DC"
            GEO_CACHE[ip] = (flag, country, city)
            return GEO_CACHE[ip]
    except Exception:
        pass
    return "🇷🇺", "Russia", "DC"

def extract_configs_from_sources(sources_text):
    """استخراج تمام کانفیگ‌ها از ۳ لینک با گزارش‌دهی دقیق در کنسول"""
    links = [line.strip() for line in re.split(r'[\r\n,]+', sources_text) if line.strip()]
    total_links = len(links)
    
    print("\n" + "="*50, flush=True)
    print(f"📡 تعداد کل لینک‌های شناسایی‌شده در SOURCE_1: {total_links} عدد", flush=True)
    print("="*50, flush=True)
    
    if total_links == 0:
        print("[❌] هیچ لینکی در SOURCE_1 یافت نشد!", flush=True)
        return []

    raw_configs = []
    
    for idx, url in enumerate(links, 1):
        domain = urllib.parse.urlsplit(url).netloc or f"Source-{idx}"
        print(f"[{idx}/{total_links}] ⏳ در حال بررسی سورس: {domain} ...", flush=True)
        
        try:
            headers = {'User-Agent': 'v2rayNG/1.8.12'}
            resp = requests.get(url, headers=headers, timeout=12)
            
            if resp.status_code == 200:
                text = resp.text.strip()
                # بررسی ساب‌اسکریپشن بیس۶۴
                try:
                    padding = '=' * (-len(text) % 4)
                    decoded = base64.b64decode(text + padding).decode('utf-8', errors='ignore')
                    if any(p in decoded for p in ["vmess://", "vless://", "ss://", "trojan://"]):
                        text = decoded
                except Exception:
                    pass
                
                found = re.findall(r'((?:vmess|vless|trojan|ss|ssr|hysteria|hy2|tuic)://[^\s]+)', text)
                print(f"    ✅ دریافت موفق (HTTP 200) ⬅️ تعداد کانفیگ دریافت‌شده: {len(found)} عدد", flush=True)
                raw_configs.extend(found)
            else:
                print(f"    ⚠️ خطا در ارتباط با سرور سورس (کد وضعیت: {resp.status_code})", flush=True)
        except Exception as e:
            print(f"    ❌ سورس شماره {idx} با خطا مواجه شد و رد گردید: {e}", flush=True)
            continue

    # حذف کانفیگ‌های تکراری
    unique_configs = list(dict.fromkeys(raw_configs))
    print("="*50, flush=True)
    print(f"📊 مجموع کانفیگ‌های خام: {len(raw_configs)} عدد", flush=True)
    print(f"✨ مجموع کانفیگ‌های یکتا (پس از حذف تکراری): {len(unique_configs)} عدد", flush=True)
    print("="*50 + "\n", flush=True)
    return unique_configs

def parse_and_rebuild_config(config_str):
    """بررسی زنده بودن، سنجش پینگ کمتر از ۵۰۰ و بازنویسی با الگوی اختصاصی"""
    try:
        proto = config_str.split("://")[0].lower()
        feature = "Reality" if "reality" in config_str.lower() else ("WS" if "ws" in config_str.lower() else "TLS/TCP")

        if proto == "vmess":
            b64_data = config_str.replace("vmess://", "")
            b64_data += '=' * (-len(b64_data) % 4)
            data = json.loads(base64.b64decode(b64_data).decode('utf-8', errors='ignore'))
            host = data.get("add")
            port = data.get("port")
            
            ping, ip, ip_ver = resolve_and_ping(host, port)
            if not ping or ping >= 500:  # فیلتر سخت‌گیرانه Strict VIP
                return None
                
            flag, country, city = get_geo_info(ip)
            
            # الگوی اختصاصی شما
            remark = (
                f"👉🆔@Goodbaye_filtering 📡{flag} {country} ®️{city}\n"
                f"🅿️ping:{ping}ms ⚡{feature} | {proto.upper()} {ip_ver}"
            )
            data["ps"] = remark
            new_b64 = base64.b64encode(json.dumps(data, ensure_ascii=False).encode('utf-8')).decode('utf-8')
            return f"vmess://{new_b64}"

        else:
            parsed = urllib.parse.urlsplit(config_str)
            host = parsed.hostname
            port = parsed.port
            
            if not host or not port:
                return None
                
            ping, ip, ip_ver = resolve_and_ping(host, port)
            if not ping or ping >= 500:
                return None
                
            flag, country, city = get_geo_info(ip)
            
            remark = (
                f"👉🆔@Goodbaye_filtering 📡{flag} {country} ®️{city}\n"
                f"🅿️ping:{ping}ms ⚡{feature} | {proto.upper()} {ip_ver}"
            )
            encoded_remark = urllib.parse.quote(remark)
            base_url = config_str.split("#")[0]
            return f"{base_url}#{encoded_remark}"
            
    except Exception:
        return None

def send_telegram_file(file_path, healthy_count):
    """ارسال فایل همراه با کپشن رسمی و ۴ دکمه شیشه‌ای به کانال"""
    tz = pytz.timezone("Asia/Tehran")
    now_tehran = datetime.now(tz)
    jalali_date = jdatetime.datetime.fromgregorian(datetime=now_tehran).strftime("%Y/%m/%d")
    tehran_time = now_tehran.strftime("%H:%M:%S")

    caption = (
        "🚀 مجموعه کانفیگ‌های تست‌شده و زنده (Goodbaye VIP) 📡 مناسب دوران اختلال، فیلترینگ و شبکه ملی\n\n"
        f"📅 تاریخ شمسی: {jalali_date} ⏰ ساعت تهران: {tehran_time} 📊 شاخص کیفیت: VIP Strict (Ping < 500ms) "
        f"🔢 تعداد کانفیگ سالم این فایل: {healthy_count}"
    )

    reply_markup = {
        "inline_keyboard": [
            [{"text": "📢 کانال اصلی Goodbaye_filtering", "url": "https://t.me/Goodbaye_filtering"}],
            [{"text": "⚡ کانال اختصاصی VIP", "url": "https://t.me/CONFIG_V2RAY_VIP"}],
            [{"text": "🔒 کانال خصوصی", "url": "https://t.me/+m4GhEHGLd2k5ZjU0"}],
            [{"text": "🔄 اشتراک‌گذاری با دوستان", "url": "https://t.me/share/url?url=https://t.me/Goodbaye_filtering"}]
        ]
    }

    tg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    with open(file_path, "rb") as f:
        payload = {
            "chat_id": CHAT_ID,
            "caption": caption,
            "reply_markup": json.dumps(reply_markup)
        }
        files = {"document": f}
        r = requests.post(tg_url, data=payload, files=files, timeout=30)
        if r.status_code == 200:
            print("🚀 [موفقیت] فایل نهایی با ۴ دکمه به کانال تلگرام ارسال شد!", flush=True)
        else:
            print(f"❌ خطا در ارسال تلگرام: {r.text}", flush=True)

def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("[!] خطای متغیرها: BOT_TOKEN2 یا CHAT_ID ست نشده است.", flush=True)
        return

    raw_configs = extract_configs_from_sources(SOURCE_1)
    if not raw_configs:
        print("[!] هیچ کانفیگی استخراج نشد.", flush=True)
        return

    print("⚡ در حال تست اتصال زنده و غربالگری پینگ (Ping < 500ms)...", flush=True)
    healthy_configs = []
    
    with ThreadPoolExecutor(max_workers=35) as executor:
        results = executor.map(parse_and_rebuild_config, raw_configs)
        for res in results:
            if res:
                healthy_configs.append(res)

    print(f"🎯 تعداد نهایی کانفیگ‌های زنده و پرسرعت: {len(healthy_configs)} عدد", flush=True)

    if not healthy_configs:
        print("[!] هیچ کانفیگی شرط پینگ زیر ۵۰۰ میلی‌ثانیه را پاس نکرد.", flush=True)
        return

    output_filename = "Goodbaye_filtering_VIP.txt"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write("\n".join(healthy_configs))

    send_telegram_file(output_filename, len(healthy_configs))

if __name__ == "__main__":
    main()
