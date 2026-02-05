from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.keyboards import student_menu, cancel_menu, mentor_menu
from bot.texts import t
from bot.db import (
    is_mentor, get_student_mentor, get_student_by_telegram_id, create_question,
    mark_question_answered, get_user_language, add_question_reply,
    get_mentor_by_telegram_id
)

router = Router()


class QuestionStates(StatesGroup):
    waiting_question = State()
    waiting_reply = State()


# ==================== STUDENT: ASK QUESTION ====================

@router.message(F.text.in_(["❓ Задать вопрос", "❓ Soraw beriw", "❓ Ask Question"]))
async def ask_question_start(message: Message, state: FSMContext):
    """Student starts asking a question"""
    if await is_mentor(message.from_user.id):
        return
    await state.clear()
    lang = await get_user_language(message.from_user.id)

    mentor = await get_student_mentor(message.from_user.id)
    if not mentor:
        await message.answer(t("not_assigned", lang))
        return

    await state.set_state(QuestionStates.waiting_question)
    await message.answer(t("write_question", lang), reply_markup=cancel_menu(lang))


@router.message(QuestionStates.waiting_question)
async def receive_question(message: Message, state: FSMContext, bot: Bot):
    """Student sends their question"""
    if await is_mentor(message.from_user.id):
        return
    lang = await get_user_language(message.from_user.id)

    # Handle cancel
    if message.text in ["❌ Отмена", "❌ Biykar etiw", "❌ Cancel"]:
        await state.clear()
        await message.answer(t("cancelled", lang), reply_markup=student_menu(lang))
        return

    mentor = await get_student_mentor(message.from_user.id)
    if not mentor:
        await state.clear()
        await message.answer(t("error", lang))
        return

    student_telegram_id = message.from_user.id
    student = await get_student_by_telegram_id(student_telegram_id)

    # Save question to DB (for admin panel tracking)
    question = await create_question(
        mentor=mentor,
        text=message.text,
        student=student,
        message_id=message.message_id,
        student_telegram_id=student_telegram_id
    )
    question_id = question.id
    print(f"[QUESTION] Created #{question_id} from student {student_telegram_id} to mentor {mentor.telegram_id}")

    # Get mentor's language
    mentor_lang = await get_user_language(mentor.telegram_id)

    # CRITICAL: Store student_telegram_id in callback_data!
    # This avoids ALL database query issues when replying
    callback_data = f"reply_{question_id}_{student_telegram_id}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_reply", mentor_lang), callback_data=callback_data)]
    ])

    # Send question to mentor
    await bot.send_message(
        mentor.telegram_id,
        t("anonymous_question", mentor_lang, text=message.text),
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await state.clear()
    await message.answer(t("question_sent", lang), reply_markup=student_menu(lang))


# ==================== MENTOR: REPLY TO QUESTION ====================

@router.callback_query(F.data.startswith("reply_"))
async def question_reply_start(callback: CallbackQuery, state: FSMContext):
    """Mentor clicks 'Reply' button"""
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)

    # Parse callback_data: "reply_{question_id}_{student_telegram_id}"
    parts = callback.data.split("_")

    if len(parts) >= 3:
        # New format: reply_123_456789
        question_id = int(parts[1])
        student_telegram_id = int(parts[2])
    else:
        # Old format: reply_123 (fallback, may not work for old messages)
        question_id = int(parts[1])
        student_telegram_id = None
        print(f"[QUESTION] Warning: Old callback format for question #{question_id}, student_telegram_id not available")

    print(f"[QUESTION] Mentor {callback.from_user.id} starting reply to #{question_id}, student: {student_telegram_id}")

    # Extract question text from the message (no DB query needed)
    message_text = callback.message.text or callback.message.caption or ""
    question_text = message_text.split("\n\n", 1)[-1] if "\n\n" in message_text else message_text

    # Save ALL data to FSM - NO database queries needed for reply!
    await state.set_state(QuestionStates.waiting_reply)
    await state.update_data(
        question_id=question_id,
        student_telegram_id=student_telegram_id,
        question_text=question_text
    )

    # Ask mentor to write reply
    await callback.message.answer(
        t("write_reply", lang, text=question_text),
        parse_mode="HTML",
        reply_markup=cancel_menu(lang)
    )
    await callback.answer()


@router.message(QuestionStates.waiting_reply)
async def receive_reply(message: Message, state: FSMContext, bot: Bot):
    """Mentor sends their reply"""
    if not await is_mentor(message.from_user.id):
        return
    lang = await get_user_language(message.from_user.id)

    # Handle cancel
    if message.text in ["❌ Отмена", "❌ Biykar etiw", "❌ Cancel"]:
        await state.clear()
        mentor = await get_mentor_by_telegram_id(message.from_user.id)
        await message.answer(t("cancelled", lang), reply_markup=mentor_menu(lang))
        return

    # Get ALL data from FSM (no DB queries!)
    data = await state.get_data()
    question_id = data.get("question_id")
    student_telegram_id = data.get("student_telegram_id")

    print(f"[QUESTION] Mentor {message.from_user.id} replying to #{question_id}, sending to student {student_telegram_id}")

    if not question_id:
        await state.clear()
        await message.answer(t("error", lang))
        return

    # Save reply to DB (async, for admin panel - don't wait for result)
    # This is fire-and-forget, the main goal is sending message to student
    try:
        await add_question_reply(question_id, message.text)
        print(f"[QUESTION] Reply saved to DB for question #{question_id}")
    except Exception as e:
        print(f"[QUESTION] Warning: Failed to save reply to DB: {e}")
        # Continue anyway - sending to student is more important!

    # MAIN GOAL: Send reply to student
    reply_sent = False
    if student_telegram_id:
        student_lang = await get_user_language(student_telegram_id)
        try:
            await bot.send_message(
                chat_id=student_telegram_id,
                text=t("mentor_reply", student_lang, text=message.text),
                parse_mode="HTML"
            )
            reply_sent = True
            print(f"[QUESTION] Reply sent to student {student_telegram_id}")
        except Exception as e:
            print(f"[QUESTION] ERROR: Failed to send reply to student {student_telegram_id}: {e}")
    else:
        print(f"[QUESTION] ERROR: No student_telegram_id for question #{question_id}")

    await state.clear()
    mentor = await get_mentor_by_telegram_id(message.from_user.id)

    if reply_sent:
        await message.answer(t("reply_sent", lang), reply_markup=mentor_menu(lang))
    else:
        await message.answer(t("reply_saved_not_sent", lang), reply_markup=mentor_menu(lang))


# ==================== BACKWARD COMPATIBILITY ====================

@router.callback_query(F.data.startswith("answered_"))
async def question_answered(callback: CallbackQuery):
    """Keep this for backward compatibility with old question messages"""
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)

    question_id = int(callback.data.replace("answered_", ""))
    await mark_question_answered(question_id)

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer(t("marked_answered", lang))
