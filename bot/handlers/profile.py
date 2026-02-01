import re
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.keyboards import student_menu, profile_setup_keyboard, cancel_menu
from bot.texts import t
from bot.db import (
    get_user_language, get_student_by_telegram_id,
    update_student_full_name, is_student_profile_completed,
    get_student_mentor, get_student_quiz_stats
)

router = Router()


class ProfileStates(StatesGroup):
    waiting_full_name = State()
    editing_full_name = State()


def validate_full_name(name: str) -> tuple[bool, str]:
    """
    Validate full name input.
    Returns: (is_valid, error_key)
    """
    name = name.strip()

    # Check length
    if len(name) < 3:
        return False, "profile_name_too_short"
    if len(name) > 200:
        return False, "profile_name_too_long"

    # Allow Cyrillic, Latin, spaces, hyphens, apostrophes
    # Pattern: letters from any alphabet, spaces, hyphens, apostrophes
    if not re.match(r"^[\w\s\-']+$", name, re.UNICODE):
        return False, "profile_name_invalid"

    return True, ""


def normalize_full_name(name: str) -> str:
    """Normalize full name: remove extra spaces, capitalize words"""
    # Remove extra spaces
    name = re.sub(r'\s+', ' ', name.strip())
    # Capitalize each word
    return ' '.join(word.capitalize() for word in name.split())


# ==================== PROFILE SETUP (FIRST TIME) ====================

async def start_profile_setup(message: Message, state: FSMContext, lang: str):
    """Start profile setup for new users"""
    await state.set_state(ProfileStates.waiting_full_name)

    # Get Telegram name for the button
    telegram_name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
    await state.update_data(telegram_name=telegram_name)

    await message.answer(
        t("profile_setup_welcome", lang),
        reply_markup=profile_setup_keyboard(lang, telegram_name if telegram_name else None),
        parse_mode="HTML"
    )


@router.message(ProfileStates.waiting_full_name, F.text.in_(["✅ Использовать имя из Telegram", "✅ Telegram atın paydalanıw", "✅ Use Telegram name"]))
async def use_telegram_name(message: Message, state: FSMContext):
    """Use Telegram name as full name"""
    lang = await get_user_language(message.from_user.id)
    data = await state.get_data()
    telegram_name = data.get("telegram_name", "")

    if not telegram_name:
        await message.answer(t("profile_name_too_short", lang))
        return

    # Normalize and save
    full_name = normalize_full_name(telegram_name)
    await update_student_full_name(message.from_user.id, full_name)

    await state.clear()
    await message.answer(
        t("profile_completed", lang, name=full_name),
        reply_markup=student_menu(lang),
        parse_mode="HTML"
    )


@router.message(ProfileStates.waiting_full_name)
async def receive_full_name_setup(message: Message, state: FSMContext):
    """Receive and validate full name during setup"""
    lang = await get_user_language(message.from_user.id)

    # Check for cancel
    if message.text in [t("btn_cancel", "ru"), t("btn_cancel", "qq"), t("btn_cancel", "en")]:
        await state.clear()
        await message.answer(t("cancelled", lang), reply_markup=student_menu(lang))
        return

    # Validate
    is_valid, error_key = validate_full_name(message.text)
    if not is_valid:
        await message.answer(t(error_key, lang))
        return

    # Normalize and save
    full_name = normalize_full_name(message.text)
    await update_student_full_name(message.from_user.id, full_name)

    await state.clear()
    await message.answer(
        t("profile_completed", lang, name=full_name),
        reply_markup=student_menu(lang),
        parse_mode="HTML"
    )


# ==================== PROFILE VIEW & EDIT ====================

@router.message(F.text.in_(["👤 Профиль", "👤 Profil", "👤 Profile"]))
async def view_profile(message: Message, state: FSMContext):
    """View student profile"""
    await state.clear()
    lang = await get_user_language(message.from_user.id)
    student = await get_student_by_telegram_id(message.from_user.id)

    if not student:
        await message.answer(t("error", lang))
        return

    # Check if profile is completed
    profile_completed = await is_student_profile_completed(message.from_user.id)

    if not profile_completed:
        # Start profile setup if not completed
        await start_profile_setup(message, state, lang)
        return

    # Get mentor info
    mentor = await get_student_mentor(message.from_user.id)
    mentor_name = mentor.name if mentor else t("profile_not_set", lang)

    # Format data
    full_name = student.full_name or t("profile_not_set", lang)
    telegram_username = f"@{student.username}" if student.username else t("profile_not_set", lang)
    joined_date = student.joined_at.strftime("%d.%m.%Y")

    language_names = {"ru": "Русский", "qq": "Qaraqalpaq", "en": "English"}
    language = language_names.get(student.language, student.language)

    # Get quiz statistics
    stats = await get_student_quiz_stats(message.from_user.id)

    # Format streak info
    current_streak = student.current_streak
    longest_streak = student.longest_streak
    streak_emoji = "🔥" if current_streak > 0 else "💤"

    # Show profile
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_edit_profile", lang), callback_data="edit_profile")]
    ])

    await message.answer(
        t("profile_view", lang,
          name=full_name,
          telegram=telegram_username,
          joined=joined_date,
          language=language,
          mentor=mentor_name,
          total_quizzes=stats['total_quizzes'],
          total_ranked=stats['total_ranked'],
          total_practice=stats['total_practice'],
          avg_percentage=stats['avg_percentage'],
          best_score=stats['best_score'],
          best_total=stats['best_total'],
          best_percentage=stats['best_percentage'],
          streak_emoji=streak_emoji,
          current_streak=current_streak,
          longest_streak=longest_streak),
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "edit_profile")
async def start_edit_profile(callback: CallbackQuery, state: FSMContext):
    """Start editing profile"""
    lang = await get_user_language(callback.from_user.id)

    await state.set_state(ProfileStates.editing_full_name)
    await callback.message.answer(
        t("profile_edit_prompt", lang),
        reply_markup=cancel_menu(lang)
    )
    await callback.answer()


@router.message(ProfileStates.editing_full_name)
async def receive_full_name_edit(message: Message, state: FSMContext):
    """Receive and validate full name during editing"""
    lang = await get_user_language(message.from_user.id)

    # Check for cancel
    if message.text in [t("btn_cancel", "ru"), t("btn_cancel", "qq"), t("btn_cancel", "en")]:
        await state.clear()
        await message.answer(t("cancelled", lang), reply_markup=student_menu(lang))
        return

    # Validate
    is_valid, error_key = validate_full_name(message.text)
    if not is_valid:
        await message.answer(t(error_key, lang))
        return

    # Normalize and save
    full_name = normalize_full_name(message.text)
    await update_student_full_name(message.from_user.id, full_name)

    await state.clear()
    await message.answer(
        t("profile_updated", lang),
        reply_markup=student_menu(lang)
    )
