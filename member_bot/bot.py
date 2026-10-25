import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import aiosqlite

# ==================== متغیرها ====================
# دریافت متغیرها بر اساس اسامی که مشخص کردید
BOT_TOKEN = os.environ.get("BOT_TOKEN1", "").strip()
CHAT_ID = int(os.environ.get("CHAT_ID", 0))

REQUIRED_INVITES = 3  # شرط دعوت ۳ نفر (هم برای کاربران عادی و هم برای ادمین‌ها)

# متن تبلیغاتی که ادمین باید در کانالش منتشر کند
PROMO_TEXT = "🚀 برای دریافت بهترین پروکسی‌ها و اینترنت پرسرعت به ما بپیوندید:\nhttps://t.me/Goodbaye_filtering"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# استیت‌های مربوط به مراحل احراز هویت ادمین
class AdminForm(StatesGroup):
    waiting_for_channel = State()
    waiting_for_forward = State()

# ==================== ساخت پایگاه داده ====================
async def init_db():
    async with aiosqlite.connect("member_bot/database.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                invited_count INTEGER DEFAULT 0,
                referrer_id INTEGER DEFAULT 0,
                is_admin INTEGER DEFAULT 0,
                promo_approved INTEGER DEFAULT 0,
                has_joined INTEGER DEFAULT 0
            )
        """)
        await db.commit()

# ==================== دریافت درخواست عضویت در کانال ====================
@dp.chat_join_request(F.chat.id == CHAT_ID)
async def handle_join_request(event: types.ChatJoinRequest):
    user_id = event.from_user.id
    async with aiosqlite.connect("member_bot/database.db") as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await db.commit()

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="👥 دریافت لینک دعوت (کاربر عادی)", callback_data="get_ref_link")],
        [types.InlineKeyboardButton(text="📢 من ادمین کانال هستم", callback_data="start_admin_verify")]
    ])

    text = (
        f"سلام {event.from_user.first_name} عزیز! 🌹\n\n"
        f"درخواست عضویت شما دریافت شد. جهت تایید ورود به کانال:\n\n"
        f"▫️ <b>کاربران عادی:</b> باید <b>{REQUIRED_INVITES} نفر</b> را با لینک خود به ربات دعوت کنند.\n"
        f"▫️ <b>ادمین‌های کانال:</b> باید ربات را در کانال خود اضافه کرده، متن تبلیغ ما را در کانالشان منتشر کنند و <b>همچنین {REQUIRED_INVITES} نفر</b> را دعوت کنند."
    )
    try:
        await bot.send_message(chat_id=user_id, text=text, parse_mode="HTML", reply_markup=keyboard)
    except Exception as e:
        logging.warning(f"ارسال پیام به کاربر ناموفق بود: {e}")

# ==================== دستور استارت و رفرال ====================
@dp.message(CommandStart())
async def start_handler(message: types.Message, command: CommandObject):
    user_id = message.from_user.id
    ref_id = None
    
    if command.args and command.args.startswith("ref_"):
        try:
            ref_id = int(command.args.split("_")[1])
        except ValueError:
            pass

    async with aiosqlite.connect("member_bot/database.db") as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        exists = await cursor.fetchone()

        if not exists:
            await db.execute("INSERT INTO users (user_id, referrer_id) VALUES (?, ?)", (user_id, ref_id or 0))
            await db.commit()
            
            # ثبت امتیاز برای شخص دعوت‌کننده
            if ref_id and ref_id != user_id:
                await db.execute("UPDATE users SET invited_count = invited_count + 1 WHERE user_id = ?", (ref_id,))
                await db.commit()
                
                # بررسی شرایط تکمیل عضویت دعوت‌کننده
                cur = await db.execute("SELECT invited_count, is_admin, promo_approved, has_joined FROM users WHERE user_id = ?", (ref_id,))
                row = await cur.fetchone()
                if row and row[3] == 0:
                    invites, is_admin, promo_ok, joined = row
                    
                    # کاربر عادی: فقط ۳ دعوت
                    if is_admin == 0 and invites >= REQUIRED_INVITES:
                        await approve_and_welcome(ref_id)
                    # ادمین کانال: ۳ دعوت + تایید تبلیغ
                    elif is_admin == 1 and invites >= REQUIRED_INVITES and promo_ok == 1:
                        await approve_and_welcome(ref_id)

    await message.answer(
        "به ربات احراز عضویت خوش آمدید!\nجهت دریافت لینک دعوت خود، روی دکمه زیر کلیک کنید:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔗 دریافت لینک دعوت", callback_data="get_ref_link")]
        ])
    )

# ==================== تولید لینک رفرال ====================
@dp.callback_query(F.data == "get_ref_link")
async def send_ref_link(callback: types.CallbackQuery):
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{callback.from_user.id}"
    
    async with aiosqlite.connect("member_bot/database.db") as db:
        cur = await db.execute("SELECT invited_count, is_admin, promo_approved FROM users WHERE user_id = ?", (callback.from_user.id,))
        data = await cur.fetchone()
        count = data[0] if data else 0
        is_admin = data[1] if data else 0
        promo_ok = data[2] if data else 0

    role_status = ""
    if is_admin == 1:
        promo_status = "تایید شد ✅" if promo_ok == 1 else "هنوز انجام نشده ❌"
        role_status = f"\n📢 وضعیت تبلیغ در کانال شما: {promo_status}"

    await callback.message.answer(
        f"🔗 <b>لینک اختصاصی دعوت شما:</b>\n<code>{ref_link}</code>\n\n"
        f"📊 تعداد دعوت‌های شما: <b>{count} از {REQUIRED_INVITES} نفر</b>"
        f"{role_status}\n\n"
        f"به محض تکمیل شرایط، عضویت شما در کانال به صورت خودکار تایید خواهد شد.",
        parse_mode="HTML"
    )
    await callback.answer()

# ==================== مراحل احراز هویت و تبلیغ ادمین ====================
@dp.callback_query(F.data == "start_admin_verify")
async def admin_verify_step1(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminForm.waiting_for_channel)
    text = (
        "👑 <b>مراحل احراز هویت مدیران کانال:</b>\n\n"
        "1️⃣ ربات را با دسترسی مشاهده اعضا در کانال خود ادد (Admin) کنید.\n"
        "2️⃣ سپس آیدی عمومی کانال خود را ارسال کنید (مثلاً: <code>@channel_id</code>):"
    )
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@dp.message(AdminForm.waiting_for_channel)
async def check_admin_rights(message: types.Message, state: FSMContext):
    channel_input = message.text.strip()
    try:
        # بررسی اینکه آیا خود کاربر در آن کانال ادمین است
        chat_member = await bot.get_chat_member(chat_id=channel_input, user_id=message.from_user.id)
        if chat_member.status in ["administrator", "creator"]:
            await state.update_data(target_channel=channel_input)
            await state.set_state(AdminForm.waiting_for_forward)
            
            # تغییر نقش کاربر به ادمین در دیتابیس
            async with aiosqlite.connect("member_bot/database.db") as db:
                await db.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (message.from_user.id,))
                await db.commit()

            await message.answer(
                f"✅ ادمین بودن شما در کانال {channel_input} تایید شد!\n\n"
                f"📢 <b>مرحله بعدی (تبلیغ):</b> متن زیر را در کانال خود پست کنید و سپس آن پیام را به این ربات <b>فوروارد (Forward)</b> کنید:\n\n"
                f"<code>{PROMO_TEXT}</code>",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ شما در این کانال مدیر نیستید! لطفاً کانال متعلق به خودتان را وارد کنید.")
    except Exception as e:
        await message.answer(f"❌ ربات نتوانست به کانال شما دسترسی پیدا کند. مطمئن شوید ربات در کانال شما ادمین شده است.\nخطا: {e}")

@dp.message(AdminForm.waiting_for_forward)
async def check_forwarded_promo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    expected_channel = data.get("target_channel")
    
    # اطمینان از اینکه پیام از کانال خود کاربر فوروارد شده است
    if message.forward_from_chat:
        user_ch_username = message.forward_from_chat.username
        user_ch_id = str(message.forward_from_chat.id)
        
        if (user_ch_username and f"@{user_ch_username}".lower() == expected_channel.lower()) or (user_ch_id in expected_channel):
            async with aiosqlite.connect("member_bot/database.db") as db:
                await db.execute("UPDATE users SET promo_approved = 1 WHERE user_id = ?", (message.from_user.id,))
                await db.commit()
                
                # بررسی تعداد دعوت‌های ادمین
                cur = await db.execute("SELECT invited_count FROM users WHERE user_id = ?", (message.from_user.id,))
                inv_data = await cur.fetchone()
                inv_count = inv_data[0] if inv_data else 0

            await state.clear()
            
            # اگر از قبل ۳ نفر را دعوت کرده باشد، بلافاصله تایید می‌شود
            if inv_count >= REQUIRED_INVITES:
                await approve_and_welcome(message.from_user.id)
            else:
                await message.answer(
                    f"🎉 پست تبلیغاتی با موفقیت تایید شد!\n\n"
                    f"اکنون فقط شرط پایانی باقی مانده است: باید <b>{REQUIRED_INVITES} نفر</b> را با لینک اختصاصی خود به ربات دعوت کنید.\n"
                    f"تعداد دعوت‌های فعلی شما: <b>{inv_count} از {REQUIRED_INVITES}</b>",
                    parse_mode="HTML",
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                        [types.InlineKeyboardButton(text="🔗 دریافت لینک دعوت", callback_data="get_ref_link")]
                    ])
                )
        else:
            await message.answer("❌ پیام ارسال‌شده از کانال ثبت‌شده شما نیست!")
    else:
        await message.answer("❌ لطفاً پیام تبلیغ را مستقیماً از کانال خود به اینجا فوروارد (Forward) کنید.")

# ==================== تابع تایید عضویت و ارسال پیام خوش‌آمدگویی ====================
async def approve_and_welcome(user_id: int):
    try:
        # ۱. تایید درخواست عضویت در کانال تلگرام
        await bot.approve_chat_join_request(chat_id=CHAT_ID, user_id=user_id)
        
        # ۲. به‌روزرسانی دیتابیس
        async with aiosqlite.connect("member_bot/database.db") as db:
            await db.execute("UPDATE users SET has_joined = 1 WHERE user_id = ?", (user_id,))
            await db.commit()

        # ۳. ارسال پیام خوش‌آمدگویی شکیل به کاربر
        welcome_text = (
            "🎉 <b>عضویت شما با موفقیت تایید شد!</b>\n\n"
            "درخواست ورود شما به کانال مورد تایید قرار گرفت و هم‌اکنون به عنوان عضو رسمی پذیرفته شدید.\n\n"
            "🌹 <i>به جمع ما خوش آمدید!</i>"
        )
        await bot.send_message(chat_id=user_id, text=welcome_text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"خطا در تایید کاربر {user_id}: {e}")

# ==================== شروع به کار ربات ====================
async def main():
    await init_db()
    print("[*] ربات عضویت با موفقیت فعال شد و آماده دریافت درخواست‌ها است...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
