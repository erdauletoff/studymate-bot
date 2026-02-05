from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.keyboards import student_menu, cancel_menu, mentor_menu
from bot.texts import t
from bot.db import (
    is_mentor, get_student_mentor, get_student_by_telegram_id, create_question,
    mark_question_answered, get_user_language, get_question_by_id, add_question_reply,
    get_mentor_by_telegram_id
)

router = Router()


class QuestionStates(StatesGroup):
    waiting_question = State()
    waiting_reply = State()


@router.message(F.text.in_(["❓ Задать вопрос", "❓ Soraw beriw", "❓ Ask Question"]))
async def ask_question_start(message: Message, state: FSMContext):
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
    if await is_mentor(message.from_user.id):
        return
    lang = await get_user_language(message.from_user.id)
    
    if message.text in ["❌ Отмена", "❌ Biykar etiw", "❌ Cancel"]:
        await state.clear()
        await message.answer(t("cancelled", lang), reply_markup=student_menu(lang))
        return

    mentor = await get_student_mentor(message.from_user.id)

    if not mentor:
        await state.clear()
        await message.answer(t("error", lang))
        return

    # Get student for tracking in admin panel
    student = await get_student_by_telegram_id(message.from_user.id)

    # Create question with message_id and telegram_id for reply functionality
    question = await create_question(
        mentor,
        message.text,
        student,
        message.message_id,
        message.from_user.id  # Always save telegram_id for replies
    )

    # Get question ID explicitly
    question_id = question.id
    print(f"DEBUG: Created question with ID: {question_id}")

    # Get mentor's language for the notification
    mentor_lang = await get_user_language(mentor.telegram_id)

    # IMPORTANT: Store question data in callback_data as JSON to avoid DB query issues
    # Format: reply_{question_id}_{student_telegram_id}_{text_preview}
    callback_data = f"reply_{question_id}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_reply", mentor_lang), callback_data=callback_data)]
    ])

    await bot.send_message(
        mentor.telegram_id,
        t("anonymous_question", mentor_lang, text=message.text),
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await state.clear()
    await message.answer(t("question_sent", lang), reply_markup=student_menu(lang))


@router.callback_query(F.data.startswith("reply_"))
async def question_reply_start(callback: CallbackQuery, state: FSMContext):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)

    question_id = int(callback.data.replace("reply_", ""))
    print(f"DEBUG: Processing reply callback for question ID: {question_id}")

    # Get question from the callback message text instead of DB
    # Extract question text from the notification message
    message_text = callback.message.text or callback.message.caption or ""

    # Parse question text from "❓ Анонимный вопрос:\n\n{text}"
    question_text = message_text.split("\n\n", 1)[-1] if "\n\n" in message_text else message_text

    # Save to FSM - no DB query needed!
    await state.set_state(QuestionStates.waiting_reply)
    await state.update_data(
        question_id=question_id,
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
    if not await is_mentor(message.from_user.id):
        return
    lang = await get_user_language(message.from_user.id)

    # Check for cancel
    if message.text in ["❌ Отмена", "❌ Biykar etiw", "❌ Cancel"]:
        await state.clear()
        mentor = await get_mentor_by_telegram_id(message.from_user.id)
        await message.answer(t("cancelled", lang), reply_markup=mentor_menu(lang))
        return

    # Get question_id from FSM
    data = await state.get_data()
    question_id = data.get("question_id")

    if not question_id:
        await state.clear()
        await message.answer(t("error", lang))
        return

    # Add reply to question (works even without fetching the object)
    print(f"DEBUG: Adding reply to question {question_id}")
    success = await add_question_reply(question_id, message.text)
    print(f"DEBUG: add_question_reply returned: {success}")

    if not success:
        await state.clear()
        await message.answer(t("question_not_found", lang))
        return

    # Get question to send notification to student
    # By this time (after user typed reply), the question should be in DB
    import asyncio
    question = None
    for attempt in range(3):
        question = await get_question_by_id(question_id)
        if question:
            break
        if attempt < 2:
            await asyncio.sleep(0.5)  # Wait longer since this isn't time-critical

    # DEBUG: Log question retrieval result
    if not question:
        print(f"ERROR: Question {question_id} not found after retry attempts")
    else:
        print(f"DEBUG: Question {question_id} found. Student attached: {question.student is not None}, telegram_id: {question.student_telegram_id}")

    # Send reply to student using telegram_id (works even if Student object is not linked)
    if question and question.student_telegram_id:
        student_lang = await get_user_language(question.student_telegram_id)
        try:
            # Use reply_to_message_id if we have the original message
            reply_params = {
                "chat_id": question.student_telegram_id,
                "text": t("mentor_reply", student_lang, text=message.text),
                "parse_mode": "HTML"
            }

            if question.message_id:
                # Reply to original question message
                reply_params["reply_to_message_id"] = question.message_id
                print(f"DEBUG: Replying to message_id {question.message_id} in chat {question.student_telegram_id}")

            await bot.send_message(**reply_params)
            print(f"DEBUG: Successfully sent reply to student {question.student_telegram_id}")
        except Exception as e:
            # Student may have blocked the bot or deleted their account
            print(f"ERROR: Failed to send reply to student: {e}")
            pass

    await state.clear()
    mentor = await get_mentor_by_telegram_id(message.from_user.id)
    await message.answer(t("reply_sent", lang), reply_markup=mentor_menu(lang))


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
