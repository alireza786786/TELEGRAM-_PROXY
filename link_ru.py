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

# --- دریافت متغیرهای محرمانه ---
BOT_TOKEN = os.getenv("BOT_TOKEN2")
CHAT_ID = os.getenv("CHAT_ID")
SOURCE_1 = os.getenv("SOURCE_1", "")

GEO_CACHE = {}

def get_country_flag(country_code):
    """تبدیل کد کشور دو حرفی به ایموجی پرچم"""
    if not country_code or len(country_code) != 2:
        return "🌐"
    return "".join(chr(127397 + ord(c.upper())) for c in country_code)

def resolve_and_ping(host, port, timeout=1.8):
    """بررسی اتصال، پینگ واقعی TCP و مشخص کردن نسخه IP"""
    try:
        start_time = datetime.now()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, int(port)))
        sock.close()
        latency = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # تشخیص نسخه آی‌پی
        ip = socket.gethostbyname(host)
        ip_ver = "IPv6" if ":" in ip else "IPv4"
        return latency, ip, ip_ver
    except Exception:
        return None, None, None

def get_geo_info(ip):
    """دریافت موقعیت مکانی و دیتاسنتر از روی IP"""
    if not ip:
        return "🌐", "Unknown", "Server"
    if ip in GEO_CACHE:
        return GEO_CACHE[ip]
    try:
        res = requests.get(f"http://ip-api.com/json/{ip}?fields=status,country,countryCode,city,org", timeout=3).json()
        if res.get("status") == "success":
            flag = get_country_flag(res.get("countryCode", ""))
            country = res.get("country", "Global")
            city = res.get("city") or res.get("org", "Cloud")
            # کوتاه کردن نام شهر یا شرکت
            city = city.split()[0] if city else "DC"
            GEO_CACHE[ip] = (flag, country, city)
            return GEO_CACHE[ip]
    except Exception:
        pass
    return "🌐", "Global", "DC"

def extract_configs_from_sources(sources_text):
    """دریافت محتوا از سورس‌ها بدون متوقف شدن در صورت خرابی یک لینک"""
    links = [line.strip() for line in re.split(r'[\r\n,]+', sources_text) if line.strip()]
    raw_configs = []
    
    for url in links:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                text = resp.text.strip()
                # بررسی امکان بیس۶۴ بودن محتوای ساب‌اسکریپشن
                try:
                    decoded = base64.b64decode(text).decode('utf-8', errors='ignore')
                    if any(p in decoded for p in ["vmess://", "vless://", "ss://", "trojan://"]):
                        text = decoded
                except Exception:
                    pass
                
                # استخراج خطوط کانفیگ
                found = re.findall(r'((?:vmess|vless|trojan|ss|ssr|hysteria|hy2|tuic)://[^\s]+)', text)
                raw_configs.extend(found)
        except Exception as e:
            print(f"[!] Warning: Error fetching {url} -> {e}")
            continue
            
    # حذف تکراری‌ها
    return list(dict.fromkeys(raw_configs))

def parse_and_rebuild_config(config_str):
    """آنالیز کانفیگ، تست پینگ و بازنویسی نام بر اساس الگوی پنج‌خطی"""
    try:
        proto = config_str.split("://")[0].lower()
        host, port = None, None
        feature = "Reality" if "reality" in config_str.lower() else ("WS" if "ws" in config_str.lower() else "TLS/TCP")

        if proto == "vmess":
            b64_data = config_str.replace("vmess://", "")
            # رفع مشکل padding در بیس۶۴
            b64_data += '=' * (-len(b64_data) % 4)
            data = json.loads(base64.b64decode(b64_data).decode('utf-8', errors='ignore'))
            host = data.get("add")
            port = data.get("port")
            
            ping, ip, ip_ver = resolve_and_ping(host, port)
            if not ping or ping >= 500: # شرط VIP Strict < 500ms
                return None
                
            flag, country, city = get_geo_info(ip)
            
            # الگوی اختصاصی کاربر
            remark = (
                f"👉🆔@Goodbaye_filtering 📡{flag} {country} ®️{city}\n"
                f"🅿️ping:{ping}ms ⚡{feature} | {proto.upper()} {ip_ver}"
            )
            data["ps"] = remark
            new_b64 = base64.b64encode(json.dumps(data).encode('utf-8')).decode('utf-8')
            return f"vmess://{new_b64}"

        else:
            # بقیه پروتکل‌ها (Vless, Trojan, Shadowsocks, Tuic, Hy2)
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
            
            # حذف رمارک قبلی و جایگزینی با جدید
            base_url = config_str.split("#")[0]
            return f"{base_url}#{encoded_remark}"
            
    except Exception:
        return None

def send_telegram_file(file_path, healthy_count):
    """ارسال فایل به تلگرام با کپشن و دکمه‌های شیشه‌ای درخواستی"""
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
            print("[+] Successfully sent to Telegram!")
        else:
            print(f"[-] Telegram Send Failed: {r.text}")

def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("[!] BOT_TOKEN2 or CHAT_ID is missing!")
        return

    print("[*] Fetching configs from SOURCE_1...")
    raw_configs = extract_configs_from_sources(SOURCE_1)
    print(f"[*] Found {len(raw_configs)} unique configs. Testing latency & ping...")

    healthy_configs = []
    # تست موازی چندنخی کانفیگ‌ها برای افزایش حداکثری سرعت
    with ThreadPoolExecutor(max_workers=30) as executor:
        results = executor.map(parse_and_rebuild_config, raw_configs)
        for res in results:
            if res:
                healthy_configs.append(res)

    print(f"[*] {len(healthy_configs)} healthy strict configs verified.")

    if not healthy_configs:
        print("[!] No healthy configs found under 500ms.")
        return

    output_filename = "Goodbaye_filtering_VIP.txt"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write("\n".join(healthy_configs))

    send_telegram_file(output_filename, len(healthy_configs))

if __name__ == "__main__":
    main()
