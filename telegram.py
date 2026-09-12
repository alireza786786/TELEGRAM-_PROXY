# -*- coding: utf-8 -*-
"""انتشار به تلگرام: ساخت فایل‌های اشتراک و ارسال با sendDocument."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import List, Tuple

import aiohttp

from .config import CFG
from .models import ScoredNode

log = logging.getLogger("v2ray")


class TelegramSender:
    def __init__(self):
        self.base = f"https://api.telegram.org/bot{CFG.bot_token}"
        self.semaphore = asyncio.Semaphore(3)

    async def _send_one(self, session: aiohttp.ClientSession,
                         file_path: str, caption: str, num: int) -> bool:
        async with self.semaphore:
            for attempt in range(3):
                try:
                    data = aiohttp.FormData()
                    data.add_field('chat_id', CFG.chat_id)
                    data.add_field('caption', caption)
                    with open(file_path, 'rb') as f:
                        data.add_field('document', f, filename=file_path)
                        async with session.post(
                            f"{self.base}/sendDocument", data=data,
                            timeout=aiohttp.ClientTimeout(total=60)
                        ) as resp:
                            r = await resp.json()
                    if r.get("ok"):
                        log.info(f"   ✅ پارت {num} ارسال شد")
                        return True
                    log.warning(f"   ⚠️ خطا: {r.get('description')}")
                    retry_after = r.get("parameters", {}).get("retry_after")
                    if retry_after:
                        await asyncio.sleep(retry_after)
                except Exception as e:
                    log.error(f"   ❌ Attempt {attempt+1}: {e}")
                    await asyncio.sleep(2 ** attempt)
        return False

    def build(self, nodes: List[ScoredNode]) -> List[Tuple[str, str]]:
        parts: List[Tuple[str, str]] = []
        for i in range(0, len(nodes), CFG.chunk_size):
            n = (i // CFG.chunk_size) + 1
            chunk = nodes[i:i + CFG.chunk_size]
            fname = f"subscription_part{n}.txt"
            header = (
                f"# 🔥 اشتراک هوشمند V2Ray v4\n"
                f"# 📦 فایل: {fname}\n"
                f"# 📊 تعداد: {len(chunk)} کانفیگ تست‌شده\n"
                f"# ⏰ زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"# ✨ {CFG.telegram_link}\n"
                f"# {'='*50}\n"
            )
            with open(fname, "w", encoding="utf-8") as f:
                # config از قبل با ConfigParser.rename ساخته شده؛ دوباره #name نزن
                f.write(header + "\n".join(x.config for x in chunk))
            caption = (
                f"🔥 *اشتراک هوشمند - پارت {n}*\n\n"
                f"📦 فایل: `{fname}`\n"
                f"📊 تعداد: *{len(chunk)}* کانفیگ تست‌شده\n\n"
                f"💬 گروه: {CFG.group_link}\n"
                f"✨ کانال: {CFG.telegram_link}"
            )
            parts.append((fname, caption))
        return parts

    async def send_all(self, parts: List[Tuple[str, str]]):
        if not CFG.bot_token or not CFG.chat_id:
            log.warning("⚠️ BOT_TOKEN یا CHAT_ID تنظیم نشده. فقط فایل‌ها ساخته می‌شوند.")
            return
        async with aiohttp.ClientSession() as session:
            tasks = [self._send_one(session, f, c, i)
                     for i, (f, c) in enumerate(parts, 1)]
            await asyncio.gather(*tasks)