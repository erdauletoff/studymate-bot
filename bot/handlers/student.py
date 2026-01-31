from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.keyboards import topics_for_view, files_for_view, materials_submenu
from bot.texts import t
from bot.db import (
    is_mentor, get_student_mentor, get_mentor_by_telegram_id,
    get_topics_by_mentor, get_topic_by_id, get_materials_by_topic,
    get_material_by_id, get_materials_count_by_topics,
    get_student_by_telegram_id, record_download, get_user_language
)

router = Router()


@router.message(F.text.in_(["📚 Материалы", "📚 Materiallar", "📚 Materials"]))
async def view_materials(message: Message, state: FSMContext):
    await state.clear()
    lang = await get_user_language(message.from_user.id)

    # For mentors, show materials management submenu
    if await is_mentor(message.from_user.id):
        await message.answer(
            t("materials_submenu_header", lang),
            reply_markup=materials_submenu(lang),
            parse_mode="HTML"
        )
        return

    # For students, show materials list
    mentor = await get_student_mentor(message.from_user.id)

    if not mentor:
        await message.answer(t("not_assigned", lang))
        return

    topics = await get_topics_by_mentor(mentor)

    if not topics:
        await message.answer(t("no_materials_yet", lang))
        return

    materials_count = await get_materials_count_by_topics(topics)
    keyboard = topics_for_view(topics, materials_count, lang, page=0)

    if not keyboard.inline_keyboard:
        await message.answer(t("no_materials_yet", lang))
        return

    await message.answer(t("lesson_materials", lang), reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("viewpage_"))
async def view_page(callback: CallbackQuery):
    lang = await get_user_language(callback.from_user.id)
    page = int(callback.data.replace("viewpage_", ""))
    
    if await is_mentor(callback.from_user.id):
        mentor = await get_mentor_by_telegram_id(callback.from_user.id)
    else:
        mentor = await get_student_mentor(callback.from_user.id)
    
    if not mentor:
        await callback.answer(t("error", lang))
        return
        
    topics = await get_topics_by_mentor(mentor)
    materials_count = await get_materials_count_by_topics(topics)
    keyboard = topics_for_view(topics, materials_count, lang, page=page)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("view_"))
async def view_topic_files(callback: CallbackQuery):
    lang = await get_user_language(callback.from_user.id)
    topic_id = int(callback.data.replace("view_", ""))
    topic = await get_topic_by_id(topic_id)
    materials = await get_materials_by_topic(topic)

    keyboard = files_for_view(materials, topic_id, lang, page=0)
    
    await callback.message.edit_text(
        t("topic_files", lang, name=topic.name, count=len(materials)),
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("filespage_"))
async def files_page(callback: CallbackQuery):
    lang = await get_user_language(callback.from_user.id)
    parts = callback.data.split("_")
    topic_id = int(parts[1])
    page = int(parts[2])

    topic = await get_topic_by_id(topic_id)
    materials = await get_materials_by_topic(topic)
    keyboard = files_for_view(materials, topic_id, lang, page=page)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("getfile_"))
async def send_file(callback: CallbackQuery, bot: Bot):
    lang = await get_user_language(callback.from_user.id)
    material_id = int(callback.data.replace("getfile_", ""))
    material = await get_material_by_id(material_id)

    if material:
        if not await is_mentor(callback.from_user.id):
            student = await get_student_by_telegram_id(callback.from_user.id)
            if student:
                await record_download(student, material)
        
        await bot.send_document(
            callback.message.chat.id,
            material.file_id,
            caption=f"📄 <b>{material.title}</b>",
            parse_mode="HTML"
        )
        await callback.answer(t("file_sent", lang))
    else:
        await callback.answer(t("file_not_found", lang))


@router.callback_query(F.data == "back_view")
async def back_to_view(callback: CallbackQuery):
    lang = await get_user_language(callback.from_user.id)
    
    if await is_mentor(callback.from_user.id):
        mentor = await get_mentor_by_telegram_id(callback.from_user.id)
    else:
        mentor = await get_student_mentor(callback.from_user.id)
    
    if not mentor:
        await callback.answer(t("error", lang))
        return
        
    topics = await get_topics_by_mentor(mentor)
    materials_count = await get_materials_count_by_topics(topics)
    keyboard = topics_for_view(topics, materials_count, lang, page=0)

    if not keyboard.inline_keyboard:
        await callback.message.edit_text(t("no_materials_yet", lang))
        return

    await callback.message.edit_text(t("lesson_materials", lang), reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()
