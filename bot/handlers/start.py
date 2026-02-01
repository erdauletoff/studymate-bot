from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from bot.keyboards import mentor_menu, student_menu, language_keyboard
from bot.texts import t
from bot.db import (
    is_mentor, get_mentor_by_telegram_id, get_all_mentors,
    get_or_create_student, assign_student_to_mentor,
    get_user_language, set_user_language
)

router = Router()


async def check_group_membership(bot: Bot, user_id: int, group_chat_id: int) -> bool:
    import logging
    logger = logging.getLogger('studymate')

    try:
        member = await bot.get_chat_member(chat_id=group_chat_id, user_id=user_id)
        is_member = member.status in ['member', 'administrator', 'creator']

        logger.info(
            f"Group membership check: user_id={user_id}, "
            f"group={group_chat_id}, status={member.status}, "
            f"is_member={is_member}"
        )

        return is_member
    except Exception as e:
        logger.error(
            f"Failed to check group membership: user_id={user_id}, "
            f"group={group_chat_id}, error={type(e).__name__}: {str(e)}"
        )
        return False


@router.message(Command("start"))
async def cmd_start(message: Message, bot: Bot, state: FSMContext, is_cancel=False):
    import logging
    logger = logging.getLogger('studymate')

    user_id = message.from_user.id
    username = message.from_user.username or 'no_username'
    await state.clear()

    lang = await get_user_language(user_id)

    logger.info(f"/start command from user_id={user_id}, username=@{username}")

    if await is_mentor(user_id):
        mentor = await get_mentor_by_telegram_id(user_id)
        logger.info(f"User {user_id} is a mentor: {mentor.name}")
        await message.answer(
            t("welcome_mentor", lang, name=mentor.name),
            reply_markup=mentor_menu(lang),
            parse_mode="HTML"
        )
        return

    mentors = await get_all_mentors()
    logger.info(f"Checking {len(mentors)} mentors for user {user_id}")

    for mentor in mentors:
        logger.info(
            f"Checking if user {user_id} is in mentor {mentor.name}'s group "
            f"(group_chat_id={mentor.group_chat_id})"
        )

        if await check_group_membership(bot, user_id, mentor.group_chat_id):
            logger.info(f"✅ User {user_id} found in group! Registering as student...")

            student = await get_or_create_student(
                telegram_id=user_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name or '',
                last_name=message.from_user.last_name or '',
                language=lang
            )
            await assign_student_to_mentor(student, mentor)

            logger.info(f"✅ Student {user_id} registered to mentor {mentor.name}")

            if is_cancel:
                await message.answer(
                    t("cancelled", lang),
                    reply_markup = student_menu(lang)
                )
            else:
                await message.answer(
                    t("welcome_student", lang, name=mentor.name),
                    reply_markup=student_menu(lang),
                    parse_mode="HTML"
                )
            return

    logger.warning(
        f"❌ Access denied for user {user_id} (@{username}) - "
        f"not found in any mentor's group"
    )
    await message.answer(t("access_denied", lang))


# ==================== LANGUAGE CHANGE ====================

@router.message(F.text.in_(["🌐 Язык", "🌐 Til", "🌐 Language"]))
async def change_language(message: Message, state: FSMContext):
    await state.clear()
    lang = await get_user_language(message.from_user.id)
    await message.answer(t("choose_language", lang), reply_markup=language_keyboard())


@router.callback_query(F.data.startswith("lang_"))
async def set_language(callback: CallbackQuery, bot: Bot):
    lang = callback.data.replace("lang_", "")
    await set_user_language(callback.from_user.id, lang)
    
    await callback.answer(t("language_changed", lang))
    
    # Show updated menu
    if await is_mentor(callback.from_user.id):
        mentor = await get_mentor_by_telegram_id(callback.from_user.id)
        await callback.message.answer(t("language_changed", lang), reply_markup=mentor_menu(lang))
    else:
        from bot.db import get_student_mentor
        mentor = await get_student_mentor(callback.from_user.id)
        if mentor:
            await callback.message.answer(t("language_changed", lang), reply_markup=student_menu(lang))


# ==================== CANCEL ====================

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, bot: Bot, state: FSMContext):
    await state.clear()
    await cmd_start(message, bot, state, True)


@router.message(F.text.in_(["❌ Отмена", "❌ Biykar etiw", "❌ Cancel"]))
async def btn_cancel(message: Message, bot: Bot, state: FSMContext):
    await state.clear()
    await cmd_start(message, bot, state, True)
