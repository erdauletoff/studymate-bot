from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from bot.texts import t

ITEMS_PER_PAGE = 5


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Русский", callback_data="lang_ru"),
            InlineKeyboardButton(text="Qaraqalpaq", callback_data="lang_qq"),
            InlineKeyboardButton(text="English", callback_data="lang_en")
        ]
    ])


def mentor_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn_upload", lang)), KeyboardButton(text=t("btn_manage", lang))],
            [KeyboardButton(text=t("btn_view", lang)), KeyboardButton(text=t("btn_quizzes", lang))],
            [KeyboardButton(text=t("btn_statistics", lang)), KeyboardButton(text=t("btn_questions", lang))],
            [KeyboardButton(text=t("btn_language", lang))]
        ],
        resize_keyboard=True
    )


def student_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn_lesson_materials", lang)), KeyboardButton(text=t("btn_quizzes", lang))],
            [KeyboardButton(text=t("btn_ask_question", lang))],
            [KeyboardButton(text=t("btn_language", lang))]
        ],
        resize_keyboard=True
    )


def cancel_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t("btn_cancel", lang))]],
        resize_keyboard=True
    )


def topics_for_upload(topics, lang: str) -> InlineKeyboardMarkup:
    buttons = []
    for topic in topics:
        buttons.append([InlineKeyboardButton(text=f"📁 {topic.name}", callback_data=f"upload_to_{topic.id}")])
    buttons.append([InlineKeyboardButton(text=t("create_new_topic", lang), callback_data="create_topic")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def topics_for_manage(topics, materials_count: dict, lang: str, page: int = 0) -> InlineKeyboardMarkup:
    total_pages = (len(topics) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE or 1
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    page_topics = topics[start:end]

    buttons = []
    for topic in page_topics:
        count = materials_count.get(topic.id, 0)
        buttons.append([InlineKeyboardButton(
            text=f"📁 {topic.name}  •  {count} 📄",
            callback_data=f"manage_{topic.id}"
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text=t("btn_prev", lang), callback_data=f"managepage_{page - 1}"))
    
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text=t("btn_next", lang), callback_data=f"managepage_{page + 1}"))
    
    if nav:
        buttons.append(nav)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def files_for_manage(materials, topic_id: int, lang: str) -> InlineKeyboardMarkup:
    buttons = []
    for m in materials:
        buttons.append([InlineKeyboardButton(text=f"🗑️ {m.title}", callback_data=f"delete_{topic_id}_{m.id}")])
    
    buttons.append([InlineKeyboardButton(text=t("btn_delete_topic", lang), callback_data=f"deletetopic_{topic_id}")])
    buttons.append([InlineKeyboardButton(text=t("btn_back_topics", lang), callback_data="back_manage")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def topics_for_view(topics, materials_count: dict, lang: str, page: int = 0) -> InlineKeyboardMarkup:
    topics_with_materials = [tp for tp in topics if materials_count.get(tp.id, 0) > 0]

    total_pages = (len(topics_with_materials) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE or 1
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    page_topics = topics_with_materials[start:end]

    buttons = []
    for topic in page_topics:
        count = materials_count.get(topic.id, 0)
        buttons.append([InlineKeyboardButton(
            text=f"📂 {topic.name}  •  {count} 📄",
            callback_data=f"view_{topic.id}"
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text=t("btn_prev", lang), callback_data=f"viewpage_{page - 1}"))
    
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text=t("btn_next", lang), callback_data=f"viewpage_{page + 1}"))
    
    if nav:
        buttons.append(nav)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def files_for_view(materials, topic_id: int, lang: str, page: int = 0) -> InlineKeyboardMarkup:
    total_pages = (len(materials) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE or 1
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    page_materials = materials[start:end]

    buttons = []
    for i, m in enumerate(page_materials, start=start+1):
        buttons.append([InlineKeyboardButton(
            text=f"{i}. {m.title}",
            callback_data=f"getfile_{m.id}"
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text=t("btn_prev", lang), callback_data=f"filespage_{topic_id}_{page - 1}"))
    
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text=t("btn_next", lang), callback_data=f"filespage_{topic_id}_{page + 1}"))
    
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton(text=t("btn_back", lang), callback_data="back_view")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
