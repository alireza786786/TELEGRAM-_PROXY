import base64
import binascii
import json
import os
import re
import socket
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import jdatetime
import pytz
import requests


BOT_TOKEN = os.getenv("BOT_TOKEN2", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()
SOURCE_1 = os.getenv("SOURCE_1", "").strip()

GEO_CACHE = {}

SUPPORTED_PROTOCOLS = (
    "vmess://",
    "vless://",
    "trojan://",
    "ss://",
    "ssr://",
    "hysteria://",
    "hysteria2://",
    "hy2://",
    "tuic://",
    "shadowsocks://",
)


def decode_base64(value):
    """Decode standard or URL-safe Base64 with optional missing padding."""
    value = re.sub(r"\s+", "", value or "")

    if not value:
        raise ValueError("Base64 value is empty")

    value += "=" * (-len(value) % 4)
    decoded = base64.urlsafe_b64decode(value.encode("ascii"))
    return decoded


def get_country_flag(country_code):
    if (
        not country_code
        or len(country_code) != 2
        or not country_code.isalpha()
    ):
        return "🌐"

    return "".join(
        chr(127397 + ord(char.upper()))
        for char in country_code
    )


def resolve_and_ping(host, port, timeout=1.8):
    """Try TCP connections over available IPv4 and IPv6 addresses."""
    if not host or port is None:
        return None, None, None

    try:
        port = int(port)

        if not 1 <= port <= 65535:
            return None, None, None

        addresses = socket.getaddrinfo(
            host,
            port,
            type=socket.SOCK_STREAM,
        )
    except (OSError, TypeError, ValueError):
        return None, None, None

    for family, socktype, proto, _, sockaddr in addresses:
        sock = socket.socket(family, socktype, proto)
        sock.settimeout(timeout)
        start_time = time.monotonic()

        try:
            sock.connect(sockaddr)
            latency = int((time.monotonic() - start_time) * 1000)
            ip = sockaddr[0]
            ip_version = "IPv6" if family == socket.AF_INET6 else "IPv4"
            return latency, ip, ip_version
        except OSError:
            continue
        finally:
            sock.close()

    return None, None, None


def get_geo_info(ip):
    if not ip:
        return "🌐", "Unknown", "Unknown"

    if ip in GEO_CACHE:
        return GEO_CACHE[ip]

    try:
        encoded_ip = urllib.parse.quote(ip, safe="")
        response = requests.get(
            "http://ip-api.com/json/"
            f"{encoded_ip}?fields=status,country,countryCode,city,org",
            timeout=4,
        )
        response.raise_for_status()
        result = response.json()

        if result.get("status") == "success":
            flag = get_country_flag(result.get("countryCode"))
            country = result.get("country") or "Unknown"
            city = result.get("city") or result.get("org") or "Unknown"
            info = (flag, country, city.split()[0])

            GEO_CACHE[ip] = info
            return info

    except (requests.RequestException, ValueError, TypeError):
        pass

    return "🌐", "Unknown", "Unknown"


def extract_configs_from_sources(sources_text):
    """Fetch supported links from the URLs supplied in SOURCE_1."""
    source_urls = [
        line.strip()
        for line in re.split(r"[\r\n,]+", sources_text or "")
        if line.strip()
    ]

    print(
        f"\n{'=' * 50}\n"
        f"📡 تعداد سورس‌های شناسایی‌شده: {len(source_urls)} عدد\n"
        f"{'=' * 50}",
        flush=True,
    )

    all_configs = []

    for index, url in enumerate(source_urls, start=1):
        domain = urllib.parse.urlsplit(url).netloc or f"Source-{index}"
        print(
            f"[{index}/{len(source_urls)}] ⏳ دریافت از: {domain}",
            flush=True,
        )

        headers = {
            "User-Agent": "v2rayNG/1.8.12",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        }

        separator = "&" if "?" in url else "?"
        fetch_url = f"{url}{separator}_t={int(time.time())}"

        try:
            response = requests.get(
                fetch_url,
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()
            text = response.text.strip()

            # Subscription responses are often Base64 encoded.
            try:
                decoded_text = decode_base64(text).decode(
                    "utf-8",
                    errors="ignore",
                )

                if any(
                    protocol in decoded_text.lower()
                    for protocol in SUPPORTED_PROTOCOLS
                ):
                    text = decoded_text

            except (
                ValueError,
                UnicodeError,
                binascii.Error,
            ):
                pass

            found = [
                line.strip()
                for line in text.splitlines()
                if line.strip().lower().startswith(SUPPORTED_PROTOCOLS)
            ]

            print(
                f"    ✅ تعداد کانفیگ این سورس: {len(found)}",
                flush=True,
            )
            all_configs.extend(found)

        except requests.RequestException as error:
            print(
                f"    ❌ دریافت سورس {index} ناموفق بود: {error}",
                flush=True,
            )

    # Remove duplicate links while preserving their original order.
    all_configs = list(dict.fromkeys(all_configs))

    print(
        f"{'=' * 50}\n"
        f"📊 مجموع کانفیگ‌های استخراج‌شده: {len(all_configs)}\n"
        f"{'=' * 50}\n",
        flush=True,
    )

    return all_configs


def get_vmess_data(config):
    payload = config[len("vmess://"):].split("#", 1)[0]
    decoded = decode_base64(payload).decode("utf-8")
    return json.loads(decoded)


def get_endpoint(config, protocol):
    """Extract host and port from common proxy-link formats."""
    parsed = urllib.parse.urlsplit(config)

    try:
        if parsed.hostname and parsed.port:
            return parsed.hostname, parsed.port
    except ValueError:
        return None, None

    if protocol in ("ss", "shadowsocks"):
        body = config.split("://", 1)[1].split("#", 1)[0]

        # Legacy Shadowsocks links may encode the whole endpoint.
        if "@" not in body:
            try:
                decoded = decode_base64(body).decode("utf-8")
                parsed = urllib.parse.urlsplit("//" + decoded)

                if parsed.hostname and parsed.port:
                    return parsed.hostname, parsed.port
            except (
                ValueError,
                UnicodeError,
                binascii.Error,
            ):
                pass

    if protocol == "ssr":
        body = config.split("://", 1)[1].split("#", 1)[0]

        try:
            decoded = decode_base64(body).decode("utf-8")
            fields = decoded.split(":", 5)

            if len(fields) >= 6:
                host = fields[0]
                port = int(fields[1])

                if host.startswith("[") and host.endswith("]"):
                    host = host[1:-1]

                return host, port

        except (
            ValueError,
            UnicodeError,
            binascii.Error,
        ):
            pass

    return None, None


def parse_and_rebuild_config(config):
    try:
        protocol = config.split("://", 1)[0].lower()
        supported_names = {
            item[:-3]
            for item in SUPPORTED_PROTOCOLS
        }

        if protocol not in supported_names:
            return None

        vmess_data = None

        if protocol == "vmess":
            vmess_data = get_vmess_data(config)
            host = vmess_data.get("add")
            port = vmess_data.get("port")
        else:
            host, port = get_endpoint(config, protocol)

        ping, ip, ip_version = resolve_and_ping(host, port)

        if ping is None or ping >= 500:
            return None

        flag, country, city = get_geo_info(ip)
        lowered_config = config.lower()

        if "reality" in lowered_config:
            feature = "Reality"
        elif "ws" in lowered_config:
            feature = "WS"
        else:
            feature = "TLS/TCP"

        remark = (
            f"👉🆔@Goodbaye_filtering "
            f"📡{flag} {country} ®️{city}\n"
            f"🅿️ping:{ping}ms ⚡{feature} | "
            f"{protocol.upper()} {ip_version}"
        )

        if protocol == "vmess":
            vmess_data["ps"] = remark
            encoded = base64.b64encode(
                json.dumps(
                    vmess_data,
                    ensure_ascii=False,
                ).encode("utf-8")
            ).decode("ascii")

            return f"vmess://{encoded}"

        parsed = urllib.parse.urlsplit(config)
        encoded_remark = urllib.parse.quote(remark, safe="")

        return urllib.parse.urlunsplit(
            parsed._replace(fragment=encoded_remark)
        )

    except (
        ValueError,
        TypeError,
        KeyError,
        json.JSONDecodeError,
        binascii.Error,
    ):
        return None


def send_telegram_file(file_path, healthy_count):
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError(
            "لطفاً Secretsهای BOT_TOKEN2 و CHAT_ID را در GitHub تنظیم کنید."
        )

    tehran_now = datetime.now(pytz.timezone("Asia/Tehran"))
    jalali_date = jdatetime.datetime.fromgregorian(
        datetime=tehran_now
    ).strftime("%Y/%m/%d")

    caption = (
        "🚀 مجموعه کانفیگ‌های تست‌شده و زنده (Goodbaye VIP) 📡\n\n"
        f"📅 تاریخ شمسی: {jalali_date} "
        f"⏰ ساعت تهران: {tehran_now:%H:%M:%S}\n"
        "📊 شاخص کیفیت: VIP Strict (Ping < 500ms)\n"
        f"🔢 تعداد کانفیگ سالم: {healthy_count}"
    )

    reply_markup = {
        "inline_keyboard": [
            [
                {
                    "text": "📢 کانال اصلی Goodbaye_filtering",
                    "url": "https://t.me/Goodbaye_filtering",
                }
            ],
            [
                {
                    "text": "⚡ کانال اختصاصی VIP",
                    "url": "https://t.me/CONFIG_V2RAY_VIP",
                }
            ],
            [
                {
                    "text": "🔒 کانال خصوصی",
                    "url": "https://t.me/+m4GhEHGLd2k5ZjU0",
                }
            ],
            [
                {
                    "text": "🔄 اشتراک‌گذاری با دوستان",
                    "url": (
                        "https://t.me/share/url"
                        "?url=https://t.me/Goodbaye_filtering"
                    ),
                }
            ],
        ]
    }

    telegram_url = (
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    )

    try:
        with open(file_path, "rb") as document:
            response = requests.post(
                telegram_url,
                data={
                    "chat_id": CHAT_ID,
                    "caption": caption,
                    "reply_markup": json.dumps(reply_markup),
                },
                files={
                    "document": (
                        os.path.basename(file_path),
                        document,
                        "text/plain",
                    )
                },
                timeout=30,
            )

        response.raise_for_status()
        result = response.json()

        if not result.get("ok"):
            raise RuntimeError(
                f"Telegram API خطا برگرداند: {result}"
            )

        print("✅ فایل با موفقیت به تلگرام ارسال شد.", flush=True)

    except (requests.RequestException, ValueError) as error:
        raise RuntimeError(
            f"ارسال فایل به تلگرام ناموفق بود: {error}"
        ) from error


def main():
    if not SOURCE_1:
        raise RuntimeError(
            "متغیر SOURCE_1 خالی است؛ آن را در GitHub Secrets تنظیم کنید."
        )

    configs = extract_configs_from_sources(SOURCE_1)

    if not configs:
        print(
            "[!] هیچ کانفیگی از سورس‌ها دریافت نشد.",
            flush=True,
        )
        return

    print(
        f"🔍 شروع بررسی {len(configs)} کانفیگ...",
        flush=True,
    )

    with ThreadPoolExecutor(max_workers=50) as executor:
        results = executor.map(parse_and_rebuild_config, configs)

    healthy_configs = [
        result
        for result in results
        if result
    ]

    # Keep output deterministic and remove any duplicate rebuilt links.
    healthy_configs = list(dict.fromkeys(healthy_configs))

    print(
        f"🎯 تعداد نهایی کانفیگ‌های زنده و سالم: "
        f"{len(healthy_configs)} عدد",
        flush=True,
    )

    if not healthy_configs:
print("[!] هیچ کانفیگی شرط پینگ زیر ۵۰۰ میلی‌ثانیه را پاس نکرد.", flush=True)
return

output_filename = "Goodbaye_filtering_VIP.txt"
with open(output_filename, "w", encoding="utf-8") as f:
f.write("\n".join(healthy_configs))

send_telegram_file(output_filename, len(healthy_configs))

if name == "main":
main()
