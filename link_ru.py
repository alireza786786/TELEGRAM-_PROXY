def extract_configs_from_sources(sources_text):
    """دریافت محتوا از سورس‌ها با گزارش‌دهی دقیق تک‌تک لینک‌ها در لاگ گیتهاب"""
    links = [line.strip() for line in re.split(r'[\r\n,]+', sources_text) if line.strip()]
    total_links = len(links)
    print(f"\n==========================================")
    print(f"🔍 تعداد کل لینک‌های شناسایی‌شده در SOURCE_1: {total_links} عدد")
    print(f"==========================================")
    
    if total_links == 0:
        print("[❌] هیچ لینکی در SOURCE_1 پیدا نشد! لطفا سکرت را بررسی کنید.")
        return []

    raw_configs = []
    
    for idx, url in enumerate(links, 1):
        # نمایش دامنه لینک برای تشخیص بدون مسدود شدن توسط سکرت گیتهاب
        domain = urllib.parse.urlsplit(url).netloc or "لینک ساب"
        print(f"[{idx}/{total_links}] 🌐 در حال خواندن سورس ({domain})...")
        
        try:
            headers = {'User-Agent': 'v2rayNG/1.8.5'}
            resp = requests.get(url, headers=headers, timeout=12)
            
            if resp.status_code == 200:
                text = resp.text.strip()
                # بررسی دیکود بیس۶۴ در صورت ساب‌اسکریپشن بودن
                try:
                    decoded = base64.b64decode(text).decode('utf-8', errors='ignore')
                    if any(p in decoded for p in ["vmess://", "vless://", "ss://", "trojan://"]):
                        text = decoded
                except Exception:
                    pass
                
                found = re.findall(r'((?:vmess|vless|trojan|ss|ssr|hysteria|hy2|tuic)://[^\s]+)', text)
                print(f"    ✅ موفق! (کد وضعیت ۲۰۰) | تعداد {len(found)} کانفیگ از این لینک استخراج شد.")
                raw_configs.extend(found)
            else:
                print(f"    ⚠️ خطا در پاسخ سرور! کد وضعیت: {resp.status_code}")
                
        except Exception as e:
            print(f"    ❌ سورس شماره {idx} باز نشد یا تایم‌اوت داد: {e}")
            continue

    unique_configs = list(dict.fromkeys(raw_configs))
    print(f"==========================================")
    print(f"📊 مجموع کل کانفیگ‌های خام قبل از حذف تکراری: {len(raw_configs)}")
    print(f"✨ مجموع کانفیگ‌های یکتا (تکراری‌ها حذف شدند): {len(unique_configs)}")
    print(f"==========================================\n")
    
    return unique_configs
