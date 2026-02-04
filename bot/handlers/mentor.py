from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.keyboards import (
    mentor_menu, cancel_menu, materials_submenu,
    topics_for_upload, topics_for_manage, files_for_manage,
    topics_for_view
)
from bot.texts import t
from bot.db import (
    is_mentor, get_mentor_by_telegram_id,
    get_topics_by_mentor, get_topic_by_id, create_topic, delete_topic,
    get_materials_by_topic, get_material_by_id, add_material, delete_material,
    get_unanswered_questions, get_materials_count_by_topics,
    get_mentor_stats, get_user_language, get_students_by_mentor
)

router = Router()


# ==================== MATERIALS SUBMENU ====================
# Note: Materials button ("📚 Материалы") is handled in student.py for both mentors and students
# Mentors get the materials submenu, students get the materials list

@router.message(F.text.in_(["⬅️ Назад", "⬅️ Artqa", "⬅️ Back"]))
async def back_to_main_menu(message: Message, state: FSMContext):
    if not await is_mentor(message.from_user.id):
        return
    await state.clear()
    lang = await get_user_language(message.from_user.id)
    mentor = await get_mentor_by_telegram_id(message.from_user.id)
    await message.answer(
        t("welcome_mentor", lang, name=mentor.name),
        reply_markup=mentor_menu(lang),
        parse_mode="HTML"
    )


class UploadStates(StatesGroup):
    waiting_topic_name = State()
    waiting_file = State()
    waiting_file_title = State()


# ==================== UPLOAD MATERIAL ====================

@router.message(F.text.in_(["📤 Загрузить", "📤 Júklew", "📤 Upload"]))
async def upload_start(message: Message, state: FSMContext):
    if not await is_mentor(message.from_user.id):
        return
    await state.clear()
    lang = await get_user_language(message.from_user.id)
    mentor = await get_mentor_by_telegram_id(message.from_user.id)
    topics = await get_topics_by_mentor(mentor)
    keyboard = topics_for_upload(topics, lang)
    await message.answer(t("choose_topic_upload", lang), reply_markup=keyboard)


@router.callback_query(F.data == "create_topic")
async def create_topic_start(callback: CallbackQuery, state: FSMContext):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)
    await state.set_state(UploadStates.waiting_topic_name)
    await callback.message.edit_text(t("enter_topic_name", lang))
    await callback.answer()


@router.message(UploadStates.waiting_topic_name)
async def receive_topic_name(message: Message, state: FSMContext):
    if not await is_mentor(message.from_user.id):
        return
    lang = await get_user_language(message.from_user.id)
    mentor = await get_mentor_by_telegram_id(message.from_user.id)
    topic = await create_topic(mentor, message.text.strip())

    await state.clear()
    await message.answer(
        t("topic_created", lang, name=topic.name),
        reply_markup=materials_submenu(lang)
    )


@router.callback_query(F.data.startswith("upload_to_"))
async def select_topic_for_upload(callback: CallbackQuery, state: FSMContext):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)
    topic_id = int(callback.data.replace("upload_to_", ""))
    topic = await get_topic_by_id(topic_id)

    await state.set_state(UploadStates.waiting_file)
    await state.update_data(topic_id=topic_id, topic_name=topic.name)

    await callback.message.edit_text(t("send_file", lang, name=topic.name))
    await callback.answer()


@router.message(UploadStates.waiting_file, F.document)
async def receive_document(message: Message, state: FSMContext):
    if not await is_mentor(message.from_user.id):
        return
    lang = await get_user_language(message.from_user.id)
    await state.update_data(file_id=message.document.file_id, file_name=message.document.file_name)
    await state.set_state(UploadStates.waiting_file_title)
    await message.answer(
        t("file_received", lang, name=message.document.file_name),
        reply_markup=cancel_menu(lang)
    )


@router.message(UploadStates.waiting_file, F.photo)
async def receive_photo(message: Message, state: FSMContext):
    if not await is_mentor(message.from_user.id):
        return
    lang = await get_user_language(message.from_user.id)
    await state.update_data(file_id=message.photo[-1].file_id, file_name="photo.jpg")
    await state.set_state(UploadStates.waiting_file_title)
    await message.answer(t("photo_received", lang), reply_markup=cancel_menu(lang))


@router.message(UploadStates.waiting_file_title)
async def receive_file_title(message: Message, state: FSMContext):
    if not await is_mentor(message.from_user.id):
        return
    lang = await get_user_language(message.from_user.id)
    data = await state.get_data()
    topic = await get_topic_by_id(data["topic_id"])

    await add_material(topic, message.text.strip(), data["file_id"], data["file_name"])

    await state.clear()
    await message.answer(
        t("material_added", lang, topic=topic.name, title=message.text.strip()),
        reply_markup=materials_submenu(lang)
    )


# ==================== MANAGE MATERIALS ====================

@router.message(F.text.in_(["📂 Управление", "📂 Basqarıw", "📂 Manage"]))
async def manage_start(message: Message, state: FSMContext):
    if not await is_mentor(message.from_user.id):
        return
    await state.clear()
    lang = await get_user_language(message.from_user.id)
    mentor = await get_mentor_by_telegram_id(message.from_user.id)
    topics = await get_topics_by_mentor(mentor)

    if not topics:
        await message.answer(t("no_topics", lang))
        return

    materials_count = await get_materials_count_by_topics(topics)
    keyboard = topics_for_manage(topics, materials_count, lang, page=0)
    await message.answer(t("select_topic_manage", lang), reply_markup=keyboard)


@router.callback_query(F.data.startswith("managepage_"))
async def manage_page(callback: CallbackQuery):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)
    page = int(callback.data.replace("managepage_", ""))
    mentor = await get_mentor_by_telegram_id(callback.from_user.id)
    topics = await get_topics_by_mentor(mentor)
    materials_count = await get_materials_count_by_topics(topics)
    keyboard = topics_for_manage(topics, materials_count, lang, page=page)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("manage_"))
async def manage_topic(callback: CallbackQuery):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)
    topic_id = int(callback.data.replace("manage_", ""))
    topic = await get_topic_by_id(topic_id)
    materials = await get_materials_by_topic(topic)

    keyboard = files_for_manage(materials, topic_id, lang)
    await callback.message.edit_text(t("tap_to_delete", lang, name=topic.name), reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


# ==================== DELETE FILE WITH CONFIRMATION ====================

@router.callback_query(F.data.startswith("delete_") & ~F.data.startswith("deletetopic_"))
async def confirm_delete_file(callback: CallbackQuery):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)
    parts = callback.data.split("_")
    topic_id = int(parts[1])
    material_id = int(parts[2])
    
    material = await get_material_by_id(material_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t("btn_yes_delete", lang), callback_data=f"confirmdelete_{topic_id}_{material_id}"),
            InlineKeyboardButton(text=t("btn_no_cancel", lang), callback_data=f"manage_{topic_id}")
        ]
    ])
    
    await callback.message.edit_text(
        t("confirm_delete_file", lang, title=material.title),
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirmdelete_"))
async def delete_file_confirmed(callback: CallbackQuery):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)
    parts = callback.data.split("_")
    topic_id = int(parts[1])
    material_id = int(parts[2])

    await delete_material(material_id)
    await callback.answer(t("file_deleted", lang))

    topic = await get_topic_by_id(topic_id)
    materials = await get_materials_by_topic(topic)
    keyboard = files_for_manage(materials, topic_id, lang)
    await callback.message.edit_text(t("tap_to_delete", lang, name=topic.name), reply_markup=keyboard, parse_mode="HTML")


# ==================== DELETE TOPIC WITH CONFIRMATION ====================

@router.callback_query(F.data.startswith("deletetopic_") & ~F.data.startswith("deletetopicconfirm_"))
async def confirm_delete_topic(callback: CallbackQuery):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)
    topic_id = int(callback.data.replace("deletetopic_", ""))
    topic = await get_topic_by_id(topic_id)
    materials = await get_materials_by_topic(topic)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t("btn_yes_delete_all", lang), callback_data=f"deletetopicconfirm_{topic_id}"),
            InlineKeyboardButton(text=t("btn_no_cancel", lang), callback_data=f"manage_{topic_id}")
        ]
    ])
    
    await callback.message.edit_text(
        t("confirm_delete_topic", lang, name=topic.name, count=len(materials)),
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("deletetopicconfirm_"))
async def delete_topic_confirmed(callback: CallbackQuery):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)
    topic_id = int(callback.data.replace("deletetopicconfirm_", ""))
    topic_name = await delete_topic(topic_id)

    await callback.answer(t("topic_deleted", lang, name=topic_name))

    mentor = await get_mentor_by_telegram_id(callback.from_user.id)
    topics = await get_topics_by_mentor(mentor)

    if not topics:
        await callback.message.edit_text(t("no_topics_left", lang))
        return

    materials_count = await get_materials_count_by_topics(topics)
    keyboard = topics_for_manage(topics, materials_count, lang, page=0)
    await callback.message.edit_text(t("select_topic_manage", lang), reply_markup=keyboard)


@router.callback_query(F.data == "back_manage")
async def back_to_manage(callback: CallbackQuery):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)
    mentor = await get_mentor_by_telegram_id(callback.from_user.id)
    topics = await get_topics_by_mentor(mentor)

    if not topics:
        await callback.message.edit_text(t("no_topics", lang))
        return

    materials_count = await get_materials_count_by_topics(topics)
    keyboard = topics_for_manage(topics, materials_count, lang, page=0)
    await callback.message.edit_text(t("select_topic_manage", lang), reply_markup=keyboard)
    await callback.answer()


# ==================== STATISTICS ====================

@router.message(F.text.in_(["📊 Статистика", "📊 Statistika", "📊 Statistics"]))
async def show_statistics(message: Message, state: FSMContext):
    if not await is_mentor(message.from_user.id):
        return
    await state.clear()
    lang = await get_user_language(message.from_user.id)
    
    mentor = await get_mentor_by_telegram_id(message.from_user.id)
    stats = await get_mentor_stats(mentor)
    
    text = t("statistics", lang)
    text += t("stats_students", lang, count=stats['students'])
    text += t("stats_topics", lang, count=stats['topics'])
    text += t("stats_materials", lang, count=stats['materials'])
    text += t("stats_questions", lang, total=stats['questions_total'])
    
    if stats['questions_unanswered'] > 0:
        text += t("stats_unanswered", lang, count=stats['questions_unanswered'])
    text += "\n\n"
    
    text += t("stats_active_today", lang, count=stats['active_today'])
    text += t("stats_active_week", lang, count=stats['active_week'])
    
    if stats['popular']:
        text += t("stats_popular", lang)
        for i, (title, count) in enumerate(stats['popular'], 1):
            text += t("stats_popular_item", lang, num=i, title=title, count=count)
    
    await message.answer(text, parse_mode="HTML")


# ==================== QUESTIONS ====================

@router.message(F.text.in_(["❓ Вопросы", "❓ Sorawlar", "❓ Questions"]))
async def view_questions(message: Message, state: FSMContext):
    if not await is_mentor(message.from_user.id):
        return
    await state.clear()
    lang = await get_user_language(message.from_user.id)
    
    mentor = await get_mentor_by_telegram_id(message.from_user.id)
    questions = await get_unanswered_questions(mentor)

    if not questions:
        await message.answer(t("no_questions", lang))
        return

    text = t("unanswered_questions", lang, count=len(questions))
    for i, q in enumerate(questions[:10], 1):
        text += f"{i}. {q.text[:100]}{'...' if len(q.text) > 100 else ''}\n\n"

    if len(questions) > 10:
        text += t("and_more", lang, count=len(questions) - 10)

    await message.answer(text)


# ==================== MESSAGE STUDENTS ====================

class MessageStates(StatesGroup):
    waiting_message = State()


@router.message(F.text.in_(["✉️ Написать ученику", "✉️ Oqıwshıǵa jazıw", "✉️ Message Student"]))
async def message_students_start(message: Message, state: FSMContext):
    if not await is_mentor(message.from_user.id):
        return
    await state.clear()
    lang = await get_user_language(message.from_user.id)

    mentor = await get_mentor_by_telegram_id(message.from_user.id)
    students = await get_students_by_mentor(mentor)

    if not students:
        await message.answer(t("no_students", lang))
        return

    from bot.keyboards import students_for_message
    keyboard = students_for_message(students, lang, page=0)
    await message.answer(t("select_student", lang), reply_markup=keyboard)


@router.callback_query(F.data.startswith("msgpage_"))
async def message_students_page(callback: CallbackQuery):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)
    page = int(callback.data.replace("msgpage_", ""))

    mentor = await get_mentor_by_telegram_id(callback.from_user.id)
    students = await get_students_by_mentor(mentor)

    from bot.keyboards import students_for_message
    keyboard = students_for_message(students, lang, page=page)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("msgstudent_"))
async def select_student_for_message(callback: CallbackQuery, state: FSMContext):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)

    student_id = int(callback.data.replace("msgstudent_", ""))

    # Get student from DB
    from bot.db import get_student_by_id
    student = await get_student_by_id(student_id)

    if not student:
        await callback.answer(t("student_not_found", lang))
        return

    # Save student_id to FSM
    await state.set_state(MessageStates.waiting_message)
    await state.update_data(student_id=student_id)

    # Show student name
    student_name = student.full_name or f"{student.first_name} {student.last_name}".strip() or f"ID: {student.telegram_id}"

    # Ask mentor to write message
    await callback.message.answer(
        t("write_message_to_student", lang, name=student_name),
        parse_mode="HTML",
        reply_markup=cancel_menu(lang)
    )
    await callback.answer()


@router.message(MessageStates.waiting_message)
async def receive_message_to_student(message: Message, state: FSMContext, bot: Bot):
    if not await is_mentor(message.from_user.id):
        return
    lang = await get_user_language(message.from_user.id)

    # Check for cancel
    if message.text in ["❌ Отмена", "❌ Biykar etiw", "❌ Cancel"]:
        await state.clear()
        mentor = await get_mentor_by_telegram_id(message.from_user.id)
        await message.answer(t("cancelled", lang), reply_markup=mentor_menu(lang))
        return

    # Get student_id from FSM
    data = await state.get_data()
    student_id = data.get("student_id")

    if not student_id:
        await state.clear()
        await message.answer(t("error", lang))
        return

    # Get student from DB
    from bot.db import get_student_by_id
    student = await get_student_by_id(student_id)

    if not student:
        await state.clear()
        await message.answer(t("student_not_found", lang))
        return

    # Send message to student
    student_lang = await get_user_language(student.telegram_id)
    try:
        await bot.send_message(
            student.telegram_id,
            t("mentor_message", student_lang, text=message.text),
            parse_mode="HTML"
        )

        # Confirm to mentor
        student_name = student.full_name or f"{student.first_name} {student.last_name}".strip() or f"ID: {student.telegram_id}"
        await state.clear()
        await message.answer(
            t("message_sent_to_student", lang, name=student_name),
            reply_markup=mentor_menu(lang)
        )
    except Exception as e:
        # Student may have blocked the bot or deleted their account
        await state.clear()
        await message.answer(
            t("error", lang),
            reply_markup=mentor_menu(lang)
        )
