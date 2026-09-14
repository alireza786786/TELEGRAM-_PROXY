#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 Script برای تست محلی پروکسی‌های تلگرام
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass
import logging

# تنظیم logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ProxyLink:
    """کلاس برای نمایندگی پروکسی"""
    server: str
    port: int
    secret: str
    raw: str
    latency: float = 999.0


async def test_proxy_speed(proxy: ProxyLink, timeout: float = 5.0) -> Optional[float]:
    """تست سرعت اتصال TCP به پروکسی"""
    try:
        start_time = asyncio.get_event_loop().time()
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(proxy.server, proxy.port),
            timeout=timeout
        )
        end_time = asyncio.get_event_loop().time()
        latency = round((end_time - start_time) * 1000, 2)
        writer.close()
        await writer.wait_closed()
        return latency
    except asyncio.TimeoutError:
        logger.warning(f"⏱ Timeout برای {proxy.server}:{proxy.port}")
        return None
    except Exception as e:
        logger.warning(f"❌ خطا برای {proxy.server}:{proxy.port}: {e}")
        return None


async def test_proxies_from_file(file_path: str, max_tests: int = 10) -> None:
    """تست پروکسی‌های موجود در فایل"""
    
    if not Path(file_path).exists():
        logger.error(f"❌ فایل {file_path} وجود ندارد")
        logger.info("🔍 ابتدا proxy_collector.py را اجرا کنید یا فایل را ایجاد کنید")
        return
    
    logger.info(f"📂 فایل {file_path} بررسی می‌شود...\n")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        logger.error(f"❌ خطا در خواندن فایل: {e}")
        return
    
    if not lines:
        logger.error(f"❌ فایل خالی است")
        return
    
    logger.info(f"📊 تعداد کل پروکسی‌های موجود: {len(lines)}")
    
    # تست تعداد محدودی از پروکسی‌ها
    test_count = min(max_tests, len(lines))
    logger.info(f"🧪 درحال تست {test_count} پروکسی اول...\n")
    
    results = []
    
    for i, line in enumerate(lines[:test_count]):
        line = line.strip()
        if not line:
            continue
        
        try:
            # تجزیه URL پروکسی
            if "server=" not in line or "port=" not in line:
                logger.warning(f"⚠️  {i+1}. فرمت نامعتبر: {line[:50]}")
                continue
            
            # استخراج server و port
            import re
            server_match = re.search(r'server=([^&]+)', line)
            port_match = re.search(r'port=(\d+)', line)
            
            if not server_match or not port_match:
                logger.warning(f"⚠️  {i+1}. نتوانست اطلاعات پروکسی را استخراج کند")
                continue
            
            server = server_match.group(1)
            port = int(port_match.group(1))
            
            proxy = ProxyLink(
                server=server,
                port=port,
                secret="",
                raw=line
            )
            
            logger.info(f"⏳ {i+1}. تست {server}:{port}...", end=" ")
            latency = await test_proxy_speed(proxy)
            
            if latency is not None:
                logger.info(f"✅ Latency: {latency}ms")
                results.append((proxy, latency))
            else:
                logger.info(f"❌ بدون پاسخ")
        
        except Exception as e:
            logger.error(f"❌ خطا در تست: {e}")
            continue
    
    # نمایش نتایج
    logger.info("\n" + "=" * 60)
    logger.info("📊 نتایج تست:")
    logger.info("=" * 60)
    
    if not results:
        logger.warning("⚠️  هیچ پروکسی سالمی پیدا نشد")
        logger.info("\n💡 توصیه‌ها:")
        logger.info("1. تنظیمات فایروال خود را بررسی کنید")
        logger.info("2. اطمینان حاصل کنید که اتصال به اینترنت برقرار است")
        logger.info("3. منابع پروکسی ممکن است بروز نباشند")
        return
    
    results.sort(key=lambda x: x[1])
    
    logger.info(f"\n✅ {len(results)} پروکسی سالم پیدا شدند:\n")
    
    for i, (proxy, latency) in enumerate(results, 1):
        logger.info(f"{i}. 📍 {proxy.server}:{proxy.port}")
        logger.info(f"   ⏱ Latency: {latency}ms")
        logger.info(f"   🔗 {proxy.raw[:60]}...")
    
    # محاسبه آمار
    latencies = [lat for _, lat in results]
    avg_latency = sum(latencies) / len(latencies)
    min_latency = min(latencies)
    max_latency = max(latencies)
    
    logger.info("\n📈 آمار:")
    logger.info(f"   میانگین Latency: {avg_latency:.2f}ms")
    logger.info(f"   سریع‌ترین: {min_latency}ms")
    logger.info(f"   کندترین: {max_latency}ms")
    logger.info("=" * 60)


async def main():
    """تابع اصلی"""
    logger.info("\n" + "=" * 60)
    logger.info("🧪 Telegram Proxy Local Tester")
    logger.info("=" * 60 + "\n")
    
    file_path = "TELEGRAM_PROXY_SUB_TXT"
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    
    max_tests = 10
    if len(sys.argv) > 2:
        try:
            max_tests = int(sys.argv[2])
        except ValueError:
            logger.warning("⚠️  پارامتر دوم باید عدد باشد")
    
    await test_proxies_from_file(file_path, max_tests)
    
    logger.info("\n💡 نکات:")
    logger.info("• اگر فایل وجود ندارد، ابتدا proxy_collector.py را اجرا کنید")
    logger.info("• می‌توانید تعداد تست‌ها را مشخص کنید:")
    logger.info("  python test_proxy_local.py TELEGRAM_PROXY_SUB_TXT 20")
    logger.info("")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⚠️  برنامه توقف یافت (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ خطا: {e}", exc_info=True)
        sys.exit(1)
