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

    question = await create_question(mentor, message.text, student)
    
    # Get mentor's language for the notification
    mentor_lang = await get_user_language(mentor.telegram_id)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_reply", mentor_lang), callback_data=f"reply_{question.id}")]
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
    question = await get_question_by_id(question_id)

    if not question:
        await callback.answer(t("question_not_found", lang))
        return

    # Save question_id to FSM for later use
    await state.set_state(QuestionStates.waiting_reply)
    await state.update_data(question_id=question_id)

    # Ask mentor to write reply
    await callback.message.answer(
        t("write_reply", lang, text=question.text),
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

    # Get question from DB
    question = await get_question_by_id(question_id)

    if not question:
        await state.clear()
        await message.answer(t("question_not_found", lang))
        return

    # Add reply to question
    await add_question_reply(question_id, message.text)

    # Send reply to student if they are linked
    if question.student:
        student_lang = await get_user_language(question.student.telegram_id)
        try:
            await bot.send_message(
                question.student.telegram_id,
                t("mentor_reply", student_lang, text=message.text),
                parse_mode="HTML"
            )
        except Exception:
            # Student may have blocked the bot or deleted their account
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
