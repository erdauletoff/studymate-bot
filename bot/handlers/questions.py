from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.keyboards import student_menu, cancel_menu
from bot.texts import t
from bot.db import (
    is_mentor, get_student_mentor, get_student_by_telegram_id, create_question,
    mark_question_answered, get_user_language
)

router = Router()


class QuestionStates(StatesGroup):
    waiting_question = State()


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
        [InlineKeyboardButton(text=t("btn_answered", mentor_lang), callback_data=f"answered_{question.id}")]
    ])

    await bot.send_message(
        mentor.telegram_id,
        t("anonymous_question", mentor_lang, text=message.text),
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await state.clear()
    await message.answer(t("question_sent", lang), reply_markup=student_menu(lang))


@router.callback_query(F.data.startswith("answered_"))
async def question_answered(callback: CallbackQuery):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)
    
    question_id = int(callback.data.replace("answered_", ""))
    await mark_question_answered(question_id)
    
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer(t("marked_answered", lang))
