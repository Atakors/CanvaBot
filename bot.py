"""
Telegram Bot implementation for Canva Distribution System (Algeria 🇩🇿).
Includes multi-language support (العربية 🇩🇿, Français 🇫🇷, English 🇬🇧),
native Telegram command menu, inline query sharing, and polished UI design.
"""

import os
import re
import io
import logging
from typing import Optional

import telebot
from telebot import types

from config import settings
import database as db
from receipt_verifier import verify_baridimob_receipt, ReceiptVerificationResult
from translations import t

logger = logging.getLogger(__name__)

# Initialize bot safely
bot_token = settings.BOT_TOKEN if (settings.BOT_TOKEN and ":" in settings.BOT_TOKEN) else "123456789:AABBFakeTokenForModuleImportOnly123456"
bot = telebot.TeleBot(bot_token, parse_mode="Markdown")

# Robust email regex
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_admin(user_id: int) -> bool:
    """Checks if a user is the primary system administrator."""
    return user_id == settings.ADMIN_ID


def get_lang(user_id: int) -> str:
    """Retrieves user's preferred language with 'fr' as default."""
    try:
        return db.get_user_language(user_id)
    except Exception:
        return "fr"


def check_channel_membership(user_id: int) -> bool:
    """Checks if user has joined the mandatory channel."""
    if not settings.REQUIRED_CHANNEL or settings.REQUIRED_CHANNEL.strip() == "":
        return True

    channel = settings.REQUIRED_CHANNEL.strip()
    if channel in ["@YourChannelUsername", "YourChannelUsername"]:
        if settings.CHANNEL_INVITE_LINK:
            m = re.search(r"t\.me/([a-zA-Z0-9_]+)", settings.CHANNEL_INVITE_LINK)
            if m and not m.group(1).startswith("+"):
                channel = f"@{m.group(1)}"
            else:
                return True
        else:
            return True

    try:
        member = bot.get_chat_member(chat_id=channel, user_id=user_id)
        return member.status in ["creator", "administrator", "member", "restricted"]
    except Exception as e:
        error_str = str(e).lower()
        logger.warning(f"Could not verify channel membership for {user_id} in {channel}: {e}")
        # If user is not in the chat, they have definitely not joined!
        if "user not found" in error_str or "user is not a member" in error_str:
            return False
        return False


def get_channel_link() -> str:
    """Returns the channel join URL."""
    if settings.CHANNEL_INVITE_LINK:
        return settings.CHANNEL_INVITE_LINK
    channel = settings.REQUIRED_CHANNEL
    if channel.startswith("@"):
        return f"https://t.me/{channel[1:]}"
    return "https://t.me/"


def setup_bot_commands():
    """Configures Telegram native menu commands."""
    try:
        user_commands = [
            types.BotCommand("start", "🚀 الرئيسية / Menu Principal"),
            types.BotCommand("pay", "💳 تفعيل كانفا / Activer 500 DZD"),
            types.BotCommand("affiliate", "🎁 برنامج المكافآت / Programme Cadeaux"),
            types.BotCommand("status", "📊 حالة حسابي / Mon Statut"),
            types.BotCommand("lang", "🌐 تغيير اللغة / Changer de Langue"),
            types.BotCommand("help", "❓ مساعدة ودليل / Aide & FAQ"),
        ]
        bot.set_my_commands(user_commands)
        logger.info("Bot menu commands registered successfully.")
    except Exception as e:
        logger.warning(f"Could not set bot commands: {e}")


# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------

def get_main_menu_keyboard(user: dict, lang: str = "fr") -> types.InlineKeyboardMarkup:
    """Generates the embellished main menu keyboard in user's language."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    status = user.get("status", "NEW")
    
    # Primary CTA
    if status in ["NEW", "AWAITING_RECEIPT"]:
        markup.add(types.InlineKeyboardButton(t("btn_pay", lang), callback_data="cb_paid"))
    elif status == "AWAITING_EMAIL":
        markup.add(types.InlineKeyboardButton(t("btn_enter_email", lang), callback_data="cb_enter_email"))

    # Affiliate / Rewards
    markup.add(types.InlineKeyboardButton(t("btn_affiliate", lang), callback_data="cb_referral"))

    # Status & Help in one row
    markup.row(
        types.InlineKeyboardButton(t("btn_status", lang), callback_data="cb_status"),
        types.InlineKeyboardButton(t("btn_help", lang), callback_data="cb_help")
    )

    # Language Switcher
    markup.add(types.InlineKeyboardButton(t("btn_lang", lang), callback_data="cb_lang"))
    return markup


def get_language_keyboard(lang: str = "fr") -> types.InlineKeyboardMarkup:
    """Generates language selection keyboard."""
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton("🇩🇿 العربية", callback_data="cb_set_lang_ar"),
        types.InlineKeyboardButton("🇫🇷 Français", callback_data="cb_set_lang_fr"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="cb_set_lang_en"),
    )
    markup.add(types.InlineKeyboardButton(t("btn_back_menu", lang), callback_data="cb_menu"))
    return markup


# ---------------------------------------------------------------------------
# User Commands
# ---------------------------------------------------------------------------

@bot.message_handler(commands=["start"])
def handle_start(message: types.Message):
    """
    Handles /start command with optional referral argument:
    Example: /start ref_12345678 or /start 12345678
    """
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # Parse referral parameter
    referred_by = None
    args = message.text.split()
    if len(args) > 1:
        param = args[1]
        if param.startswith("ref_"):
            cand = param[4:]
            if cand.isdigit():
                referred_by = int(cand)
        elif param.isdigit():
            referred_by = int(param)

    # Fetch or register user in DB
    user, is_new = db.create_or_get_user(
        user_id=user_id,
        username=username,
        first_name=first_name,
        referred_by=referred_by
    )
    lang = user.get("language") or "fr"

    # Check Channel Membership Gate
    is_member = check_channel_membership(user_id)
    if not is_member:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton(t("btn_join_channel", lang), url=get_channel_link()),
            types.InlineKeyboardButton(t("btn_verify_channel", lang), callback_data="cb_verify_membership"),
            types.InlineKeyboardButton(t("btn_lang", lang), callback_data="cb_lang")
        )
        channel_name = settings.REQUIRED_CHANNEL
        if channel_name in ["@YourChannelUsername", "YourChannelUsername"] and settings.CHANNEL_INVITE_LINK:
            m = re.search(r"t\.me/([a-zA-Z0-9_]+)", settings.CHANNEL_INVITE_LINK)
            if m:
                channel_name = f"@{m.group(1)}"
        text = t("channel_gate_title", lang, first_name=first_name, channel=channel_name)
        bot.send_message(message.chat.id, text, reply_markup=markup)
        return

    # If already a member and was referred, verify join
    if user.get("referred_by") and user.get("referral_verified") == 0:
        verify_result = db.verify_referral_join(user_id)
        if verify_result:
            referrer_id, new_count = verify_result
            notify_referrer_progress(referrer_id, new_count)

    # Render Welcome Screen
    stats = db.get_system_stats()
    text = t(
        "welcome_menu",
        lang,
        first_name=first_name,
        remaining=stats["remaining_seats"],
        max_seats=settings.MAX_SEATS,
        amount=settings.PAYMENT_AMOUNT
    )
    bot.send_message(message.chat.id, text, reply_markup=get_main_menu_keyboard(user, lang))


@bot.message_handler(commands=["pay"])
def handle_pay_command(message: types.Message):
    """Direct payment instructions command."""
    user_id = message.from_user.id
    lang = get_lang(user_id)
    db.update_user_status(user_id, "AWAITING_RECEIPT")
    
    text = t(
        "payment_instructions",
        lang,
        amount=settings.PAYMENT_AMOUNT,
        rip=settings.TARGET_RIP,
        ccp=settings.TARGET_CCP,
        holder=settings.ACCOUNT_HOLDER
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(t("btn_back_menu", lang), callback_data="cb_menu"))
    bot.send_message(message.chat.id, text, reply_markup=markup)


@bot.message_handler(commands=["affiliate", "referrals", "rewards"])
def handle_affiliate_command(message: types.Message):
    """Direct affiliate/rewards dashboard command."""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    if not user:
        user, _ = db.create_or_get_user(user_id, message.from_user.username, message.from_user.first_name)
    show_affiliate_screen(message.chat.id, user)


@bot.message_handler(commands=["status"])
def handle_status_command(message: types.Message):
    """Direct account status command."""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    if not user:
        user, _ = db.create_or_get_user(user_id, message.from_user.username, message.from_user.first_name)
    show_status_screen(message.chat.id, user)


@bot.message_handler(commands=["help", "faq"])
def handle_help_command(message: types.Message):
    """Direct help and FAQ command."""
    user_id = message.from_user.id
    lang = get_lang(user_id)
    text = t("help_faq", lang)
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(t("btn_back_menu", lang), callback_data="cb_menu"))
    bot.send_message(message.chat.id, text, reply_markup=markup)


@bot.message_handler(commands=["lang", "language"])
def handle_language_command(message: types.Message):
    """Direct language selector command."""
    user_id = message.from_user.id
    lang = get_lang(user_id)
    text = t("lang_selection_title", lang)
    bot.send_message(message.chat.id, text, reply_markup=get_language_keyboard(lang))


# ---------------------------------------------------------------------------
# Notifications to Referrer
# ---------------------------------------------------------------------------

def notify_referrer_progress(referrer_id: int, new_count: int):
    """Sends a notification to the referrer when an invited friend joins the channel."""
    lang = get_lang(referrer_id)
    try:
        if lang == "ar":
            msg = (
                f"👥 *صديق جديد انضم عبر رابطك!* 🇩🇿\n\n"
                f"قام صديق بالانضمام عبر رابط الإحالة الخاص بك.\n"
                f"💡 *تذكير*: بمجرد قيامه بتفعيل Canva (دفع 500 دج)، سيتم احتسابه كـ *إحالة مدفوعة* نحو هديتك المجانية (5 إحالات مدفوعة = هدية حصرية)!"
            )
        elif lang == "fr":
            msg = (
                f"👥 *Un ami a rejoint via votre lien !* 🇩🇿\n\n"
                f"Dès qu'il active son compte Canva (500 DZD), il sera comptabilisé dans vos *parrainages payants* "
                f"pour débloquer votre cadeau exclusif (5 payants = 1 cadeau gratuit) !"
            )
        else:
            msg = (
                f"👥 *A friend joined using your referral link!* 🇩🇿\n\n"
                f"Once they complete Canva activation (500 DZD), they will count toward your *Paid Referrals* "
                f"to earn an exclusive freebie reward (5 paid = 1 reward)!"
            )
        bot.send_message(referrer_id, msg)
    except Exception as e:
        logger.warning(f"Could not send join notification to referrer {referrer_id}: {e}")


def notify_referrer_paid_invite(referrer_id: int, new_paid_count: int, reward_unlocked: bool):
    """Sends a notification to the referrer when an invited friend pays."""
    lang = get_lang(referrer_id)
    target = getattr(settings, "PAID_REFERRALS_FOR_REWARD", 5)
    try:
        if reward_unlocked:
            if lang == "ar":
                msg = (
                    f"🎁 *ألف مبروك! لقد فتحت مكافأة جديدة!* 🚀\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"لقد حققت *{new_paid_count} إحالات مدفوعة* بنجاح!\n"
                    f"استحققت الآن *هدية مجانية حصرية (Freebie Gift)*! 🎁\n\n"
                    f"تم إشعار إدارة البوت وسيقوم المشرف بتسليم هديتك قريباً جداً. شكراً لثقتكم ومشاركتكم!"
                )
            elif lang == "fr":
                msg = (
                    f"🎁 *FÉLICITATIONS ! RÉCOMPENSE DÉBLOQUÉE !* 🚀\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"Vous avez atteint *{new_paid_count} parrainages payants* !\n"
                    f"Vous avez gagné un *Cadeau Digital Exclusif (Freebie)* ! 🎁\n\n"
                    f"Notre équipe administrative a été notifiée et vous livrera votre cadeau très bientôt. Merci pour votre fidélité !"
                )
            else:
                msg = (
                    f"🎁 *CONGRATULATIONS! REWARD UNLOCKED!* 🚀\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"You have reached *{new_paid_count} paid referrals*!\n"
                    f"You earned an *Exclusive Freebie Gift*! 🎁\n\n"
                    f"Our admin team has been notified and will deliver your reward shortly. Thank you!"
                )
            bot.send_message(referrer_id, msg)
            
            # Notify Admin
            if settings.ADMIN_ID and settings.ADMIN_ID != 0:
                admin_alert = (
                    f"🎁 *NEW REWARD UNLOCKED! (5 PAID INVITES)*\n"
                    f"• Referrer User ID: `{referrer_id}`\n"
                    f"• Total Paid Referrals: `{new_paid_count}`\n"
                    f"👉 Check Web Dashboard or use `/deliver_reward {referrer_id}` to deliver their freebie."
                )
                bot.send_message(settings.ADMIN_ID, admin_alert)
        else:
            remaining = target - (new_paid_count % target)
            if lang == "ar":
                msg = (
                    f"🎉 *إحالة مدفوعة جديدة مؤكدة!* 💰\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"قام أحد أصدقائك بدفع وتفعيل اشتراك كانفا بنجاح!\n"
                    f"• تقدمك الحالي: *{new_paid_count}* إحالات مدفوعة.\n"
                    f"• المتبقي لهديتك القادمة: *{remaining}* فقط!"
                )
            elif lang == "fr":
                msg = (
                    f"🎉 *Nouveau Parrainage Payant Validé !* 💰\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"Un ami parrainé vient de payer son accès Canva !\n"
                    f"• Votre total : *{new_paid_count}* parrainages payants.\n"
                    f"• Plus que *{remaining}* pour débloquer votre prochain cadeau exclusif !"
                )
            else:
                msg = (
                    f"🎉 *New Paid Referral Confirmed!* 💰\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"A friend you referred just completed their payment!\n"
                    f"• Your total: *{new_paid_count}* paid invites.\n"
                    f"• Only *{remaining} more* needed for your next Freebie reward!"
                )
            bot.send_message(referrer_id, msg)
    except Exception as e:
        logger.warning(f"Could not notify referrer {referrer_id}: {e}")


# ---------------------------------------------------------------------------
# UI View Renderers
# ---------------------------------------------------------------------------

def show_affiliate_screen(chat_id: int, user: dict):
    """Renders the affiliate and reward dashboard."""
    user_id = user["user_id"]
    lang = user.get("language") or "fr"
    has_paid = user.get("status") in ["AWAITING_EMAIL", "PENDING_INVITE", "INVITED"] or user.get("unlock_method") == "PAID"
    
    if not has_paid:
        text = t("affiliate_locked", lang)
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton(t("btn_pay", lang), callback_data="cb_paid"),
            types.InlineKeyboardButton(t("btn_back_menu", lang), callback_data="cb_menu")
        )
        bot.send_message(chat_id, text, reply_markup=markup)
        return

    bot_info = bot.get_me()
    bot_username = bot_info.username or "CanvaProBot"
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

    paid_count = user.get("paid_referrals_count", 0) or 0
    target = getattr(settings, "PAID_REFERRALS_FOR_REWARD", 5)
    rewards_claimed = user.get("rewards_claimed", 0) or 0
    needed_for_next = target - (paid_count % target) if (paid_count % target) != 0 else target

    share_text = t("share_link_text", lang)
    share_url = f"https://t.me/share/url?url={ref_link}&text={share_text}"

    text = t(
        "affiliate_dashboard",
        lang,
        target=target,
        link=ref_link,
        paid_count=paid_count,
        claimed=rewards_claimed,
        needed=needed_for_next,
        revenue=paid_count * settings.PAYMENT_AMOUNT
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(t("btn_share_link", lang), url=share_url),
        types.InlineKeyboardButton(t("btn_refresh", lang), callback_data="cb_referral"),
        types.InlineKeyboardButton(t("btn_back_menu", lang), callback_data="cb_menu")
    )
    bot.send_message(chat_id, text, reply_markup=markup)


def show_status_screen(chat_id: int, user: dict):
    """Renders the account status screen."""
    user_id = user["user_id"]
    lang = user.get("language") or "fr"
    status = user.get("status", "NEW")
    email = user.get("email") or ("غير محدد" if lang == "ar" else "Non renseigné")
    paid_refs = user.get("paid_referrals_count", 0) or 0
    rewards = user.get("rewards_claimed", 0) or 0
    
    badge_key = f"status_badge_{status.lower()}"
    status_badge = t(badge_key, lang)

    extra_hint = ""
    if status == "AWAITING_EMAIL":
        extra_hint = "👉 " + t("email_prompt", lang)
    elif status == "PENDING_INVITE":
        extra_hint = "✅ " + ("مقعدك محجوز رسمياً وبانتظار وصول الإيميل." if lang == "ar" else "Votre place est réservée. L'invitation par e-mail arrive bientôt.")

    text = t(
        "account_status_card",
        lang,
        user_id=user_id,
        status_badge=status_badge,
        email=email,
        paid_refs=paid_refs,
        rewards=rewards,
        extra_hint=extra_hint
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    if status in ["NEW", "AWAITING_RECEIPT"]:
        markup.add(types.InlineKeyboardButton(t("btn_pay", lang), callback_data="cb_paid"))
    else:
        markup.add(types.InlineKeyboardButton(t("btn_affiliate", lang), callback_data="cb_referral"))
    markup.add(types.InlineKeyboardButton(t("btn_back_menu", lang), callback_data="cb_menu"))
    bot.send_message(chat_id, text, reply_markup=markup)


# ---------------------------------------------------------------------------
# Callback Query Handlers
# ---------------------------------------------------------------------------

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call: types.CallbackQuery):
    """Processes all inline button clicks."""
    user_id = call.from_user.id
    first_name = call.from_user.first_name
    data = call.data
    
    user = db.get_user(user_id)
    if not user:
        user, _ = db.create_or_get_user(user_id, call.from_user.username, first_name)
    lang = user.get("language") or "fr"

    if data.startswith("cb_set_lang_"):
        new_lang = data.split("_")[-1]
        db.set_user_language(user_id, new_lang)
        bot.answer_callback_query(call.id, t("lang_switched", new_lang), show_alert=False)
        user = db.get_user(user_id)
        stats = db.get_system_stats()
        text = t(
            "welcome_menu",
            new_lang,
            first_name=first_name,
            remaining=stats["remaining_seats"],
            max_seats=settings.MAX_SEATS,
            amount=settings.PAYMENT_AMOUNT
        )
        try:
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_main_menu_keyboard(user, new_lang)
            )
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=get_main_menu_keyboard(user, new_lang))

    elif data == "cb_lang":
        bot.answer_callback_query(call.id)
        text = t("lang_selection_title", lang)
        bot.send_message(call.message.chat.id, text, reply_markup=get_language_keyboard(lang))

    elif data == "cb_verify_membership":
        is_member = check_channel_membership(user_id)
        if not is_member:
            bot.answer_callback_query(call.id, t("channel_gate_alert_not_member", lang), show_alert=True)
            return

        bot.answer_callback_query(call.id, "✅ OK!")
        
        # Verify referral credit if applicable
        if user.get("referred_by") and user.get("referral_verified") == 0:
            verify_result = db.verify_referral_join(user_id)
            if verify_result:
                ref_id, count = verify_result
                notify_referrer_progress(ref_id, count)

        user = db.get_user(user_id)
        stats = db.get_system_stats()
        text = t(
            "welcome_menu",
            lang,
            first_name=first_name,
            remaining=stats["remaining_seats"],
            max_seats=settings.MAX_SEATS,
            amount=settings.PAYMENT_AMOUNT
        )
        bot.send_message(call.message.chat.id, text, reply_markup=get_main_menu_keyboard(user, lang))

    elif data == "cb_paid":
        bot.answer_callback_query(call.id)
        db.update_user_status(user_id, "AWAITING_RECEIPT")
        
        text = t(
            "payment_instructions",
            lang,
            amount=settings.PAYMENT_AMOUNT,
            rip=settings.TARGET_RIP,
            ccp=settings.TARGET_CCP,
            holder=settings.ACCOUNT_HOLDER
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton(t("btn_back_menu", lang), callback_data="cb_menu"))
        bot.send_message(call.message.chat.id, text, reply_markup=markup)

    elif data == "cb_referral":
        bot.answer_callback_query(call.id)
        show_affiliate_screen(call.message.chat.id, user)

    elif data == "cb_status":
        bot.answer_callback_query(call.id)
        show_status_screen(call.message.chat.id, user)

    elif data == "cb_help":
        bot.answer_callback_query(call.id)
        text = t("help_faq", lang)
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton(t("btn_back_menu", lang), callback_data="cb_menu"))
        bot.send_message(call.message.chat.id, text, reply_markup=markup)

    elif data == "cb_enter_email":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, t("email_prompt", lang))

    elif data == "cb_menu":
        bot.answer_callback_query(call.id)
        stats = db.get_system_stats()
        text = t(
            "welcome_menu",
            lang,
            first_name=first_name,
            remaining=stats["remaining_seats"],
            max_seats=settings.MAX_SEATS,
            amount=settings.PAYMENT_AMOUNT
        )
        bot.send_message(call.message.chat.id, text, reply_markup=get_main_menu_keyboard(user, lang))


# ---------------------------------------------------------------------------
# Receipt Upload Handlers (PDF Documents & Photos)
# ---------------------------------------------------------------------------

@bot.message_handler(content_types=["document", "photo"])
def handle_receipt_upload(message: types.Message):
    """
    Handles PDF document or image photo uploads.
    Performs automated zero-API BaridiMob receipt validation.
    """
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    user, _ = db.create_or_get_user(user_id, username, first_name)
    lang = user.get("language") or "fr"
    current_status = user.get("status", "NEW")
    
    # Check if already invited or pending
    if current_status in ["PENDING_INVITE", "INVITED"]:
        already_msg = (
            f"ℹ️ مقعدك في Canva مؤكد مسبقاً! (البريد: `{user.get('email')}`). لا داعي لإرسال وصل آخر."
            if lang == "ar" else
            f"ℹ️ Votre place Canva est déjà confirmée ! (E-mail : `{user.get('email')}`). Aucun nouveau reçu requis."
        )
        bot.reply_to(message, already_msg)
        return

    # Check Seat Availability
    stats = db.get_system_stats()
    if stats["remaining_seats"] <= 0:
        bot.reply_to(message, t("all_seats_taken", lang))
        return

    status_msg = bot.reply_to(message, t("receipt_analyzing", lang))

    try:
        file_bytes: bytes = b""
        filename = "receipt.jpg"
        is_pdf = False

        if message.document:
            filename = message.document.file_name or "document.pdf"
            is_pdf = filename.lower().endswith(".pdf") or message.document.mime_type == "application/pdf"
            file_info = bot.get_file(message.document.file_id)
            file_bytes = bot.download_file(file_info.file_path)
        elif message.photo:
            photo = message.photo[-1]
            filename = "screenshot.jpg"
            file_info = bot.get_file(photo.file_id)
            file_bytes = bot.download_file(file_info.file_path)

        # Run verification engine
        result: ReceiptVerificationResult = verify_baridimob_receipt(
            file_bytes=file_bytes,
            filename=filename,
            is_pdf=is_pdf
        )

        if not result.is_valid:
            bot.edit_message_text(
                f"{result.error_message}\n\n{t('receipt_tip', lang)}",
                chat_id=message.chat.id,
                message_id=status_msg.message_id
            )
            return

        # Verification Succeeded! Save receipt & update user
        db.record_used_receipt(
            tx_id=result.tx_id,
            file_hash=result.file_hash,
            user_id=user_id,
            amount=result.amount or settings.PAYMENT_AMOUNT
        )
        db.update_user_status(
            user_id=user_id,
            status="AWAITING_EMAIL",
            unlock_method="PAID",
            tx_id=result.tx_id
        )

        # Credit paid referral to referrer (5 paid referrals = 1 freebie reward)
        paid_credit = db.credit_paid_referral(user_id)
        if paid_credit:
            ref_id, paid_count, unlocked = paid_credit
            notify_referrer_paid_invite(ref_id, paid_count, unlocked)

        op_line = f"• *Type d'opération*: `{result.operation_type}`\n" if result.operation_type else ""
        success_text = t(
            "receipt_verified_success",
            lang,
            tx_id=result.tx_id,
            amount=result.amount or settings.PAYMENT_AMOUNT,
            date=result.tx_date or "Aujourd'hui",
            account=result.account_matched or settings.TARGET_RIP,
            op_line=op_line
        )
        bot.edit_message_text(
            success_text,
            chat_id=message.chat.id,
            message_id=status_msg.message_id
        )

    except Exception as e:
        logger.error(f"Error processing receipt for user {user_id}: {e}", exc_info=True)
        bot.edit_message_text(
            "⚠️ An error occurred while analyzing your receipt. Please ensure the file is intact and try again.",
            chat_id=message.chat.id,
            message_id=status_msg.message_id
        )


# ---------------------------------------------------------------------------
# Email Submission & Text Message Handling
# ---------------------------------------------------------------------------

@bot.message_handler(content_types=["text"])
def handle_text_messages(message: types.Message):
    """Handles text messages, primarily email submissions."""
    user_id = message.from_user.id
    text = message.text.strip()
    
    if text.startswith("/"):
        return

    user = db.get_user(user_id)
    if not user:
        user, _ = db.create_or_get_user(user_id, message.from_user.username, message.from_user.first_name)
    lang = user.get("language") or "fr"
    current_status = user.get("status", "NEW")

    is_email_candidate = bool(EMAIL_REGEX.match(text))

    if current_status == "AWAITING_EMAIL" or (is_email_candidate and current_status in ["NEW", "AWAITING_RECEIPT"]):
        if not is_email_candidate:
            bot.reply_to(message, t("invalid_email_format", lang))
            return

        email = text.lower()

        # Check duplicate email
        if db.is_email_already_registered(email, exclude_user_id=user_id):
            bot.reply_to(message, t("email_already_registered", lang, email=email))
            return

        # Check seats
        stats = db.get_system_stats()
        if stats["remaining_seats"] <= 0:
            bot.reply_to(message, t("all_seats_taken", lang))
            return

        # Save email and transition to PENDING_INVITE
        db.set_user_email(user_id, email)
        updated_stats = db.get_system_stats()

        seat_num = updated_stats["claimed_seats"]
        confirm_text = t(
            "seat_confirmed_card",
            lang,
            email=email,
            seat_num=seat_num,
            max_seats=settings.MAX_SEATS
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton(t("btn_affiliate", lang), callback_data="cb_referral"),
            types.InlineKeyboardButton(t("btn_back_menu", lang), callback_data="cb_menu")
        )
        bot.reply_to(message, confirm_text, reply_markup=markup)

        # Notify Admin on Telegram
        if settings.ADMIN_ID and settings.ADMIN_ID != 0:
            admin_alert = (
                f"🔔 *New Canva Seat Reserved!*\n"
                f"• User: @{message.from_user.username or 'N/A'} (`{user_id}`)\n"
                f"• Email: `{email}`\n"
                f"• Method: PAID\n"
                f"• Total Seats Claimed: `{seat_num}/{settings.MAX_SEATS}`"
            )
            try:
                bot.send_message(settings.ADMIN_ID, admin_alert)
            except Exception as e:
                logger.warning(f"Failed to send admin alert to {settings.ADMIN_ID}: {e}")
        return

    # Fallback response
    bot.reply_to(
        message,
        "👋 " + t("welcome_menu", lang, first_name=message.from_user.first_name, remaining=db.get_system_stats()["remaining_seats"], max_seats=settings.MAX_SEATS, amount=settings.PAYMENT_AMOUNT),
        reply_markup=get_main_menu_keyboard(user, lang)
    )


# ---------------------------------------------------------------------------
# Inline Query Handler (@BotUsername in any chat)
# ---------------------------------------------------------------------------

@bot.inline_handler(lambda query: True)
def handle_inline_query(query: types.InlineQuery):
    """Allows users to share their referral invite card directly in any chat."""
    user_id = query.from_user.id
    user = db.get_user(user_id)
    lang = user.get("language") if user else "fr"

    bot_info = bot.get_me()
    bot_username = bot_info.username or "CanvaBot"
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

    title = "🎨 Canva Algérie (500 DZD) — Activation Instantanée"
    description = "اشترك في كانفا بـ 500 دج | Partagez pour gagner des cadeaux VIP"

    text = (
        f"🎨 *Canva Algeria Hub (500 DZD)* 🇩🇿\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"✨ *Obtenez Canva officiel pour seulement 500 DZD !*\n"
        f"Activation automatique et instantanée via BaridiMob.\n\n"
        f"✨ *احصل على اشتراك كانفا الرسمي بـ 500 دج فقط!*\n"
        f"تفعيل آلي فوري بدون انتظار عبر بريدي موب.\n\n"
        f"👉 *Rejoignez et activez votre compte ici* :\n{ref_link}"
    )

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🚀 تفعيل كانفا الآن | Activer Canva", url=ref_link))

    r = types.InlineQueryResultArticle(
        id=f"share_{user_id}",
        title=title,
        description=description,
        input_message_content=types.InputTextMessageContent(text, parse_mode="Markdown"),
        reply_markup=markup
    )
    bot.answer_inline_query(query.id, [r], cache_time=1)


# ---------------------------------------------------------------------------
# Administrator Commands
# ---------------------------------------------------------------------------

@bot.message_handler(commands=["admin"])
def handle_admin_command(message: types.Message):
    """Admin dashboard command."""
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Access denied. Administrator privileges required.")
        return

    stats = db.get_system_stats()
    text = (
        f"⚙️ *Canva Admin Control Panel*\n\n"
        f"👥 *Total Registered Users*: `{stats['total_users']}`\n"
        f"💳 *Paid Unlocks (500 DZD)*: `{stats['paid_unlocks']}` ({stats['total_revenue_dzd']:,.0f} DZD)\n"
        f"🤝 *Paid Referrals Generated*: `{stats.get('total_paid_referrals', 0)}`\n"
        f"🕒 *Pending Invites*: `{stats['pending_invites']}`\n"
        f"🎁 *Pending Freebie Claims*: `{stats.get('pending_rewards', 0)}`\n"
        f"✅ *Already Invited*: `{stats['invited_users']}`\n"
        f"🪑 *Total Seats Claimed*: `{stats['claimed_seats']}/{settings.MAX_SEATS}`\n"
        f"🟢 *Remaining Seats*: `{stats['remaining_seats']}`\n\n"
        f"Select an action or use admin commands:\n"
        f"• `/stats` - View stats summary\n"
        f"• `/export_csv` - Download Canva invite batch CSV\n"
        f"• `/pending_emails` - View pending invite emails\n"
        f"• `/rewards` - View pending 5-paid-invite freebie rewards\n"
        f"• `/deliver_reward <id>` - Deliver reward\n"
        f"• `/mark_invited <email>` - Mark user as invited\n"
        f"• `/bulk_mark_invited` - Mark all pending users as invited\n"
        f"• `/reset_system` - Clear database and restart from 0"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📥 Export CSV", callback_data="cb_admin_export"),
        types.InlineKeyboardButton("📋 Pending List", callback_data="cb_admin_pending"),
        types.InlineKeyboardButton("🎁 Rewards", callback_data="cb_admin_rewards"),
        types.InlineKeyboardButton("⚡ Bulk Mark Invited", callback_data="cb_admin_bulk_mark"),
        types.InlineKeyboardButton("🔄 Refresh", callback_data="cb_admin_refresh")
    )
    bot.send_message(message.chat.id, text, reply_markup=markup)


@bot.message_handler(commands=["stats"])
def handle_stats_command(message: types.Message):
    """View system statistics."""
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Admin only.")
        return

    stats = db.get_system_stats()
    percent_full = (stats["claimed_seats"] / settings.MAX_SEATS) * 100 if settings.MAX_SEATS > 0 else 0
    text = (
        f"📊 *SYSTEM METRICS (500-Seat Batch)*\n\n"
        f"🪑 *Capacity*: `{stats['claimed_seats']}/{settings.MAX_SEATS}` ({percent_full:.1f}% filled)\n"
        f"🟢 *Seats Available*: `{stats['remaining_seats']}`\n"
        f"👥 *Total Bot Users*: `{stats['total_users']}`\n"
        f"💳 *Paid Seats*: `{stats['paid_unlocks']}`\n"
        f"🤝 *Paid Referrals Generated*: `{stats.get('total_paid_referrals', 0)}`\n"
        f"📋 *Pending Invites*: `{stats['pending_invites']}`\n"
        f"🎁 *Pending Freebies*: `{stats.get('pending_rewards', 0)}`\n"
        f"✅ *Completed Invites*: `{stats['invited_users']}`\n"
        f"💰 *Total Revenue*: `{stats['total_revenue_dzd']:,.0f} DZD`"
    )
    bot.send_message(message.chat.id, text)


@bot.message_handler(commands=["export_csv"])
def handle_export_csv_command(message: types.Message):
    """Exports and sends the canva_invites_batch.csv directly to the chat."""
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Admin only.")
        return

    csv_content = db.export_canva_csv()
    if not csv_content.strip():
        bot.reply_to(message, "ℹ️ No emails collected yet.")
        return

    bio = io.BytesIO(csv_content.encode("utf-8"))
    bio.name = "canva_invites_batch.csv"
    bot.send_document(
        message.chat.id,
        document=bio,
        caption="📄 *Canva Invites Batch CSV*\nReady for 1-click batch import into Canva Admin Team settings."
    )


@bot.message_handler(commands=["pending_emails"])
def handle_pending_emails_command(message: types.Message):
    """Lists pending emails with quick mark commands."""
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Admin only.")
        return

    pending = db.get_pending_invite_users(limit=25)
    if not pending:
        bot.reply_to(message, "✅ No pending invites at the moment. All caught up!")
        return

    lines = ["📋 *PENDING CANVA INVITATION LIST*:\n"]
    for i, u in enumerate(pending, 1):
        lines.append(f"{i}. `{u['email']}` (@{u['username'] or 'N/A'})")

    lines.append(f"\n💡 *To mark an email as invited*: `/mark_invited <email>`")
    lines.append(f"💡 *To mark ALL as invited*: `/bulk_mark_invited`")
    bot.send_message(message.chat.id, "\n".join(lines))


@bot.message_handler(commands=["mark_invited"])
def handle_mark_invited_command(message: types.Message):
    """Marks a specific user as INVITED by email or user_id."""
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Admin only.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "Usage: `/mark_invited youremail@gmail.com` or `/mark_invited <user_id>`")
        return

    identifier = args[1].strip()
    user = db.mark_user_as_invited(identifier)
    if not user:
        bot.reply_to(message, f"❌ No user found matching `{identifier}`.")
        return

    bot.reply_to(message, f"✅ User marked as *INVITED*:\nEmail: `{user.get('email')}`\nUser ID: `{user.get('user_id')}`")

    try:
        user_id = user["user_id"]
        lang = user.get("language") or "fr"
        msg = (
            "🎉 *مبروك! تم إرسال دعوتك الرسمية لـ Canva!* 🚀\n\n"
            f"تمت إضافة حسابك (`{user.get('email')}`) إلى فريق العمل في Canva.\n"
            "يرجى فتح بريدك الإلكتروني والضغط على قبول الدعوة لتفعيل الميزات فوراً."
            if lang == "ar" else
            "🎉 *BONNE NOUVELLE ! VOTRE INVITATION CANVA EST ENVOYÉE !* 🚀\n\n"
            f"Votre compte (`{user.get('email')}`) a été ajouté à notre équipe Canva.\n"
            "Veuillez vérifier votre boîte de réception pour accepter l'invitation."
        )
        bot.send_message(user_id, msg)
    except Exception as e:
        logger.warning(f"Could not notify user {user.get('user_id')} of invitation: {e}")


@bot.message_handler(commands=["bulk_mark_invited"])
def handle_bulk_mark_invited_command(message: types.Message):
    """Marks all pending invite users as INVITED."""
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Admin only.")
        return

    count = db.bulk_mark_all_pending_as_invited()
    bot.reply_to(message, f"✅ Successfully updated *{count} users* from PENDING_INVITE to *INVITED*.")


@bot.message_handler(commands=["rewards"])
def handle_rewards_command(message: types.Message):
    """Lists pending reward claims (users who referred 5 paying friends)."""
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Admin only.")
        return

    rewards = db.get_pending_rewards(limit=25)
    if not rewards:
        bot.reply_to(message, "✅ No pending rewards. All freebies delivered!")
        return

    lines = ["🎁 *PENDING REWARD CLAIMS (5 PAID INVITES)*:\n"]
    for i, r in enumerate(rewards, 1):
        uname = f"@{r['username']}" if r.get("username") else f"User {r['user_id']}"
        lines.append(
            f"{i}. Reward #{r['id']} — {uname} (ID: `{r['user_id']}`)\n"
            f"   Email: `{r.get('email') or 'N/A'}` | Paid Referrals: *{r.get('paid_referrals_count', 5)}*\n"
            f"   👉 Deliver: `/deliver_reward {r['id']} <message/freebie_link>`"
        )
    bot.send_message(message.chat.id, "\n".join(lines))


@bot.message_handler(commands=["deliver_reward"])
def handle_deliver_reward_command(message: types.Message):
    """Marks a reward as delivered and delivers message/link to user."""
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Admin only.")
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        bot.reply_to(message, "Usage: `/deliver_reward <reward_id> [optional message/freebie_details]`")
        return

    reward_id_str = args[1].strip()
    if not reward_id_str.isdigit():
        bot.reply_to(message, "Reward ID must be numeric.")
        return

    reward_id = int(reward_id_str)
    note = args[2] if len(args) > 2 else "Delivered by admin"

    delivered = db.mark_reward_delivered(reward_id, note=note)
    if not delivered:
        bot.reply_to(message, f"❌ Reward #{reward_id} not found or already delivered.")
        return

    user_id = delivered["user_id"]
    bot.reply_to(message, f"✅ Reward #{reward_id} marked as *DELIVERED* to user `{user_id}`.")

    try:
        lang = get_lang(user_id)
        msg = (
            f"🎁 *مبروك! لقد استلمت هديتك المجانية!* 🚀\n\n"
            f"شكراً لدعوتك 5 أعضاء مشتركين في Canva Algeria Hub.\n\n"
            f"📦 *تفاصيل الهدية / رابط التحميل*:\n{note}\n\n"
            f"واصل دعوة أصدقائك للحصول على المزيد من الهدايا!"
            if lang == "ar" else
            f"🎁 *FÉLICITATIONS ! VOTRE CADEAU GRATUIT EST ARRIVÉ !* 🚀\n\n"
            f"Merci d'avoir parrainé 5 membres actifs sur Canva Algeria Hub.\n\n"
            f"📦 *Détails du cadeau / Lien de téléchargement* :\n{note}\n\n"
            f"Continuez à inviter des amis pour débloquer votre prochain cadeau !"
        )
        bot.send_message(user_id, msg)
    except Exception as e:
        logger.warning(f"Could not notify user of reward delivery: {e}")


@bot.message_handler(commands=["reset_system"])
def handle_reset_system_command(message: types.Message):
    """Admin command to wipe all users, receipts, and rewards to start from 0."""
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Admin only.")
        return

    conn = db.get_connection()
    with conn:
        conn.execute("DELETE FROM rewards;")
        conn.execute("DELETE FROM used_receipts;")
        conn.execute("DELETE FROM users;")
        conn.execute("VACUUM;")
    conn.close()

    bot.reply_to(
        message,
        "🧹 *System Data Cleared Successfully!*\n"
        "All registered users, receipt records, and referral rewards have been wiped clean.\n"
        f"Capacity: `0/{settings.MAX_SEATS}` seats taken (`{settings.MAX_SEATS}` remaining)."
    )


def broadcast_message(text: str, target_status: Optional[str] = None, test_user_id: Optional[int] = None) -> dict:
    """Broadcasts a message to targeted users or a single test user."""
    if test_user_id:
        try:
            bot.send_message(test_user_id, f"🧪 *TEST BROADCAST PREVIEW*:\n\n{text}", parse_mode="Markdown")
            return {"total": 1, "sent": 1, "failed": 0}
        except Exception as e:
            logger.error(f"Failed test broadcast to {test_user_id}: {e}")
            return {"total": 1, "sent": 0, "failed": 1}

    users = db.get_all_users(status_filter=target_status if target_status and target_status != "ALL" else None, limit=2000)
    sent_count = 0
    fail_count = 0
    for u in users:
        try:
            personalized = text.replace("{first_name}", u.get("first_name") or u.get("username") or "Valued Member")
            personalized = personalized.replace("{user_id}", str(u["user_id"]))
            bot.send_message(u["user_id"], f"📢 *ANNOUNCEMENT*:\n\n{personalized}", parse_mode="Markdown")
            sent_count += 1
        except Exception:
            fail_count += 1
            
    return {"total": len(users), "sent": sent_count, "failed": fail_count}


@bot.message_handler(commands=["broadcast"])
def handle_broadcast_command(message: types.Message):
    """Broadcasts a message to all registered users."""
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Admin only.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "Usage: `/broadcast Your message here`")
        return

    broadcast_text = args[1]
    users = db.get_all_users(limit=2000)
    sent_count = 0
    fail_count = 0

    status_msg = bot.reply_to(message, f"📢 Broadcasting to {len(users)} users...")

    for u in users:
        try:
            bot.send_message(u["user_id"], f"📢 *ANNOUNCEMENT*:\n\n{broadcast_text}")
            sent_count += 1
        except Exception:
            fail_count += 1

    bot.edit_message_text(
        f"✅ Broadcast finished!\nSent: {sent_count}\nFailed/Blocked: {fail_count}",
        chat_id=message.chat.id,
        message_id=status_msg.message_id
    )


# ---------------------------------------------------------------------------
# Admin Callbacks
# ---------------------------------------------------------------------------

@bot.callback_query_handler(func=lambda call: call.data.startswith("cb_admin_"))
def handle_admin_callbacks(call: types.CallbackQuery):
    """Processes admin panel callbacks."""
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Access denied.", show_alert=True)
        return

    data = call.data
    bot.answer_callback_query(call.id)

    if data == "cb_admin_export":
        csv_content = db.export_canva_csv()
        if not csv_content.strip():
            bot.send_message(call.message.chat.id, "ℹ️ No emails collected yet.")
            return
        bio = io.BytesIO(csv_content.encode("utf-8"))
        bio.name = "canva_invites_batch.csv"
        bot.send_document(
            call.message.chat.id,
            document=bio,
            caption="📄 *Canva Invites Batch CSV*"
        )

    elif data == "cb_admin_pending":
        pending = db.get_pending_invite_users(limit=20)
        if not pending:
            bot.send_message(call.message.chat.id, "✅ No pending invites at the moment.")
            return
        lines = ["📋 *PENDING CANVA INVITATION LIST*:\n"]
        for i, u in enumerate(pending, 1):
            lines.append(f"{i}. `{u['email']}`")
        bot.send_message(call.message.chat.id, "\n".join(lines))

    elif data == "cb_admin_rewards":
        rewards = db.get_pending_rewards(limit=15)
        if not rewards:
            bot.send_message(call.message.chat.id, "✅ No pending rewards. All freebies delivered!")
            return
        lines = ["🎁 *PENDING REWARD CLAIMS (5 PAID INVITES)*:\n"]
        for i, r in enumerate(rewards, 1):
            uname = f"@{r['username']}" if r.get('username') else f"User {r['user_id']}"
            lines.append(f"{i}. Reward #{r['id']} — {uname} (Paid: {r['paid_referrals_count']})\n👉 `/deliver_reward {r['id']} <freebie_info>`")
        bot.send_message(call.message.chat.id, "\n".join(lines))

    elif data == "cb_admin_bulk_mark":
        count = db.bulk_mark_all_pending_as_invited()
        bot.send_message(call.message.chat.id, f"✅ Marked {count} users as INVITED.")

    elif data == "cb_admin_refresh":
        stats = db.get_system_stats()
        text = (
            f"⚙️ *Canva Admin Control Panel*\n\n"
            f"👥 *Total Registered Users*: `{stats['total_users']}`\n"
            f"💳 *Paid Unlocks (500 DZD)*: `{stats['paid_unlocks']}` ({stats['total_revenue_dzd']:,.0f} DZD)\n"
            f"🤝 *Paid Referrals Generated*: `{stats.get('total_paid_referrals', 0)}`\n"
            f"🕒 *Pending Invites*: `{stats['pending_invites']}`\n"
            f"🎁 *Pending Freebie Claims*: `{stats.get('pending_rewards', 0)}`\n"
            f"✅ *Already Invited*: `{stats['invited_users']}`\n"
            f"🪑 *Total Seats Claimed*: `{stats['claimed_seats']}/{settings.MAX_SEATS}`\n"
            f"🟢 *Remaining Seats*: `{stats['remaining_seats']}`"
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📥 Export CSV", callback_data="cb_admin_export"),
            types.InlineKeyboardButton("📋 Pending List", callback_data="cb_admin_pending"),
            types.InlineKeyboardButton("🎁 Rewards", callback_data="cb_admin_rewards"),
            types.InlineKeyboardButton("⚡ Bulk Mark Invited", callback_data="cb_admin_bulk_mark"),
            types.InlineKeyboardButton("🔄 Refresh", callback_data="cb_admin_refresh")
        )
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        except Exception:
            pass
