from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from bot.texts import t
from typing import List, Callable, Any, Optional, Tuple

ITEMS_PER_PAGE = 5


# ==================== UNIVERSAL PAGINATOR ====================

def paginate(
    items: List[Any],
    page: int,
    per_page: int,
    callback_prefix: str,
    lang: str,
    extra_data: str = ""
) -> Tuple[List[Any], List[InlineKeyboardButton], int]:
    """
    Universal pagination function.

    Args:
        items: List of items to paginate
        page: Current page (0-indexed)
        per_page: Items per page
        callback_prefix: Prefix for navigation callbacks (e.g., "msgpage")
        lang: Language code for button texts
        extra_data: Extra data to include in callback (e.g., topic_id)

    Returns:
        Tuple of (page_items, nav_buttons, total_pages)

    Example:
        page_items, nav_buttons, total = paginate(students, page=0, per_page=5,
                                                   callback_prefix="msgpage", lang="ru")
    """
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))  # Clamp page to valid range

    start = page * per_page
    end = start + per_page
    page_items = items[start:end]

    nav_buttons = []

    # Build callback data with optional extra_data
    def make_callback(p: int) -> str:
        if extra_data:
            return f"{callback_prefix}_{extra_data}_{p}"
        return f"{callback_prefix}_{p}"

    if page > 0:
        nav_buttons.append(InlineKeyboardButton(
            text=t("btn_prev", lang),
            callback_data=make_callback(page - 1)
        ))

    if total_pages > 1:
        nav_buttons.append(InlineKeyboardButton(
            text=f"{page + 1}/{total_pages}",
            callback_data="noop"
        ))

    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(
            text=t("btn_next", lang),
            callback_data=make_callback(page + 1)
        ))

    return page_items, nav_buttons, total_pages


# ==================== BASIC MENUS ====================

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
            [KeyboardButton(text=t("btn_materials_menu", lang)), KeyboardButton(text=t("btn_quizzes", lang))],
            [KeyboardButton(text=t("btn_questions", lang)), KeyboardButton(text=t("btn_leaderboard", lang))],
            [KeyboardButton(text=t("btn_message_students", lang)), KeyboardButton(text=t("btn_language", lang))]
        ],
        resize_keyboard=True
    )


def materials_submenu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn_upload", lang)), KeyboardButton(text=t("btn_manage", lang))],
            [KeyboardButton(text=t("btn_statistics", lang)), KeyboardButton(text=t("btn_back_menu", lang))]
        ],
        resize_keyboard=True
    )


def student_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn_lesson_materials", lang)), KeyboardButton(text=t("btn_quizzes", lang))],
            [KeyboardButton(text=t("btn_ask_question", lang)), KeyboardButton(text=t("btn_leaderboard", lang))],
            [KeyboardButton(text=t("btn_profile", lang)), KeyboardButton(text=t("btn_language", lang))]
        ],
        resize_keyboard=True
    )


def profile_setup_keyboard(lang: str, telegram_name: str = None) -> ReplyKeyboardMarkup:
    """Keyboard for profile setup with optional Telegram name button"""
    keyboard = []
    if telegram_name:
        keyboard.append([KeyboardButton(text=t("btn_use_telegram_name", lang))])
    keyboard.append([KeyboardButton(text=t("btn_cancel", lang))])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def cancel_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t("btn_cancel", lang))]],
        resize_keyboard=True
    )


# ==================== TOPICS & MATERIALS ====================

def topics_for_upload(topics, lang: str) -> InlineKeyboardMarkup:
    buttons = []
    for topic in topics:
        buttons.append([InlineKeyboardButton(text=f"📁 {topic.name}", callback_data=f"upload_to_{topic.id}")])
    buttons.append([InlineKeyboardButton(text=t("create_new_topic", lang), callback_data="create_topic")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def topics_for_manage(topics, materials_count: dict, lang: str, page: int = 0) -> InlineKeyboardMarkup:
    page_topics, nav_buttons, _ = paginate(
        items=topics,
        page=page,
        per_page=ITEMS_PER_PAGE,
        callback_prefix="managepage",
        lang=lang
    )

    buttons = []
    for topic in page_topics:
        count = materials_count.get(topic.id, 0)
        buttons.append([InlineKeyboardButton(
            text=f"📁 {topic.name}  •  {count} 📄",
            callback_data=f"manage_{topic.id}"
        )])

    if nav_buttons:
        buttons.append(nav_buttons)

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

    page_topics, nav_buttons, _ = paginate(
        items=topics_with_materials,
        page=page,
        per_page=ITEMS_PER_PAGE,
        callback_prefix="viewpage",
        lang=lang
    )

    buttons = []
    for topic in page_topics:
        count = materials_count.get(topic.id, 0)
        buttons.append([InlineKeyboardButton(
            text=f"📂 {topic.name}  •  {count} 📄",
            callback_data=f"view_{topic.id}"
        )])

    if nav_buttons:
        buttons.append(nav_buttons)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def files_for_view(materials, topic_id: int, lang: str, page: int = 0) -> InlineKeyboardMarkup:
    page_materials, nav_buttons, _ = paginate(
        items=materials,
        page=page,
        per_page=ITEMS_PER_PAGE,
        callback_prefix="filespage",
        lang=lang,
        extra_data=str(topic_id)
    )

    buttons = []
    start_num = page * ITEMS_PER_PAGE
    for i, m in enumerate(page_materials, start=start_num + 1):
        buttons.append([InlineKeyboardButton(
            text=f"{i}. {m.title}",
            callback_data=f"getfile_{m.id}"
        )])

    if nav_buttons:
        buttons.append(nav_buttons)

    buttons.append([InlineKeyboardButton(text=t("btn_back", lang), callback_data="back_view")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==================== STUDENTS FOR MESSAGING ====================

def students_for_message(students, lang: str, page: int = 0, show_broadcast: bool = True) -> InlineKeyboardMarkup:
    """
    Show list of students for selecting to send a message.

    Args:
        students: List of student objects
        lang: Language code
        page: Current page (0-indexed)
        show_broadcast: Whether to show "Message All" button
    """
    page_students, nav_buttons, total_pages = paginate(
        items=students,
        page=page,
        per_page=ITEMS_PER_PAGE,
        callback_prefix="msgpage",
        lang=lang
    )

    buttons = []

    # Add "Message All Students" button at the top if there are multiple students
    if show_broadcast and len(students) > 1:
        buttons.append([InlineKeyboardButton(
            text=f"📢 {t('btn_message_all', lang)} ({len(students)})",
            callback_data="msgstudent_all"
        )])

    for student in page_students:
        # Show full name if available, otherwise Telegram name or ID
        name = student.full_name or f"{student.first_name} {student.last_name}".strip() or f"ID: {student.telegram_id}"
        # Add username if available
        username_suffix = f" (@{student.username})" if student.username else ""
        display_name = f"{name}{username_suffix}"

        buttons.append([InlineKeyboardButton(
            text=f"👤 {display_name}",
            callback_data=f"msgstudent_{student.id}"
        )])

    if nav_buttons:
        buttons.append(nav_buttons)

    # Add cancel button
    buttons.append([InlineKeyboardButton(
        text=t("btn_cancel", lang),
        callback_data="msgstudent_cancel"
    )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_broadcast_keyboard(lang: str, student_count: int) -> InlineKeyboardMarkup:
    """Confirmation keyboard for broadcasting to all students"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"✅ {t('btn_confirm', lang)} ({student_count})",
                callback_data="broadcast_confirm"
            )
        ],
        [
            InlineKeyboardButton(
                text=t("btn_cancel", lang),
                callback_data="broadcast_cancel"
            )
        ]
    ])
