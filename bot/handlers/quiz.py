import asyncio
import csv
import html
import io
import time
from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from asgiref.sync import sync_to_async

QUESTION_TIMEOUT = 20  # seconds per question
QUESTIONS_PER_PAGE = 5
ANSWERS_PER_PAGE = 10  # answers per review page
QUIZ_SESSION_TIMEOUT = 900  # 15 minutes - auto-reset quiz state
LEADERBOARD_PER_PAGE = 10  # students per page in mentor leaderboard

# Store active timers: {attempt_id: (timeout_task, countdown_task)}
active_timers = {}
# Store quiz session timers: {attempt_id: session_timeout_task}
session_timers = {}

from bot.keyboards import mentor_menu, student_menu, cancel_menu


def escape_html(text: str) -> str:
    """Escape HTML special characters to prevent parsing errors"""
    return html.escape(text)


def get_option_text(question, letter: str) -> str:
    """Get full option text by letter (A, B, C, D)"""
    options = {
        'A': question.option_a,
        'B': question.option_b,
        'C': question.option_c,
        'D': question.option_d,
    }
    return options.get(letter.upper(), letter)


async def build_quiz_result_text(attempt_id: int, score: int, total: int, lang: str) -> tuple[str, list, bool]:
    """
    Build quiz result text based on quiz mode (exam/practice).
    Returns (text, buttons, show_review)
    """
    from bot.db import is_exam_mode

    attempt = await get_attempt_by_id(attempt_id)
    if not attempt:
        return "", [], False

    quiz = await get_quiz_by_id(attempt.quiz_id)
    if not quiz:
        return "", [], False

    # Check if quiz is in exam mode
    if is_exam_mode(quiz):
        # Exam mode: show only score, hide correct answers
        result_text = t("quiz_exam_mode_result", lang, score=score, total=total)
        return result_text, [], False
    else:
        # Practice mode: show full review with correct answers
        avg = await get_quiz_average_score(quiz)
        result_text = t("quiz_finished", lang, score=score, total=total, avg=f"{round(avg, 1)}/{total}")

        # Add review
        answers = await get_attempt_answers(attempt)
        review_text, total_pages = build_review_text(answers, 0, lang)
        result_text += review_text

        # Add pagination buttons if needed
        buttons = []
        if total_pages > 1:
            nav = [
                InlineKeyboardButton(text=f"1/{total_pages}", callback_data="noop"),
                InlineKeyboardButton(text=t("btn_next", lang), callback_data=f"reviewquiz_{attempt_id}_1")
            ]
            buttons.append(nav)

        return result_text, buttons, True


def build_review_text(answers, page: int, lang: str) -> str:
    """Build review text for a specific page"""
    total_pages = (len(answers) + ANSWERS_PER_PAGE - 1) // ANSWERS_PER_PAGE
    start = page * ANSWERS_PER_PAGE
    end = min(start + ANSWERS_PER_PAGE, len(answers))
    page_answers = answers[start:end]

    if total_pages > 1:
        review_text = t("quiz_review_header_page", lang, page=page + 1, total_pages=total_pages)
    else:
        review_text = t("quiz_review_header", lang)

    for answer in page_answers:
        q = answer.question
        q_text = q.question_text[:50] + "..." if len(q.question_text) > 50 else q.question_text
        selected_text = escape_html(get_option_text(q, answer.selected_answer)) if answer.selected_answer != "-" else t("quiz_time_expired", lang)
        if answer.is_correct:
            review_text += t("quiz_review_correct", lang, num=q.order, question=escape_html(q_text), answer=selected_text)
        else:
            correct_text = escape_html(get_option_text(q, q.correct_answer))
            review_text += t("quiz_review_wrong", lang, num=q.order, question=escape_html(q_text), answer=selected_text, correct=correct_text)

    return review_text, total_pages
from bot.texts import t, get_season_name
from bot.db import (
    is_mentor, get_mentor_by_telegram_id, get_student_by_telegram_id,
    get_student_mentor, get_user_language, get_students_by_mentor,
    create_quiz, get_quizzes_by_mentor, get_active_quizzes_by_mentor, get_quiz_by_id,
    create_quiz_question, get_questions_by_quiz, get_question_by_id,
    create_quiz_attempt, finish_quiz_attempt, get_student_attempt,
    get_quiz_attempts, get_quiz_average_score,
    get_quiz_stats, get_quiz_stats_by_ids, get_quiz_top_students, save_quiz_answer,
    get_attempt_by_id, get_attempt_answers, set_quiz_active,
    delete_quiz_question, get_next_quiz_question_order, update_quiz_question,
    archive_quizzes_by_title, quiz_title_exists,
    get_global_leaderboard, get_student_rank
)
from bot.utils.quiz_parser import parse_quiz_file

router = Router()


class QuizStates(StatesGroup):
    waiting_quiz_file = State()
    waiting_quiz_confirm = State()
    waiting_publish_mode = State()
    waiting_ranked_start_time = State()
    taking_quiz = State()


class QuizManageStates(StatesGroup):
    waiting_question_text = State()
    waiting_option_a = State()
    waiting_option_b = State()
    waiting_option_c = State()
    waiting_option_d = State()
    waiting_correct_option = State()
    waiting_edit_value = State()


def build_questions_keyboard(questions, quiz_id: int, lang: str, page: int = 0) -> InlineKeyboardMarkup:
    total_pages = (len(questions) + QUESTIONS_PER_PAGE - 1) // QUESTIONS_PER_PAGE or 1
    start = page * QUESTIONS_PER_PAGE
    end = start + QUESTIONS_PER_PAGE
    page_questions = questions[start:end]

    buttons = []
    for i, q in enumerate(page_questions, start=start + 1):
        # No need to escape here - this is for button text, not HTML parsing
        preview = q.question_text[:40] + ("..." if len(q.question_text) > 40 else "")
        buttons.append([InlineKeyboardButton(
            text=f"{i}. {preview}",
            callback_data=f"quizq_{quiz_id}_{q.id}"
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text=t("btn_prev", lang), callback_data=f"quizqpage_{quiz_id}_{page - 1}"))
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text=t("btn_next", lang), callback_data=f"quizqpage_{quiz_id}_{page + 1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton(text=t("btn_add_question", lang), callback_data=f"quizaddq_{quiz_id}")])
    buttons.append([InlineKeyboardButton(text=t("btn_back_quiz", lang), callback_data=f"quizmanage_{quiz_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_quiz_preview_text(parsed: dict, title: str, lang: str) -> str:
    questions = parsed.get("questions", [])
    topic = parsed.get("topic")
    count = len(questions)
    preview = ""
    if questions:
        q = questions[0]
        preview = t(
            "quiz_preview_question",
            lang,
            text=escape_html(q["text"]),
            a=escape_html(q["option_a"]),
            b=escape_html(q["option_b"]),
            c=escape_html(q["option_c"]),
            d=escape_html(q["option_d"])
        )
    return t(
        "quiz_preview",
        lang,
        title=escape_html(title),
        topic=escape_html(topic) if topic else "-",
        count=count,
        preview=preview
    )


async def ensure_unique_quiz_title(mentor, title: str) -> str:
    if not await quiz_title_exists(mentor, title):
        return title
    base = f"{title} (copy)"
    if not await quiz_title_exists(mentor, base):
        return base
    i = 2
    while True:
        candidate = f"{title} (copy {i})"
        if not await quiz_title_exists(mentor, candidate):
            return candidate
        i += 1


# ==================== MENTOR HANDLERS ====================

@router.message(F.text.in_(["📝 Квизы", "📝 Kvizler", "📝 Quizzes"]))
async def quiz_menu(message: Message, state: FSMContext):
    await state.clear()
    lang = await get_user_language(message.from_user.id)

    if await is_mentor(message.from_user.id):
        # Show choice between active and archived
        buttons = [
            [InlineKeyboardButton(text=t("btn_active_quizzes", lang), callback_data="quizlist_active_0")],
            [InlineKeyboardButton(text=t("btn_archived_quizzes", lang), callback_data="quizlist_archived_0")],
            [InlineKeyboardButton(text=t("btn_upload_quiz", lang), callback_data="upload_quiz")]
        ]
        await message.answer(
            t("quiz_management_header", lang),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )
    else:
        mentor = await get_student_mentor(message.from_user.id)
        if mentor:
            # Show choice between ranked and practice for students
            buttons = [
                [InlineKeyboardButton(text=t("btn_ranked_quizzes", lang), callback_data="studentquiz_ranked_0")],
                [InlineKeyboardButton(text=t("btn_practice_quizzes", lang), callback_data="studentquiz_practice_0")]
            ]
            await message.answer(
                t("quiz_student_header", lang),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                parse_mode="HTML"
            )
        else:
            await message.answer(t("not_assigned", lang))


@router.callback_query(F.data.startswith("quizlist_"))
async def show_quiz_list(callback: CallbackQuery):
    """Handle quiz list navigation (active/archived with pagination)"""
    if not await is_mentor(callback.from_user.id):
        return

    lang = await get_user_language(callback.from_user.id)
    parts = callback.data.split("_")
    list_type = parts[1]  # 'active' or 'archived'
    page = int(parts[2])

    if list_type == "active":
        await show_active_quizzes(callback.message, callback.from_user.id, lang, page, edit=True)
    else:
        await show_archived_quizzes(callback.message, callback.from_user.id, lang, page, edit=True)

    await callback.answer()


async def show_active_quizzes(message, user_id: int, lang: str, page: int = 0, edit: bool = False):
    """Show active quizzes with pagination (5 per page)"""
    QUIZZES_PER_PAGE = 5

    mentor = await get_mentor_by_telegram_id(user_id)

    if not mentor:
        text = t("error_mentor_not_found", lang)
        buttons = [[InlineKeyboardButton(text=t("btn_back_short", lang), callback_data="back_quizzes")]]
        if edit:
            await message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        else:
            await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        return

    all_quizzes = await get_quizzes_by_mentor(mentor, include_inactive=False)
    stats_map = await get_quiz_stats_by_ids([quiz.id for quiz in all_quizzes])

    if not all_quizzes:
        text = t("active_quizzes_header", lang) + "\n\n" + t("no_active_quizzes", lang)
        buttons = [
            [InlineKeyboardButton(text=t("btn_archived_quizzes", lang), callback_data="quizlist_archived_0")],
            [InlineKeyboardButton(text=t("btn_upload_quiz", lang), callback_data="upload_quiz")]
        ]
        if edit:
            await message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
        return

    # Calculate pagination
    total_pages = (len(all_quizzes) + QUIZZES_PER_PAGE - 1) // QUIZZES_PER_PAGE
    start_idx = page * QUIZZES_PER_PAGE
    end_idx = start_idx + QUIZZES_PER_PAGE
    page_quizzes = all_quizzes[start_idx:end_idx]

    # Build text
    text = t("active_quizzes_header", lang) + "\n\n"
    if total_pages > 1:
        text += t("pagination_info", lang, page=page + 1, total=total_pages, count=len(all_quizzes)) + "\n\n"

    # Build buttons
    buttons = []
    for quiz in page_quizzes:
        stats = stats_map.get(quiz.id, {'questions': 0, 'attempts': 0, 'avg': 0})

        # Add badge based on quiz type
        if hasattr(quiz, 'quiz_type'):
            if quiz.quiz_type == 'ranked':
                badge = "🏆"
            else:
                badge = "📚"
        else:
            badge = "📝"

        buttons.append([InlineKeyboardButton(
            text=f"{badge} {quiz.title} • {stats['questions']} вопр. • {stats['attempts']} попыток",
            callback_data=f"quizmanage_{quiz.id}"
        )])

    # Pagination buttons
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"quizlist_active_{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"quizlist_active_{page + 1}"))
        buttons.append(nav)

    # Bottom buttons
    buttons.append([InlineKeyboardButton(text=t("btn_archived_short", lang), callback_data="quizlist_archived_0")])
    buttons.append([InlineKeyboardButton(text=t("btn_upload_quiz", lang), callback_data="upload_quiz")])

    if edit:
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


async def show_archived_quizzes(message, user_id: int, lang: str, page: int = 0, edit: bool = False):
    """Show archived quizzes with pagination (5 per page)"""
    QUIZZES_PER_PAGE = 5

    mentor = await get_mentor_by_telegram_id(user_id)

    if not mentor:
        text = t("error_mentor_not_found", lang)
        buttons = [[InlineKeyboardButton(text=t("btn_back_short", lang), callback_data="back_quizzes")]]
        if edit:
            await message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        else:
            await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        return

    all_quizzes = await get_quizzes_by_mentor(mentor, include_inactive=True)
    archived_quizzes = [q for q in all_quizzes if not q.is_active]
    stats_map = await get_quiz_stats_by_ids([quiz.id for quiz in archived_quizzes])

    if not archived_quizzes:
        text = t("archived_quizzes_header", lang) + "\n\n" + t("no_archived_quizzes", lang)
        buttons = [
            [InlineKeyboardButton(text=t("btn_active_quizzes", lang), callback_data="quizlist_active_0")],
            [InlineKeyboardButton(text=t("btn_upload_quiz", lang), callback_data="upload_quiz")]
        ]
        if edit:
            await message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
        return

    # Calculate pagination
    total_pages = (len(archived_quizzes) + QUIZZES_PER_PAGE - 1) // QUIZZES_PER_PAGE
    start_idx = page * QUIZZES_PER_PAGE
    end_idx = start_idx + QUIZZES_PER_PAGE
    page_quizzes = archived_quizzes[start_idx:end_idx]

    # Build text
    text = t("archived_quizzes_header", lang) + "\n\n"
    if total_pages > 1:
        text += t("pagination_info", lang, page=page + 1, total=total_pages, count=len(archived_quizzes)) + "\n\n"

    # Build buttons
    buttons = []
    for quiz in page_quizzes:
        stats = stats_map.get(quiz.id, {'questions': 0, 'attempts': 0, 'avg': 0})
        buttons.append([InlineKeyboardButton(
            text=f"🗄️ {quiz.title} • {stats['questions']} вопр. • {stats['attempts']} попыток",
            callback_data=f"quizmanage_{quiz.id}"
        )])

    # Pagination buttons
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"quizlist_archived_{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"quizlist_archived_{page + 1}"))
        buttons.append(nav)

    # Bottom buttons
    buttons.append([InlineKeyboardButton(text=t("btn_active_short", lang), callback_data="quizlist_active_0")])
    buttons.append([InlineKeyboardButton(text=t("btn_upload_quiz", lang), callback_data="upload_quiz")])

    if edit:
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


async def show_mentor_quizzes(message: Message, lang: str, page: int = 0):
    """Show mentor quizzes with pagination (5 per page) and separated by active/archived"""
    QUIZZES_PER_PAGE = 5

    mentor = await get_mentor_by_telegram_id(message.from_user.id)
    all_quizzes = await get_quizzes_by_mentor(mentor, include_inactive=True)

    # Separate active and archived
    active_quizzes = [q for q in all_quizzes if q.is_active]
    archived_quizzes = [q for q in all_quizzes if not q.is_active]

    stats_map = await get_quiz_stats_by_ids([quiz.id for quiz in all_quizzes])

    # Build text
    text = ""
    buttons = []

    # Active quizzes section
    if active_quizzes:
        text += "📝 <b>Активные квизы</b>\n\n"
        for quiz in active_quizzes[:QUIZZES_PER_PAGE]:
            stats = stats_map.get(quiz.id, {'questions': 0, 'attempts': 0, 'avg': 0})

            # Add badge based on quiz type
            if hasattr(quiz, 'quiz_type'):
                if quiz.quiz_type == 'ranked':
                    badge = "🏆"
                else:
                    badge = "📚"
            else:
                badge = "📝"

            buttons.append([InlineKeyboardButton(
                text=f"{badge} {quiz.title} • {stats['questions']} вопр. • {stats['attempts']} попыток",
                callback_data=f"quizmanage_{quiz.id}"
            )])

        if len(active_quizzes) > QUIZZES_PER_PAGE:
            text += f"\n<i>Показано {min(QUIZZES_PER_PAGE, len(active_quizzes))} из {len(active_quizzes)}</i>\n"
    else:
        text += "📝 <b>Активные квизы</b>\n\n"
        text += t("no_quizzes", lang) + "\n"

    # Archived quizzes section
    text += "\n🗄️ <b>Архивированные квизы</b>\n\n"
    if archived_quizzes:
        # Calculate pagination for archived
        start_idx = page * QUIZZES_PER_PAGE
        end_idx = start_idx + QUIZZES_PER_PAGE
        page_archived = archived_quizzes[start_idx:end_idx]
        total_pages = (len(archived_quizzes) + QUIZZES_PER_PAGE - 1) // QUIZZES_PER_PAGE

        for quiz in page_archived:
            stats = stats_map.get(quiz.id, {'questions': 0, 'attempts': 0, 'avg': 0})
            buttons.append([InlineKeyboardButton(
                text=f"🗄️ {quiz.title} • {stats['questions']} вопр. • {stats['attempts']} попыток",
                callback_data=f"quizmanage_{quiz.id}"
            )])

        if total_pages > 1:
            text += f"<i>Страница {page + 1}/{total_pages}</i>\n"

            # Pagination buttons for archived
            nav = []
            if page > 0:
                nav.append(InlineKeyboardButton(text="◀️", callback_data=f"quizpage_{page - 1}"))
            nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
            if page < total_pages - 1:
                nav.append(InlineKeyboardButton(text="▶️", callback_data=f"quizpage_{page + 1}"))
            if nav:
                buttons.append(nav)
    else:
        text += "<i>Нет архивированных квизов</i>\n"

    # Upload button
    buttons.append([InlineKeyboardButton(text=t("btn_upload_quiz", lang), callback_data="upload_quiz")])

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


@router.callback_query(F.data.startswith("studentquiz_"))
async def show_student_quiz_list(callback: CallbackQuery):
    """Handle student quiz list navigation (ranked/practice with pagination)"""
    lang = await get_user_language(callback.from_user.id)
    parts = callback.data.split("_")
    list_type = parts[1]  # 'ranked' or 'practice'
    page = int(parts[2])

    mentor = await get_student_mentor(callback.from_user.id)
    if not mentor:
        await callback.answer(t("not_assigned", lang))
        return

    if list_type == "ranked":
        await show_student_ranked_quizzes(callback.message, callback.from_user.id, mentor, lang, page, edit=True)
    else:
        await show_student_practice_quizzes(callback.message, callback.from_user.id, mentor, lang, page, edit=True)

    await callback.answer()


async def show_student_ranked_quizzes(message, user_id: int, mentor, lang: str, page: int = 0, edit: bool = False):
    """Show ranked quizzes for student with pagination (5 per page)"""
    from bot.db import is_exam_mode

    QUIZZES_PER_PAGE = 5

    # Get all active quizzes
    all_quizzes = await get_active_quizzes_by_mentor(mentor)
    student = await get_student_by_telegram_id(user_id)

    # Filter ranked quizzes (in exam mode)
    ranked_quizzes = [quiz for quiz in all_quizzes if is_exam_mode(quiz)]

    if not ranked_quizzes:
        text = t("ranked_quizzes_header", lang) + "\n\n" + t("no_ranked_quizzes", lang)
        buttons = [
            [InlineKeyboardButton(text=t("btn_practice_quizzes", lang), callback_data="studentquiz_practice_0")]
        ]
        if edit:
            await message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
        return

    # Calculate pagination
    total_pages = (len(ranked_quizzes) + QUIZZES_PER_PAGE - 1) // QUIZZES_PER_PAGE
    start_idx = page * QUIZZES_PER_PAGE
    end_idx = start_idx + QUIZZES_PER_PAGE
    page_quizzes = ranked_quizzes[start_idx:end_idx]

    # Build text
    text = t("ranked_quizzes_header", lang) + "\n\n"
    if total_pages > 1:
        text += t("pagination_info", lang, page=page + 1, total=total_pages, count=len(ranked_quizzes)) + "\n\n"

    # Build buttons
    buttons = []
    for quiz in page_quizzes:
        attempt = await get_student_attempt(student, quiz)
        if attempt and attempt.finished_at:
            # Already completed - show score
            btn_text = f"✅ {quiz.title} — {attempt.score}/{attempt.total}"
            callback_data = f"viewquiz_{quiz.id}"
        else:
            # Not attempted yet
            btn_text = f"🏆 {quiz.title}"
            callback_data = f"startquiz_{quiz.id}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=callback_data)])

    # Pagination buttons
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"studentquiz_ranked_{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"studentquiz_ranked_{page + 1}"))
        buttons.append(nav)

    # Bottom button
    buttons.append([InlineKeyboardButton(text=t("btn_practice_short", lang), callback_data="studentquiz_practice_0")])

    if edit:
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


async def show_student_practice_quizzes(message, user_id: int, mentor, lang: str, page: int = 0, edit: bool = False):
    """Show practice quizzes for student with pagination (5 per page)"""
    from bot.db import is_practice_mode

    QUIZZES_PER_PAGE = 5

    # Get all active quizzes
    all_quizzes = await get_active_quizzes_by_mentor(mentor)
    student = await get_student_by_telegram_id(user_id)

    # Filter practice quizzes
    practice_quizzes = [quiz for quiz in all_quizzes if is_practice_mode(quiz)]

    if not practice_quizzes:
        text = t("practice_quizzes_header", lang) + "\n\n" + t("no_practice_quizzes", lang)
        buttons = [
            [InlineKeyboardButton(text=t("btn_ranked_quizzes", lang), callback_data="studentquiz_ranked_0")]
        ]
        if edit:
            await message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
        return

    # Calculate pagination
    total_pages = (len(practice_quizzes) + QUIZZES_PER_PAGE - 1) // QUIZZES_PER_PAGE
    start_idx = page * QUIZZES_PER_PAGE
    end_idx = start_idx + QUIZZES_PER_PAGE
    page_quizzes = practice_quizzes[start_idx:end_idx]

    # Build text
    text = t("practice_quizzes_header", lang) + "\n\n"
    if total_pages > 1:
        text += t("pagination_info", lang, page=page + 1, total=total_pages, count=len(practice_quizzes)) + "\n\n"

    # Build buttons
    buttons = []
    for quiz in page_quizzes:
        attempt = await get_student_attempt(student, quiz)
        if attempt and attempt.finished_at:
            # Already completed - show score and allow retake
            btn_text = f"✅ {quiz.title} — {attempt.score}/{attempt.total}"
            callback_data = f"viewquiz_{quiz.id}"
        else:
            # Not attempted yet
            btn_text = f"📚 {quiz.title}"
            callback_data = f"startquiz_{quiz.id}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=callback_data)])

    # Pagination buttons
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"studentquiz_practice_{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"studentquiz_practice_{page + 1}"))
        buttons.append(nav)

    # Bottom button
    buttons.append([InlineKeyboardButton(text=t("btn_ranked_short", lang), callback_data="studentquiz_ranked_0")])

    if edit:
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


async def show_student_quizzes(message: Message, mentor, lang: str):
    """Legacy function - redirects to new menu"""
    # This is kept for backward compatibility
    buttons = [
        [InlineKeyboardButton(text=t("btn_ranked_quizzes", lang), callback_data="studentquiz_ranked_0")],
        [InlineKeyboardButton(text=t("btn_practice_quizzes", lang), callback_data="studentquiz_practice_0")]
    ]
    await message.answer(
        t("quiz_student_header", lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )


# ==================== MENTOR: UPLOAD QUIZ ====================

@router.callback_query(F.data == "upload_quiz")
async def start_upload_quiz(callback: CallbackQuery, state: FSMContext):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)
    await state.set_state(QuizStates.waiting_quiz_file)
    await callback.message.edit_text(t("upload_quiz", lang))
    await callback.answer()


@router.message(QuizStates.waiting_quiz_file, F.document)
async def receive_quiz_file(message: Message, state: FSMContext, bot: Bot):
    if not await is_mentor(message.from_user.id):
        return
    lang = await get_user_language(message.from_user.id)

    # Download file
    file = await bot.get_file(message.document.file_id)
    file_bytes = await bot.download_file(file.file_path)
    content = file_bytes.read().decode('utf-8')

    try:
        parsed = parse_quiz_file(content)
    except ValueError as e:
        await message.answer(t("quiz_parse_error", lang) + f"\n\n{str(e)}", reply_markup=mentor_menu(lang))
        await state.clear()
        return

    mentor = await get_mentor_by_telegram_id(message.from_user.id)
    title = parsed.get("title") or message.document.file_name.replace(".txt", "")

    await state.set_state(QuizStates.waiting_quiz_confirm)
    await state.update_data(parsed=parsed, title=title, topic=parsed.get("topic"), replace_mode=None)

    preview_text = build_quiz_preview_text(parsed, title, lang)

    if await quiz_title_exists(mentor, title):
        buttons = [
            [InlineKeyboardButton(text=t("btn_view_all_questions", lang), callback_data="quizpreview_all_0")],
            [InlineKeyboardButton(text=t("btn_replace_quiz", lang), callback_data="quizconfirm_replace")],
            [InlineKeyboardButton(text=t("btn_copy_quiz", lang), callback_data="quizconfirm_copy")],
            [InlineKeyboardButton(text=t("btn_cancel_quiz", lang), callback_data="quizcancel")]
        ]
        await message.answer(
            t("quiz_duplicate_found", lang, title=title) + "\n\n" + preview_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )
        return

    buttons = [
        [InlineKeyboardButton(text=t("btn_view_all_questions", lang), callback_data="quizpreview_all_0")],
        [InlineKeyboardButton(text=t("btn_save_quiz", lang), callback_data="quizconfirm_continue")],
        [InlineKeyboardButton(text=t("btn_cancel_quiz", lang), callback_data="quizcancel")]
    ]
    await message.answer(preview_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


@router.callback_query(F.data == "quizconfirm_continue")
async def quiz_confirm_continue(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    await show_publish_mode_selection(callback, state, lang)


@router.callback_query(F.data == "quizconfirm_replace")
async def quiz_confirm_replace(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    await state.update_data(replace_mode="replace")
    await show_publish_mode_selection(callback, state, lang)


@router.callback_query(F.data == "quizconfirm_copy")
async def quiz_confirm_copy(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    await state.update_data(replace_mode="copy")
    await show_publish_mode_selection(callback, state, lang)


@router.callback_query(F.data.startswith("quizpreview_all_"))
async def show_all_questions(callback: CallbackQuery, state: FSMContext):
    """Show all quiz questions with pagination"""
    lang = await get_user_language(callback.from_user.id)
    data = await state.get_data()
    parsed = data.get("parsed")

    if not parsed:
        await callback.answer(t("error", lang))
        return

    questions = parsed.get("questions", [])
    if not questions:
        await callback.answer(t("error", lang))
        return

    page = int(callback.data.split("_")[-1])
    per_page = 3  # Show 3 questions per page

    from bot.keyboards.menus import paginate
    page_questions, nav_buttons, total_pages = paginate(
        items=questions,
        page=page,
        per_page=per_page,
        callback_prefix="quizpreview_all",
        lang=lang
    )

    # Build text for current page
    text = t("quiz_all_questions_header", lang, current=page + 1, total=total_pages)

    start_num = page * per_page
    for i, q in enumerate(page_questions, start=start_num + 1):
        text += t(
            "quiz_question_item",
            lang,
            num=i,
            text=escape_html(q["text"]),
            a=escape_html(q["option_a"]),
            b=escape_html(q["option_b"]),
            c=escape_html(q["option_c"]),
            d=escape_html(q["option_d"]),
            correct=q["correct"].upper()
        )

    # Build keyboard
    buttons = []
    if nav_buttons:
        buttons.append(nav_buttons)
    buttons.append([InlineKeyboardButton(text=t("btn_back_to_preview", lang), callback_data="quizpreview_back")])

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "quizpreview_back")
async def back_to_preview(callback: CallbackQuery, state: FSMContext):
    """Return to quiz preview from all questions view"""
    lang = await get_user_language(callback.from_user.id)
    data = await state.get_data()
    parsed = data.get("parsed")
    title = data.get("title")

    if not parsed or not title:
        await callback.answer(t("error", lang))
        return

    preview_text = build_quiz_preview_text(parsed, title, lang)
    mentor = await get_mentor_by_telegram_id(callback.from_user.id)

    if await quiz_title_exists(mentor, title):
        buttons = [
            [InlineKeyboardButton(text=t("btn_view_all_questions", lang), callback_data="quizpreview_all_0")],
            [InlineKeyboardButton(text=t("btn_replace_quiz", lang), callback_data="quizconfirm_replace")],
            [InlineKeyboardButton(text=t("btn_copy_quiz", lang), callback_data="quizconfirm_copy")],
            [InlineKeyboardButton(text=t("btn_cancel_quiz", lang), callback_data="quizcancel")]
        ]
        await callback.message.edit_text(
            t("quiz_duplicate_found", lang, title=title) + "\n\n" + preview_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )
    else:
        buttons = [
            [InlineKeyboardButton(text=t("btn_view_all_questions", lang), callback_data="quizpreview_all_0")],
            [InlineKeyboardButton(text=t("btn_save_quiz", lang), callback_data="quizconfirm_continue")],
            [InlineKeyboardButton(text=t("btn_cancel_quiz", lang), callback_data="quizcancel")]
        ]
        await callback.message.edit_text(
            preview_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )

    await callback.answer()


async def show_publish_mode_selection(callback: CallbackQuery, state: FSMContext, lang: str):
    """Show publish mode selection menu"""
    await state.set_state(QuizStates.waiting_publish_mode)

    buttons = [
        [InlineKeyboardButton(text=t("btn_publish_practice", lang), callback_data="quizpublish_practice")],
        [InlineKeyboardButton(text=t("btn_publish_ranked", lang), callback_data="quizpublish_ranked")],
        [InlineKeyboardButton(text=t("btn_cancel_quiz", lang), callback_data="quizcancel")]
    ]

    await callback.message.edit_text(
        t("choose_publish_mode", lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "quizpublish_practice")
async def quiz_publish_practice(callback: CallbackQuery, state: FSMContext):
    """Publish quiz as practice mode"""
    lang = await get_user_language(callback.from_user.id)

    data = await state.get_data()
    parsed = data.get("parsed")
    title = data.get("title")
    topic = data.get("topic")
    replace_mode = data.get("replace_mode")

    if not parsed or not title:
        await state.clear()
        await callback.answer(t("error", lang))
        return

    mentor = await get_mentor_by_telegram_id(callback.from_user.id)
    if not mentor:
        await state.clear()
        await callback.answer(t("error", lang))
        return

    # Handle replace/copy mode
    if replace_mode == "replace":
        await archive_quizzes_by_title(mentor, title)
    elif replace_mode == "copy":
        title = await ensure_unique_quiz_title(mentor, title)

    # Create practice quiz
    from bot.db import Quiz
    quiz = Quiz(
        mentor=mentor,
        title=title,
        topic=topic,
        quiz_type='practice',
        max_attempts=999,  # unlimited
        is_active=True
    )
    await sync_to_async(quiz.save)()

    for i, q in enumerate(parsed["questions"], 1):
        await create_quiz_question(
            quiz=quiz,
            question_text=q["text"],
            option_a=q["option_a"],
            option_b=q["option_b"],
            option_c=q["option_c"],
            option_d=q["option_d"],
            correct_answer=q["correct"],
            order=i,
            time_bonus=q.get("time_bonus", 0)
        )

    await state.clear()
    await callback.message.edit_text(
        t("quiz_published_practice", lang, title=title),
        parse_mode="HTML"
    )
    await callback.message.answer(t("quiz_ready_actions", lang), reply_markup=mentor_menu(lang))
    await callback.answer()


@router.callback_query(F.data == "quizpublish_ranked")
async def quiz_publish_ranked_ask_time(callback: CallbackQuery, state: FSMContext):
    """Ask when to start ranked quiz"""
    lang = await get_user_language(callback.from_user.id)

    buttons = [
        [InlineKeyboardButton(text=t("btn_start_now", lang), callback_data="quizranked_now")],
        [InlineKeyboardButton(text=t("btn_schedule_start", lang), callback_data="quizranked_schedule")],
        [InlineKeyboardButton(text=t("btn_cancel_quiz", lang), callback_data="quizcancel")]
    ]

    await callback.message.edit_text(
        t("choose_ranked_start", lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "quizranked_now")
async def quiz_ranked_start_now(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Start ranked quiz now (48 hours window)"""
    from django.utils import timezone
    from datetime import timedelta

    lang = await get_user_language(callback.from_user.id)
    now = timezone.now()

    await state.update_data(
        available_from=now.isoformat(),
        available_until=(now + timedelta(hours=48)).isoformat()
    )

    await save_ranked_quiz(callback, state, lang, bot)


@router.callback_query(F.data == "quizranked_schedule")
async def quiz_ranked_schedule(callback: CallbackQuery, state: FSMContext):
    """Ask for custom start time"""
    lang = await get_user_language(callback.from_user.id)

    await state.set_state(QuizStates.waiting_ranked_start_time)
    await callback.message.edit_text(
        t("enter_ranked_start_time", lang),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(QuizStates.waiting_ranked_start_time)
async def quiz_ranked_receive_start_time(message: Message, state: FSMContext, bot: Bot):
    """Receive and parse custom start time"""
    from datetime import datetime, timedelta
    from django.utils import timezone

    lang = await get_user_language(message.from_user.id)

    # Parse format: DD.MM HH:MM
    try:
        # Get current year
        current_year = datetime.now().year

        # Parse input
        dt_str = message.text.strip()
        dt_naive = datetime.strptime(f"{dt_str} {current_year}", "%d.%m %H:%M %Y")

        # Make timezone aware using Django's make_aware (uses settings.TIME_ZONE)
        available_from = timezone.make_aware(dt_naive)
        available_until = available_from + timedelta(hours=48)

        # Check if in the past
        if available_from < timezone.now():
            await message.answer(t("invalid_datetime_format", lang), parse_mode="HTML")
            return

        await state.update_data(
            available_from=available_from.isoformat(),
            available_until=available_until.isoformat()
        )

        # Create fake callback for save function
        from aiogram.types import CallbackQuery as CB
        fake_callback = type('obj', (object,), {
            'message': message,
            'from_user': message.from_user,
            'answer': lambda *args, **kwargs: None
        })()

        await save_ranked_quiz(fake_callback, state, lang, bot, edit=False)

    except ValueError:
        await message.answer(t("invalid_datetime_format", lang), parse_mode="HTML")


async def save_ranked_quiz(callback, state: FSMContext, lang: str, bot: Bot, edit: bool = True):
    """Save ranked quiz with scheduling"""
    from asgiref.sync import sync_to_async
    from datetime import datetime

    data = await state.get_data()
    parsed = data.get("parsed")
    title = data.get("title")
    topic = data.get("topic")
    replace_mode = data.get("replace_mode")
    available_from_str = data.get("available_from")
    available_until_str = data.get("available_until")

    # Parse ISO format strings back to datetime
    available_from = datetime.fromisoformat(available_from_str) if available_from_str else None
    available_until = datetime.fromisoformat(available_until_str) if available_until_str else None

    if not parsed or not title:
        await state.clear()
        if hasattr(callback, 'answer'):
            await callback.answer(t("error", lang))
        return

    mentor = await get_mentor_by_telegram_id(callback.from_user.id)
    if not mentor:
        await state.clear()
        if hasattr(callback, 'answer'):
            await callback.answer(t("error", lang))
        return

    # Handle replace/copy mode
    if replace_mode == "replace":
        await archive_quizzes_by_title(mentor, title)
    elif replace_mode == "copy":
        title = await ensure_unique_quiz_title(mentor, title)

    # Create ranked quiz
    from bot.db import Quiz
    quiz = Quiz(
        mentor=mentor,
        title=title,
        topic=topic,
        quiz_type='ranked',
        max_attempts=1,
        available_from=available_from,
        available_until=available_until,
        is_active=True
    )
    await sync_to_async(quiz.save)()

    for i, q in enumerate(parsed["questions"], 1):
        await create_quiz_question(
            quiz=quiz,
            question_text=q["text"],
            option_a=q["option_a"],
            option_b=q["option_b"],
            option_c=q["option_c"],
            option_d=q["option_d"],
            correct_answer=q["correct"],
            order=i,
            time_bonus=q.get("time_bonus", 0)
        )

    await state.clear()

    # Format dates for display (convert to local timezone)
    from django.utils import timezone as django_tz
    local_start = django_tz.localtime(available_from)
    local_end = django_tz.localtime(available_until)
    start_str = local_start.strftime("%d.%m %H:%M")
    end_str = local_end.strftime("%d.%m %H:%M")

    result_text = t("quiz_scheduled", lang, title=title, start=start_str, end=end_str)

    if edit and hasattr(callback.message, 'edit_text'):
        await callback.message.edit_text(result_text, parse_mode="HTML")
    else:
        await callback.message.answer(result_text, parse_mode="HTML")

    await callback.message.answer(t("quiz_ready_actions", lang), reply_markup=mentor_menu(lang))

    # Send notifications to all students
    students = await get_students_by_mentor(mentor)
    notification_text_template = "new_ranked_quiz_notification"

    for student in students:
        try:
            student_lang = await get_user_language(student.telegram_id)
            notification_text = t(
                notification_text_template,
                student_lang,
                title=title,
                start=start_str,
                end=end_str
            )
            await bot.send_message(
                student.telegram_id,
                notification_text,
                parse_mode="HTML"
            )
        except Exception as e:
            # Skip students who blocked the bot or have errors
            pass

    if hasattr(callback, 'answer'):
        await callback.answer()


@router.callback_query(F.data == "quizcancel")
async def quiz_cancel(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    await state.clear()
    await callback.message.edit_text(t("cancelled", lang))
    await callback.message.answer(t("quiz_ready_actions", lang), reply_markup=mentor_menu(lang))
    await callback.answer()


# ==================== MENTOR: MANAGE QUIZ ====================

@router.callback_query(F.data.startswith("quizmanage_"))
async def manage_quiz(callback: CallbackQuery):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)
    quiz_id = int(callback.data.replace("quizmanage_", ""))
    quiz = await get_quiz_by_id(quiz_id)

    if not quiz:
        await callback.answer(t("error", lang))
        return

    stats = await get_quiz_stats(quiz)
    top_students = await get_quiz_top_students(quiz)

    if stats['attempts'] == 0:
        text = t("quiz_no_attempts", lang)
    else:
        top_text = ""
        for i, (student, score, total) in enumerate(top_students, 1):
            top_text += f"{i}. {student} — {score}/{total}\n"

        text = t("quiz_results", lang,
                 title=quiz.title,
                 attempts=stats['attempts'],
                 avg=f"{stats['avg']}/{stats['questions']}",
                 top=top_text)

    archive_text = t("btn_unarchive_quiz", lang) if not quiz.is_active else t("btn_archive_quiz", lang)
    buttons = [
        [InlineKeyboardButton(text=archive_text, callback_data=f"quiztoggle_{quiz_id}")],
        [InlineKeyboardButton(text=t("btn_manage_questions", lang), callback_data=f"quizquestions_{quiz_id}")],
        [InlineKeyboardButton(text=t("btn_export_results", lang), callback_data=f"quizexport_{quiz_id}")],
        [InlineKeyboardButton(text=t("btn_back", lang), callback_data="back_quizzes")]
    ]

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("quizpage_"))
async def quiz_page_navigation(callback: CallbackQuery):
    """Handle pagination for archived quizzes"""
    if not await is_mentor(callback.from_user.id):
        return

    lang = await get_user_language(callback.from_user.id)
    page = int(callback.data.replace("quizpage_", ""))

    await show_mentor_quizzes_edit(callback.message, lang, page)
    await callback.answer()


async def show_mentor_quizzes_edit(message, lang: str, page: int = 0):
    """Show mentor quizzes with pagination - for editing existing message"""
    QUIZZES_PER_PAGE = 5

    mentor = await get_mentor_by_telegram_id(message.chat.id)
    all_quizzes = await get_quizzes_by_mentor(mentor, include_inactive=True)

    # Separate active and archived
    active_quizzes = [q for q in all_quizzes if q.is_active]
    archived_quizzes = [q for q in all_quizzes if not q.is_active]

    stats_map = await get_quiz_stats_by_ids([quiz.id for quiz in all_quizzes])

    # Build text
    text = ""
    buttons = []

    # Active quizzes section
    if active_quizzes:
        text += "📝 <b>Активные квизы</b>\n\n"
        for quiz in active_quizzes[:QUIZZES_PER_PAGE]:
            stats = stats_map.get(quiz.id, {'questions': 0, 'attempts': 0, 'avg': 0})

            # Add badge based on quiz type
            if hasattr(quiz, 'quiz_type'):
                if quiz.quiz_type == 'ranked':
                    badge = "🏆"
                else:
                    badge = "📚"
            else:
                badge = "📝"

            buttons.append([InlineKeyboardButton(
                text=f"{badge} {quiz.title} • {stats['questions']} вопр. • {stats['attempts']} попыток",
                callback_data=f"quizmanage_{quiz.id}"
            )])

        if len(active_quizzes) > QUIZZES_PER_PAGE:
            text += f"\n<i>Показано {min(QUIZZES_PER_PAGE, len(active_quizzes))} из {len(active_quizzes)}</i>\n"
    else:
        text += "📝 <b>Активные квизы</b>\n\n"
        text += "📭 Активных квизов пока нет.\n"

    # Archived quizzes section
    text += "\n🗄️ <b>Архивированные квизы</b>\n\n"
    if archived_quizzes:
        # Calculate pagination for archived
        start_idx = page * QUIZZES_PER_PAGE
        end_idx = start_idx + QUIZZES_PER_PAGE
        page_archived = archived_quizzes[start_idx:end_idx]
        total_pages = (len(archived_quizzes) + QUIZZES_PER_PAGE - 1) // QUIZZES_PER_PAGE

        for quiz in page_archived:
            stats = stats_map.get(quiz.id, {'questions': 0, 'attempts': 0, 'avg': 0})
            buttons.append([InlineKeyboardButton(
                text=f"🗄️ {quiz.title} • {stats['questions']} вопр. • {stats['attempts']} попыток",
                callback_data=f"quizmanage_{quiz.id}"
            )])

        if total_pages > 1:
            text += f"<i>Страница {page + 1}/{total_pages}</i>\n"

            # Pagination buttons for archived
            nav = []
            if page > 0:
                nav.append(InlineKeyboardButton(text="◀️", callback_data=f"quizpage_{page - 1}"))
            nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
            if page < total_pages - 1:
                nav.append(InlineKeyboardButton(text="▶️", callback_data=f"quizpage_{page + 1}"))
            if nav:
                buttons.append(nav)
    else:
        text += "<i>Нет архивированных квизов</i>\n"

    # Upload button
    buttons.append([InlineKeyboardButton(text="📤 Загрузить квиз", callback_data="upload_quiz")])

    await message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


@router.callback_query(F.data == "back_quizzes")
async def back_to_quizzes(callback: CallbackQuery):
    lang = await get_user_language(callback.from_user.id)
    if await is_mentor(callback.from_user.id):
        # Show choice menu
        buttons = [
            [InlineKeyboardButton(text=t("btn_active_quizzes", lang), callback_data="quizlist_active_0")],
            [InlineKeyboardButton(text=t("btn_archived_quizzes", lang), callback_data="quizlist_archived_0")],
            [InlineKeyboardButton(text=t("btn_upload_quiz", lang), callback_data="upload_quiz")]
        ]
        await callback.message.edit_text(
            t("quiz_management_header", lang),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("quizdelete_"))
async def confirm_delete_quiz(callback: CallbackQuery):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)
    quiz_id = int(callback.data.replace("quizdelete_", ""))
    quiz = await get_quiz_by_id(quiz_id)

    if not quiz:
        await callback.answer(t("error", lang))
        return

    stats = await get_quiz_stats(quiz)

    buttons = [
        [
            InlineKeyboardButton(text=t("btn_yes_delete", lang), callback_data=f"quizconfirmdelete_{quiz_id}"),
            InlineKeyboardButton(text=t("btn_no_cancel", lang), callback_data=f"quizmanage_{quiz_id}")
        ]
    ]

    await callback.message.edit_text(
        t("confirm_archive_quiz", lang, title=quiz.title, count=stats['questions']),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("quizconfirmdelete_"))
async def delete_quiz_confirmed(callback: CallbackQuery):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)
    quiz_id = int(callback.data.replace("quizconfirmdelete_", ""))

    await set_quiz_active(quiz_id, False)
    await callback.answer(t("quiz_archived", lang))

    # Return to active quizzes list
    await show_active_quizzes(callback.message, callback.from_user.id, lang, page=0, edit=True)


@router.callback_query(F.data.startswith("quiztoggle_"))
async def toggle_quiz_archive(callback: CallbackQuery):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)
    quiz_id = int(callback.data.replace("quiztoggle_", ""))
    quiz = await get_quiz_by_id(quiz_id)

    if not quiz:
        await callback.answer(t("error", lang))
        return

    new_state = not quiz.is_active
    await set_quiz_active(quiz_id, new_state)
    await callback.answer(t("quiz_unarchived", lang) if new_state else t("quiz_archived", lang))

    quiz = await get_quiz_by_id(quiz_id)
    if quiz:
        stats = await get_quiz_stats(quiz)
        top_students = await get_quiz_top_students(quiz)

        if stats['attempts'] == 0:
            text = t("quiz_no_attempts", lang)
        else:
            top_text = ""
            for i, (student, score, total) in enumerate(top_students, 1):
                top_text += f"{i}. {student} вЂ” {score}/{total}\n"

            text = t("quiz_results", lang,
                     title=quiz.title,
                     attempts=stats['attempts'],
                     avg=f"{stats['avg']}/{stats['questions']}",
                     top=top_text)

        archive_text = t("btn_unarchive_quiz", lang) if not quiz.is_active else t("btn_archive_quiz", lang)
        buttons = [
            [InlineKeyboardButton(text=archive_text, callback_data=f"quiztoggle_{quiz.id}")],
            [InlineKeyboardButton(text=t("btn_manage_questions", lang), callback_data=f"quizquestions_{quiz.id}")],
            [InlineKeyboardButton(text=t("btn_export_results", lang), callback_data=f"quizexport_{quiz.id}")],
            [InlineKeyboardButton(text=t("btn_back", lang), callback_data="back_quizzes")]
        ]

        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


# ==================== MENTOR: MANAGE QUESTIONS ====================

@router.callback_query(F.data.startswith("quizquestions_"))
async def quiz_questions(callback: CallbackQuery):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)
    quiz_id = int(callback.data.replace("quizquestions_", ""))
    quiz = await get_quiz_by_id(quiz_id)

    if not quiz:
        await callback.answer(t("error", lang))
        return

    questions = await get_questions_by_quiz(quiz)
    text = t("quiz_questions_title", lang, title=quiz.title, count=len(questions))
    keyboard = build_questions_keyboard(questions, quiz_id, lang, page=0)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("quizqpage_"))
async def quiz_questions_page(callback: CallbackQuery):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)
    parts = callback.data.split("_")
    quiz_id = int(parts[1])
    page = int(parts[2])

    quiz = await get_quiz_by_id(quiz_id)
    if not quiz:
        await callback.answer(t("error", lang))
        return

    questions = await get_questions_by_quiz(quiz)
    text = t("quiz_questions_title", lang, title=quiz.title, count=len(questions))
    keyboard = build_questions_keyboard(questions, quiz_id, lang, page=page)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("quizq_"))
async def quiz_question_detail(callback: CallbackQuery):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)
    parts = callback.data.split("_")
    quiz_id = int(parts[1])
    question_id = int(parts[2])

    question = await get_question_by_id(question_id)
    if not question:
        await callback.answer(t("error", lang))
        return

    text = t(
        "quiz_question_detail",
        lang,
        question=escape_html(question.question_text),
        a=escape_html(question.option_a),
        b=escape_html(question.option_b),
        c=escape_html(question.option_c),
        d=escape_html(question.option_d),
        correct=question.correct_answer
    )

    buttons = [
        [InlineKeyboardButton(text=t("btn_edit_question", lang), callback_data=f"quizqedit_{quiz_id}_{question_id}")],
        [InlineKeyboardButton(text=t("btn_delete_question", lang), callback_data=f"quizqdel_{quiz_id}_{question_id}")],
        [InlineKeyboardButton(text=t("btn_back_questions", lang), callback_data=f"quizquestions_{quiz_id}")]
    ]

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("quizqdel_"))
async def confirm_delete_question(callback: CallbackQuery):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)
    parts = callback.data.split("_")
    quiz_id = int(parts[1])
    question_id = int(parts[2])

    question = await get_question_by_id(question_id)
    if not question:
        await callback.answer(t("error", lang))
        return

    buttons = [
        [
            InlineKeyboardButton(text=t("btn_yes_delete", lang), callback_data=f"quizqdelconfirm_{quiz_id}_{question_id}"),
            InlineKeyboardButton(text=t("btn_no_cancel", lang), callback_data=f"quizq_{quiz_id}_{question_id}")
        ]
    ]

    await callback.message.edit_text(
        t("confirm_delete_question", lang, text=escape_html(question.question_text[:80])),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("quizqdelconfirm_"))
async def delete_question_confirmed(callback: CallbackQuery):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)
    parts = callback.data.split("_")
    quiz_id = int(parts[1])
    question_id = int(parts[2])

    await delete_quiz_question(question_id)
    await callback.answer(t("question_deleted", lang))

    quiz = await get_quiz_by_id(quiz_id)
    if not quiz:
        return

    questions = await get_questions_by_quiz(quiz)
    text = t("quiz_questions_title", lang, title=quiz.title, count=len(questions))
    keyboard = build_questions_keyboard(questions, quiz_id, lang, page=0)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("quizaddq_"))
async def start_add_question(callback: CallbackQuery, state: FSMContext):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)
    quiz_id = int(callback.data.replace("quizaddq_", ""))
    await state.set_state(QuizManageStates.waiting_question_text)
    await state.update_data(quiz_id=quiz_id)
    await callback.message.answer(t("enter_question_text", lang), reply_markup=cancel_menu(lang))
    await callback.answer()


@router.message(QuizManageStates.waiting_question_text)
async def add_question_text(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if message.text == t("btn_cancel", lang):
        await state.clear()
        await message.answer(t("cancelled", lang), reply_markup=mentor_menu(lang))
        return
    await state.update_data(question_text=message.text.strip())
    await state.set_state(QuizManageStates.waiting_option_a)
    await message.answer(t("enter_option_a", lang))


@router.message(QuizManageStates.waiting_option_a)
async def add_option_a(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if message.text == t("btn_cancel", lang):
        await state.clear()
        await message.answer(t("cancelled", lang), reply_markup=mentor_menu(lang))
        return
    await state.update_data(option_a=message.text.strip())
    await state.set_state(QuizManageStates.waiting_option_b)
    await message.answer(t("enter_option_b", lang))


@router.message(QuizManageStates.waiting_option_b)
async def add_option_b(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if message.text == t("btn_cancel", lang):
        await state.clear()
        await message.answer(t("cancelled", lang), reply_markup=mentor_menu(lang))
        return
    await state.update_data(option_b=message.text.strip())
    await state.set_state(QuizManageStates.waiting_option_c)
    await message.answer(t("enter_option_c", lang))


@router.message(QuizManageStates.waiting_option_c)
async def add_option_c(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if message.text == t("btn_cancel", lang):
        await state.clear()
        await message.answer(t("cancelled", lang), reply_markup=mentor_menu(lang))
        return
    await state.update_data(option_c=message.text.strip())
    await state.set_state(QuizManageStates.waiting_option_d)
    await message.answer(t("enter_option_d", lang))


@router.message(QuizManageStates.waiting_option_d)
async def add_option_d(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if message.text == t("btn_cancel", lang):
        await state.clear()
        await message.answer(t("cancelled", lang), reply_markup=mentor_menu(lang))
        return
    await state.update_data(option_d=message.text.strip())
    await state.set_state(QuizManageStates.waiting_correct_option)
    await message.answer(t("enter_correct_option", lang))


@router.message(QuizManageStates.waiting_correct_option)
async def add_correct_option(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if message.text == t("btn_cancel", lang):
        await state.clear()
        await message.answer(t("cancelled", lang), reply_markup=mentor_menu(lang))
        return

    correct = message.text.strip().upper()
    if correct not in ["A", "B", "C", "D"]:
        await message.answer(t("invalid_correct_option", lang))
        return

    data = await state.get_data()
    quiz_id = data.get("quiz_id")
    quiz = await get_quiz_by_id(quiz_id)
    if not quiz:
        await state.clear()
        await message.answer(t("error", lang), reply_markup=mentor_menu(lang))
        return

    order = await get_next_quiz_question_order(quiz)
    await create_quiz_question(
        quiz=quiz,
        question_text=data["question_text"],
        option_a=data["option_a"],
        option_b=data["option_b"],
        option_c=data["option_c"],
        option_d=data["option_d"],
        correct_answer=correct,
        order=order
    )

    await state.clear()
    await message.answer(t("question_added", lang), reply_markup=mentor_menu(lang))


# ==================== MENTOR: EDIT QUESTION ====================

@router.callback_query(F.data.startswith("quizqedit_"))
async def start_edit_question(callback: CallbackQuery, state: FSMContext):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)
    parts = callback.data.split("_")
    quiz_id = int(parts[1])
    question_id = int(parts[2])

    question = await get_question_by_id(question_id)
    if not question:
        await callback.answer(t("error", lang))
        return

    buttons = [
        [InlineKeyboardButton(text=t("btn_edit_text", lang), callback_data=f"quizqeditfield_{quiz_id}_{question_id}_text")],
        [InlineKeyboardButton(text=t("btn_edit_option_a", lang), callback_data=f"quizqeditfield_{quiz_id}_{question_id}_A")],
        [InlineKeyboardButton(text=t("btn_edit_option_b", lang), callback_data=f"quizqeditfield_{quiz_id}_{question_id}_B")],
        [InlineKeyboardButton(text=t("btn_edit_option_c", lang), callback_data=f"quizqeditfield_{quiz_id}_{question_id}_C")],
        [InlineKeyboardButton(text=t("btn_edit_option_d", lang), callback_data=f"quizqeditfield_{quiz_id}_{question_id}_D")],
        [InlineKeyboardButton(text=t("btn_edit_correct", lang), callback_data=f"quizqeditfield_{quiz_id}_{question_id}_correct")],
        [InlineKeyboardButton(text=t("btn_back_questions", lang), callback_data=f"quizquestions_{quiz_id}")]
    ]

    await callback.message.edit_text(
        t("quiz_edit_prompt", lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("quizqeditfield_"))
async def select_edit_field(callback: CallbackQuery, state: FSMContext):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)
    parts = callback.data.split("_")
    quiz_id = int(parts[1])
    question_id = int(parts[2])
    field = parts[3]

    await state.set_state(QuizManageStates.waiting_edit_value)
    await state.update_data(quiz_id=quiz_id, question_id=question_id, edit_field=field)

    prompt_key = {
        "text": "enter_question_text",
        "A": "enter_option_a",
        "B": "enter_option_b",
        "C": "enter_option_c",
        "D": "enter_option_d",
        "correct": "enter_correct_option"
    }.get(field, "enter_question_text")

    await callback.message.answer(t(prompt_key, lang), reply_markup=cancel_menu(lang))
    await callback.answer()


@router.message(QuizManageStates.waiting_edit_value)
async def apply_edit_value(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    data = await state.get_data()
    question_id = data.get("question_id")
    quiz_id = data.get("quiz_id")
    field = data.get("edit_field")

    if message.text == t("btn_cancel", lang):
        await state.clear()
        if question_id and quiz_id:
            question = await get_question_by_id(question_id)
            if question:
                text = t(
                    "quiz_question_detail",
                    lang,
                    question=escape_html(question.question_text),
                    a=escape_html(question.option_a),
                    b=escape_html(question.option_b),
                    c=escape_html(question.option_c),
                    d=escape_html(question.option_d),
                    correct=question.correct_answer
                )
                buttons = [
                    [InlineKeyboardButton(text=t("btn_edit_question", lang), callback_data=f"quizqedit_{quiz_id}_{question_id}")],
                    [InlineKeyboardButton(text=t("btn_delete_question", lang), callback_data=f"quizqdel_{quiz_id}_{question_id}")],
                    [InlineKeyboardButton(text=t("btn_back_questions", lang), callback_data=f"quizquestions_{quiz_id}")]
                ]
                await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
                return
        await message.answer(t("cancelled", lang), reply_markup=mentor_menu(lang))
        return

    if not question_id or not field or not quiz_id:
        await state.clear()
        await message.answer(t("error", lang), reply_markup=mentor_menu(lang))
        return

    value = message.text.strip()
    update_fields = {}

    if field == "text":
        update_fields["question_text"] = value
    elif field == "A":
        update_fields["option_a"] = value
    elif field == "B":
        update_fields["option_b"] = value
    elif field == "C":
        update_fields["option_c"] = value
    elif field == "D":
        update_fields["option_d"] = value
    elif field == "correct":
        value = value.upper()
        if value not in ["A", "B", "C", "D"]:
            await message.answer(t("invalid_correct_option", lang))
            return
        update_fields["correct_answer"] = value
    else:
        await state.clear()
        await message.answer(t("error", lang), reply_markup=mentor_menu(lang))
        return

    await update_quiz_question(question_id, **update_fields)
    await state.clear()

    question = await get_question_by_id(question_id)
    if question:
        text = t(
            "quiz_question_detail",
            lang,
            question=escape_html(question.question_text),
            a=escape_html(question.option_a),
            b=escape_html(question.option_b),
            c=escape_html(question.option_c),
            d=escape_html(question.option_d),
            correct=question.correct_answer
        )
        buttons = [
            [InlineKeyboardButton(text=t("btn_edit_question", lang), callback_data=f"quizqedit_{quiz_id}_{question_id}")],
            [InlineKeyboardButton(text=t("btn_delete_question", lang), callback_data=f"quizqdel_{quiz_id}_{question_id}")],
            [InlineKeyboardButton(text=t("btn_back_questions", lang), callback_data=f"quizquestions_{quiz_id}")]
        ]
        await message.answer(t("question_updated", lang))
        await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
        return

    await message.answer(t("question_updated", lang), reply_markup=mentor_menu(lang))


# ==================== MENTOR: EXPORT RESULTS ====================

@router.callback_query(F.data.startswith("quizexport_"))
async def export_quiz_results(callback: CallbackQuery, bot: Bot):
    if not await is_mentor(callback.from_user.id):
        return
    lang = await get_user_language(callback.from_user.id)
    quiz_id = int(callback.data.replace("quizexport_", ""))
    quiz = await get_quiz_by_id(quiz_id)

    if not quiz:
        await callback.answer(t("error", lang))
        return

    attempts = await get_quiz_attempts(quiz)
    if not attempts:
        await callback.answer(t("quiz_export_empty", lang))
        return

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "quiz_title",
        "student_telegram_id",
        "full_name",
        "username",
        "first_name",
        "last_name",
        "score",
        "total",
        "started_at",
        "finished_at"
    ])

    for attempt in attempts:
        student = attempt.student
        writer.writerow([
            quiz.title,
            student.telegram_id,
            student.full_name or "",
            student.username or "",
            student.first_name or "",
            student.last_name or "",
            attempt.score,
            attempt.total,
            attempt.started_at.isoformat() if attempt.started_at else "",
            attempt.finished_at.isoformat() if attempt.finished_at else ""
        ])

    data = output.getvalue().encode("utf-8")
    filename = f"quiz_{quiz.id}_results.csv"
    await bot.send_document(
        callback.message.chat.id,
        BufferedInputFile(data, filename=filename),
        caption=t("quiz_export_ready", lang)
    )
    await callback.answer()


# ==================== STUDENT: VIEW PREVIOUS ATTEMPT ====================

@router.callback_query(F.data.startswith("viewquiz_"))
async def view_quiz_attempt(callback: CallbackQuery):
    from bot.db import is_exam_mode, is_practice_mode

    lang = await get_user_language(callback.from_user.id)
    quiz_id = int(callback.data.replace("viewquiz_", ""))
    quiz = await get_quiz_by_id(quiz_id)

    if not quiz:
        await callback.answer(t("error", lang))
        return

    student = await get_student_by_telegram_id(callback.from_user.id)
    attempt = await get_student_attempt(student, quiz)

    if not attempt or not attempt.finished_at:
        await callback.answer(t("error", lang))
        return

    # Build buttons based on quiz mode
    buttons = []

    # Show "View answers" button only in practice mode
    if is_practice_mode(quiz):
        buttons.append([InlineKeyboardButton(text=t("quiz_view_answers", lang), callback_data=f"reviewquiz_{attempt.id}")])

    # Show "Retake" button only in practice mode (unlimited attempts)
    if is_practice_mode(quiz):
        buttons.append([InlineKeyboardButton(text=t("quiz_retake", lang), callback_data=f"startquiz_{quiz_id}")])

    # Show appropriate result message
    if is_exam_mode(quiz):
        result_text = t("quiz_exam_mode_result", lang, score=attempt.score, total=attempt.total)
    else:
        result_text = t("quiz_already_taken", lang, score=attempt.score, total=attempt.total)

    if buttons:
        await callback.message.edit_text(
            result_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(result_text, parse_mode="HTML")

    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop_handler(callback: CallbackQuery):
    """Handle no-operation callbacks (like page number display)"""
    await callback.answer()


@router.callback_query(F.data.startswith("leaderpage_"))
async def leaderboard_page_handler(callback: CallbackQuery):
    """Handle mentor leaderboard pagination"""
    lang = await get_user_language(callback.from_user.id)

    # Check if mentor
    if not await is_mentor(callback.from_user.id):
        await callback.answer(t("error", lang))
        return

    # Extract mode and page: leaderpage_{mode}_{page}
    parts = callback.data.replace("leaderpage_", "").split("_")
    mode = parts[0]  # 'season' or 'alltime'
    page = int(parts[1])

    mentor = await get_mentor_by_telegram_id(callback.from_user.id)
    if not mentor:
        await callback.answer(t("error", lang))
        return

    # Get leaderboard based on mode
    from bot.db import get_current_season, get_season_leaderboard

    if mode == 'season':
        season = await get_current_season(mentor)
        leaderboard = await get_season_leaderboard(season, limit=10000)
        title_suffix = f"\n<i>📅 {get_season_name(season, lang)}</i>"
    else:  # alltime
        leaderboard = await get_global_leaderboard(mentor, limit=10000)
        title_suffix = "\n<i>📊 За все время</i>"

    if not leaderboard:
        await callback.message.edit_text(t("leaderboard_empty", lang))
        return

    # Calculate pagination
    total_students = len(leaderboard)
    total_pages = (total_students + LEADERBOARD_PER_PAGE - 1) // LEADERBOARD_PER_PAGE or 1

    # Ensure page is within bounds
    page = max(0, min(page, total_pages - 1))

    start = page * LEADERBOARD_PER_PAGE
    end = start + LEADERBOARD_PER_PAGE
    page_leaderboard = leaderboard[start:end]

    # Build leaderboard text with real names
    text = t("leaderboard_mentor_title", lang) + title_suffix
    text += f"\n<i>{t('leaderboard_mentor_pagination', lang, total=total_students, page=page + 1, total_pages=total_pages)}</i>\n\n"

    for i, (student, rating_score, avg_percentage, total_quizzes) in enumerate(page_leaderboard, start=start + 1):
        # Show real student name for mentor
        student_name = str(student)  # Uses Student.__str__() method
        text += t("leaderboard_mentor_entry", lang,
                 rank=i,
                 name=escape_html(student_name),
                 score=rating_score,
                 percentage=avg_percentage,
                 quizzes=total_quizzes)

    text += t("leaderboard_footer", lang)

    # Build keyboard with mode switcher and pagination
    buttons = []

    # Mode switcher (top row)
    mode_row = []
    if mode == 'season':
        mode_row.append(InlineKeyboardButton(text="✅ Сезон", callback_data="noop"))
        mode_row.append(InlineKeyboardButton(text="📊 Все время", callback_data=f"leadermode_alltime_{page}"))
    else:
        mode_row.append(InlineKeyboardButton(text="📅 Сезон", callback_data=f"leadermode_season_{page}"))
        mode_row.append(InlineKeyboardButton(text="✅ Все время", callback_data="noop"))
    buttons.append(mode_row)

    # Pagination (if needed)
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"leaderpage_{mode}_{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"leaderpage_{mode}_{page + 1}"))
        buttons.append(nav)

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("leadermode_"))
async def leaderboard_mode_handler(callback: CallbackQuery):
    """Handle mentor leaderboard mode switching (season/alltime)"""
    lang = await get_user_language(callback.from_user.id)

    # Check if mentor
    if not await is_mentor(callback.from_user.id):
        await callback.answer(t("error", lang))
        return

    # Extract mode and page: leadermode_{mode}_{page}
    parts = callback.data.replace("leadermode_", "").split("_")
    mode = parts[0]  # 'season' or 'alltime'
    page = int(parts[1]) if len(parts) > 1 else 0

    mentor = await get_mentor_by_telegram_id(callback.from_user.id)
    if not mentor:
        await callback.answer(t("error", lang))
        return

    # Get leaderboard based on mode
    from bot.db import get_current_season, get_season_leaderboard

    if mode == 'season':
        season = await get_current_season(mentor)
        leaderboard = await get_season_leaderboard(season, limit=10000)
        title_suffix = f"\n<i>📅 {get_season_name(season, lang)}</i>"
    else:  # alltime
        leaderboard = await get_global_leaderboard(mentor, limit=10000)
        title_suffix = "\n<i>📊 За все время</i>"

    if not leaderboard:
        await callback.message.edit_text(t("leaderboard_empty", lang))
        return

    # Calculate pagination
    total_students = len(leaderboard)
    total_pages = (total_students + LEADERBOARD_PER_PAGE - 1) // LEADERBOARD_PER_PAGE or 1

    # Ensure page is within bounds
    page = max(0, min(page, total_pages - 1))

    start = page * LEADERBOARD_PER_PAGE
    end = start + LEADERBOARD_PER_PAGE
    page_leaderboard = leaderboard[start:end]

    # Build leaderboard text with real names
    text = t("leaderboard_mentor_title", lang) + title_suffix
    text += f"\n<i>{t('leaderboard_mentor_pagination', lang, total=total_students, page=page + 1, total_pages=total_pages)}</i>\n\n"

    for i, (student, rating_score, avg_percentage, total_quizzes) in enumerate(page_leaderboard, start=start + 1):
        # Show real student name for mentor
        student_name = str(student)  # Uses Student.__str__() method
        text += t("leaderboard_mentor_entry", lang,
                 rank=i,
                 name=escape_html(student_name),
                 score=rating_score,
                 percentage=avg_percentage,
                 quizzes=total_quizzes)

    text += t("leaderboard_footer", lang)

    # Build keyboard with mode switcher and pagination
    buttons = []

    # Mode switcher (top row)
    mode_row = []
    if mode == 'season':
        mode_row.append(InlineKeyboardButton(text="✅ Сезон", callback_data="noop"))
        mode_row.append(InlineKeyboardButton(text="📊 Все время", callback_data=f"leadermode_alltime_{page}"))
    else:
        mode_row.append(InlineKeyboardButton(text="📅 Сезон", callback_data=f"leadermode_season_{page}"))
        mode_row.append(InlineKeyboardButton(text="✅ Все время", callback_data="noop"))
    buttons.append(mode_row)

    # Pagination (if needed)
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"leaderpage_{mode}_{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"leaderpage_{mode}_{page + 1}"))
        buttons.append(nav)

    # Back button
    buttons.append([InlineKeyboardButton(text=t("back", lang), callback_data="main_menu_mentor")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass

    await callback.answer()


@router.callback_query(F.data.startswith("reviewquiz_"))
async def review_quiz_answers(callback: CallbackQuery):
    from bot.db import is_exam_mode

    lang = await get_user_language(callback.from_user.id)
    parts = callback.data.split("_")
    attempt_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0

    attempt = await get_attempt_by_id(attempt_id)

    if not attempt:
        await callback.answer(t("error", lang))
        return

    quiz = await get_quiz_by_id(attempt.quiz_id)
    if not quiz:
        await callback.answer(t("error", lang))
        return

    # Check if quiz is in exam mode
    if is_exam_mode(quiz):
        # Exam mode: don't show correct answers
        text = t("quiz_exam_mode_result", lang, score=attempt.score, total=attempt.total)
        await callback.message.edit_text(text, parse_mode="HTML")
        await callback.answer()
        return

    # Practice mode: show review with correct answers
    answers = await get_attempt_answers(attempt)
    review_text, total_pages = build_review_text(answers, page, lang)

    text = t("quiz_your_result", lang, score=attempt.score, total=attempt.total) + review_text

    # Build pagination buttons
    buttons = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text=t("btn_prev", lang), callback_data=f"reviewquiz_{attempt_id}_{page - 1}"))
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text=t("btn_next", lang), callback_data=f"reviewquiz_{attempt_id}_{page + 1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton(text=t("btn_back", lang), callback_data=f"viewquiz_{attempt.quiz_id}")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await callback.answer()


# ==================== STUDENT: TAKE QUIZ ====================

@router.callback_query(F.data.startswith("startquiz_"))
async def start_quiz(callback: CallbackQuery, state: FSMContext, bot: Bot):
    from bot.db import can_attempt_quiz

    lang = await get_user_language(callback.from_user.id)
    quiz_id = int(callback.data.replace("startquiz_", ""))
    quiz = await get_quiz_by_id(quiz_id)

    if not quiz:
        await callback.answer(t("error", lang))
        return

    student = await get_student_by_telegram_id(callback.from_user.id)
    if not student:
        await callback.answer(t("error", lang))
        return

    # Check if student can attempt this quiz
    can_attempt, reason = await can_attempt_quiz(student, quiz)
    if not can_attempt:
        # Show error message based on reason
        if reason == "quiz_not_started":
            from django.utils import timezone
            if quiz.available_from:
                local_start = timezone.localtime(quiz.available_from)
                start_str = local_start.strftime("%d.%m %H:%M")
            else:
                start_str = "?"
            error_text = t("quiz_not_started", lang, start=start_str)
        elif reason == "quiz_expired":
            error_text = t("quiz_expired", lang)
        elif reason == "quiz_max_attempts":
            error_text = t("quiz_max_attempts", lang)
        else:
            error_text = t("error", lang)

        await callback.message.edit_text(error_text, parse_mode="HTML")
        await callback.answer()
        return

    # Create new attempt
    attempt = await create_quiz_attempt(student, quiz)
    questions = await get_questions_by_quiz(quiz)

    if not questions:
        await callback.answer(t("error", lang))
        return

    # Store in FSM
    await state.set_state(QuizStates.taking_quiz)
    await state.update_data(
        attempt_id=attempt.id,
        quiz_id=quiz.id,
        question_ids=[q.id for q in questions],
        current_index=0,
        score=0,
        quiz_started_at=time.time()
    )

    # Start session timeout timer (7 minutes)
    session_task = asyncio.create_task(quiz_session_timeout(attempt.id, state, bot))
    session_timers[attempt.id] = session_task

    # Show first question
    await show_question(callback.message, questions[0], 1, len(questions), lang, attempt.id, state, bot, edit=True)
    await callback.answer()

async def show_question(message, question, current: int, total: int, lang: str, attempt_id: int, state: FSMContext, bot: Bot, edit: bool = False):
    base_text = t("quiz_question", lang,
             current=current,
             total=total,
             text=escape_html(question.question_text),
             a=escape_html(question.option_a),
             b=escape_html(question.option_b),
             c=escape_html(question.option_c),
             d=escape_html(question.option_d))

    buttons = [[
        InlineKeyboardButton(text="A", callback_data=f"ans_{attempt_id}_{question.id}_A"),
        InlineKeyboardButton(text="B", callback_data=f"ans_{attempt_id}_{question.id}_B"),
        InlineKeyboardButton(text="C", callback_data=f"ans_{attempt_id}_{question.id}_C"),
        InlineKeyboardButton(text="D", callback_data=f"ans_{attempt_id}_{question.id}_D"),
    ]]

    time_bonus = getattr(question, "time_bonus", 0) or 0
    total_timeout = QUESTION_TIMEOUT + time_bonus

    # Show question with initial timer
    text_with_timer = base_text + f"\n\n⏱ {total_timeout} {t('quiz_seconds', lang)}"

    if edit:
        try:
            sent_message = await message.edit_text(text_with_timer, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
        except TelegramBadRequest:
            # Message was deleted by student — send a new one
            sent_message = await bot.send_message(chat_id=message.chat.id, text=text_with_timer, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    else:
        sent_message = await message.answer(text_with_timer, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")

    # Pin the quiz message
    try:
        await bot.pin_chat_message(chat_id=message.chat.id, message_id=sent_message.message_id, disable_notification=True)
        # Store pinned message info in state
        await state.update_data(pinned_message_id=sent_message.message_id, pinned_chat_id=message.chat.id)
    except Exception:
        pass  # Pin might fail due to permissions

    # Cancel previous timers if exist
    if attempt_id in active_timers:
        timeout_task, countdown_task = active_timers[attempt_id]
        if timeout_task:
            timeout_task.cancel()
        if countdown_task:
            countdown_task.cancel()

    # Single time source
    start_time = time.monotonic()
    end_time = start_time + total_timeout

    # Start countdown updater task — always use sent_message so countdown targets the actual message
    countdown_task = asyncio.create_task(
        update_countdown(sent_message, base_text, buttons, end_time, lang)
    )

    # Start timeout task
    timeout_task = asyncio.create_task(
        question_timeout(sent_message, attempt_id, question.id, current, total, lang, state, end_time, bot)
    )

    active_timers[attempt_id] = (timeout_task, countdown_task)


async def update_countdown(message, base_text: str, buttons: list, end_time: float, lang: str):
    """Update countdown timer - shows seconds remaining"""
    try:
        last_displayed = None
        while True:
            remaining = int(end_time - time.monotonic())
            if remaining <= 0:
                break

            # Only update when the second changes
            if remaining != last_displayed:
                last_displayed = remaining
                try:
                    text_with_timer = base_text + f"\n\n⏱ {remaining} {t('quiz_seconds', lang)}"
                    await message.edit_text(text_with_timer, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
                except Exception:
                    pass  # Message might be deleted or already modified

            # Sleep until next second boundary
            await asyncio.sleep(0.5)

    except asyncio.CancelledError:
        pass  # Timer was cancelled


async def quiz_session_timeout(attempt_id: int, state: FSMContext, bot: Bot):
    """Auto-reset quiz state after QUIZ_SESSION_TIMEOUT seconds"""
    try:
        await asyncio.sleep(QUIZ_SESSION_TIMEOUT)

        # Check if still in quiz
        data = await state.get_data()
        if data.get("attempt_id") != attempt_id:
            return

        # Cancel question timers
        if attempt_id in active_timers:
            timeout_task, countdown_task = active_timers[attempt_id]
            if timeout_task:
                timeout_task.cancel()
            if countdown_task:
                countdown_task.cancel()
            del active_timers[attempt_id]

        # Unpin quiz message
        pinned_chat_id = data.get("pinned_chat_id")
        if pinned_chat_id:
            try:
                await bot.unpin_chat_message(chat_id=pinned_chat_id)
            except Exception:
                pass

        # Clear state
        await state.clear()

        # Remove session timer
        if attempt_id in session_timers:
            del session_timers[attempt_id]

    except asyncio.CancelledError:
        pass  # Session timer was cancelled


async def question_timeout(message, attempt_id: int, question_id: int, current: int, total: int, lang: str, state: FSMContext, end_time: float, bot: Bot):
    """Handle question timeout - auto-skip to next question"""
    try:
        # Wait until end_time
        wait_duration = max(0, end_time - time.monotonic())
        await asyncio.sleep(wait_duration)

        # Check if still on the same question
        data = await state.get_data()
        if data.get("attempt_id") != attempt_id:
            return
        if data.get("current_index", 0) != current - 1:
            return  # Already moved to next question

        # Get question and save as wrong (no answer)
        question = await get_question_by_id(question_id)
        if not question:
            return

        attempt = await get_attempt_by_id(attempt_id)
        if not attempt:
            return

        # Save empty answer as wrong
        await save_quiz_answer(attempt, question, "-")  # "-" means timeout/no answer

        current_index = current  # current is 1-based, current_index is 0-based
        question_ids = data.get("question_ids", [])
        score = data.get("score", 0)

        if current_index >= len(question_ids):
            # Quiz finished
            await finish_quiz_attempt(attempt_id, score)

            # Unpin quiz message
            pinned_chat_id = data.get("pinned_chat_id")
            if pinned_chat_id:
                try:
                    await bot.unpin_chat_message(chat_id=pinned_chat_id)
                except Exception:
                    pass  # Unpin might fail

            await state.clear()

            # Remove timers
            if attempt_id in active_timers:
                _, countdown_task = active_timers[attempt_id]
                if countdown_task:
                    countdown_task.cancel()
                del active_timers[attempt_id]

            # Remove session timer
            if attempt_id in session_timers:
                session_timers[attempt_id].cancel()
                del session_timers[attempt_id]

            # Build result text based on quiz mode
            result_text, buttons, show_review = await build_quiz_result_text(attempt_id, score, len(question_ids), lang)

            # Show result (handle deleted message)
            try:
                if buttons:
                    await message.edit_text(result_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
                else:
                    await message.edit_text(result_text, parse_mode="HTML")
            except TelegramBadRequest:
                if buttons:
                    await bot.send_message(chat_id=message.chat.id, text=result_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
                else:
                    await bot.send_message(chat_id=message.chat.id, text=result_text, parse_mode="HTML")
        else:
            # Show next question
            await state.update_data(current_index=current_index, score=score)
            next_question = await get_question_by_id(question_ids[current_index])
            await show_question(message, next_question, current_index + 1, len(question_ids), lang, attempt_id, state, bot, edit=True)

    except asyncio.CancelledError:
        pass  # Timer was cancelled (user answered in time)


@router.callback_query(F.data.startswith("ans_"))
async def handle_answer(callback: CallbackQuery, state: FSMContext, bot: Bot):
    lang = await get_user_language(callback.from_user.id)

    # Parse callback data
    parts = callback.data.split("_")
    attempt_id = int(parts[1])
    question_id = int(parts[2])
    selected = parts[3]

    # Cancel timers (both timeout and countdown)
    if attempt_id in active_timers:
        timeout_task, countdown_task = active_timers[attempt_id]
        if timeout_task:
            timeout_task.cancel()
        if countdown_task:
            countdown_task.cancel()
        del active_timers[attempt_id]

    # Verify state
    data = await state.get_data()
    if data.get("attempt_id") != attempt_id:
        await callback.answer(t("error", lang))
        return

    # Get question and save answer
    question = await get_question_by_id(question_id)
    if not question:
        await callback.answer(t("error", lang))
        return

    attempt = await get_attempt_by_id(attempt_id)
    if not attempt:
        await callback.answer(t("error", lang))
        return

    # Save answer
    is_correct = selected == question.correct_answer
    await save_quiz_answer(attempt, question, selected)

    # Update score
    score = data.get("score", 0)
    if is_correct:
        score += 1

    current_index = data.get("current_index", 0) + 1
    question_ids = data.get("question_ids", [])

    if current_index >= len(question_ids):
        # Quiz finished
        await finish_quiz_attempt(attempt_id, score)

        # Unpin quiz message
        pinned_chat_id = data.get("pinned_chat_id")
        if pinned_chat_id:
            try:
                await bot.unpin_chat_message(chat_id=pinned_chat_id)
            except Exception:
                pass  # Unpin might fail

        await state.clear()

        # Remove session timer
        if attempt_id in session_timers:
            session_timers[attempt_id].cancel()
            del session_timers[attempt_id]

        # Build result text based on quiz mode
        result_text, buttons, show_review = await build_quiz_result_text(attempt_id, score, len(question_ids), lang)

        # Show result (handle deleted message)
        try:
            if buttons:
                await callback.message.edit_text(result_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
            else:
                await callback.message.edit_text(result_text, parse_mode="HTML")
        except TelegramBadRequest:
            if buttons:
                await bot.send_message(chat_id=callback.message.chat.id, text=result_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
            else:
                await bot.send_message(chat_id=callback.message.chat.id, text=result_text, parse_mode="HTML")
    else:
        # Show next question
        await state.update_data(current_index=current_index, score=score)
        next_question = await get_question_by_id(question_ids[current_index])
        await show_question(callback.message, next_question, current_index + 1, len(question_ids), lang, attempt_id, state, bot, edit=True)

    await callback.answer()


# ==================== LEADERBOARD ====================

def get_animal_name(lang: str, index: int) -> str:
    """Get animal name for anonymization based on index"""
    animals = [
        "animal_fox", "animal_bear", "animal_eagle", "animal_wolf", "animal_lion",
        "animal_tiger", "animal_panda", "animal_koala", "animal_owl", "animal_shark",
        "animal_cheetah", "animal_giraffe", "animal_elephant", "animal_cat", "animal_kangaroo"
    ]
    # Use modulo to cycle through animals if we have more than 15 students
    animal_key = animals[index % len(animals)]
    return t(animal_key, lang)


def get_medal_emoji(rank: int) -> str:
    """Get medal emoji for top 3"""
    if rank == 1:
        return "🥇"
    elif rank == 2:
        return "🥈"
    elif rank == 3:
        return "🥉"
    else:
        return f"{rank}."


@router.message(F.text.in_(["🏆 Рейтинг", "🏆 Reyting", "🏆 Leaderboard"]))
async def show_leaderboard(message: Message):
    lang = await get_user_language(message.from_user.id)

    # Check if mentor
    if await is_mentor(message.from_user.id):
        await show_mentor_leaderboard(message, lang)
        return

    # Check if student
    student = await get_student_by_telegram_id(message.from_user.id)
    if not student:
        await message.answer(t("not_assigned", lang))
        return

    mentor = await get_student_mentor(message.from_user.id)
    if not mentor:
        await message.answer(t("not_assigned", lang))
        return

    # Get current season and leaderboard
    from bot.db import get_current_season, get_season_leaderboard, get_student_season_rank
    season = await get_current_season(mentor)
    leaderboard = await get_season_leaderboard(season, limit=15)

    if not leaderboard:
        await message.answer(t("leaderboard_empty", lang))
        return

    # Get current student's rank in season
    student_rank_data = await get_student_season_rank(student, season)

    # Build leaderboard text with season name
    text = t("leaderboard_title", lang)
    text += f"<i>{get_season_name(season, lang)}</i>\n\n"

    for rank, (lb_student, rating_score, avg_percentage, total_quizzes) in enumerate(leaderboard, 1):
        medal = get_medal_emoji(rank)

        if lb_student.id == student.id:
            # Show student's own name
            text += t("leaderboard_you", lang, medal=medal, score=rating_score)
        else:
            # Show animal name for other students
            animal_name = get_animal_name(lang, rank - 1)
            text += t("leaderboard_entry", lang, medal=medal, name=animal_name, score=rating_score)

        # Add separator after top 3
        if rank == 3:
            text += t("leaderboard_separator_top3", lang)

    # Add student's rank if not in top 15
    if student_rank_data and student_rank_data[0] > 15:
        rank, rating_score, avg_percentage, total_quizzes = student_rank_data
        text += t("leaderboard_your_rank", lang, rank=rank, score=rating_score)

    text += t("leaderboard_footer", lang)

    await message.answer(text, parse_mode="HTML")


async def show_mentor_leaderboard(message: Message, lang: str, mode: str = 'season', page: int = 0):
    """
    Show leaderboard for mentor with real student names and pagination.

    Args:
        mode: 'season' for current season, 'alltime' for all-time rating
    """
    mentor = await get_mentor_by_telegram_id(message.from_user.id)
    if not mentor:
        await message.answer(t("error", lang))
        return

    # Get leaderboard based on mode
    from bot.db import get_current_season, get_season_leaderboard

    if mode == 'season':
        season = await get_current_season(mentor)
        leaderboard = await get_season_leaderboard(season, limit=10000)
        title_suffix = f"\n<i>📅 {get_season_name(season, lang)}</i>"
    else:  # alltime
        leaderboard = await get_global_leaderboard(mentor, limit=10000)
        title_suffix = "\n<i>📊 За все время</i>"

    if not leaderboard:
        await message.answer(t("leaderboard_empty", lang))
        return

    # Calculate pagination
    total_students = len(leaderboard)
    total_pages = (total_students + LEADERBOARD_PER_PAGE - 1) // LEADERBOARD_PER_PAGE or 1

    # Ensure page is within bounds
    page = max(0, min(page, total_pages - 1))

    start = page * LEADERBOARD_PER_PAGE
    end = start + LEADERBOARD_PER_PAGE
    page_leaderboard = leaderboard[start:end]

    # Build leaderboard text with real names
    text = t("leaderboard_mentor_title", lang) + title_suffix
    text += f"\n<i>{t('leaderboard_mentor_pagination', lang, total=total_students, page=page + 1, total_pages=total_pages)}</i>\n\n"

    for i, (student, rating_score, avg_percentage, total_quizzes) in enumerate(page_leaderboard, start=start + 1):
        # Show real student name for mentor
        student_name = str(student)  # Uses Student.__str__() method
        text += t("leaderboard_mentor_entry", lang,
                 rank=i,
                 name=escape_html(student_name),
                 score=rating_score,
                 percentage=avg_percentage,
                 quizzes=total_quizzes)

    text += t("leaderboard_footer", lang)

    # Build keyboard with mode switcher and pagination
    buttons = []

    # Mode switcher (top row)
    mode_row = []
    if mode == 'season':
        mode_row.append(InlineKeyboardButton(text="✅ Сезон", callback_data="noop"))
        mode_row.append(InlineKeyboardButton(text="📊 Все время", callback_data=f"leadermode_alltime_{page}"))
    else:
        mode_row.append(InlineKeyboardButton(text="📅 Сезон", callback_data=f"leadermode_season_{page}"))
        mode_row.append(InlineKeyboardButton(text="✅ Все время", callback_data="noop"))
    buttons.append(mode_row)

    # Pagination (if needed)
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"leaderpage_{mode}_{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"leaderpage_{mode}_{page + 1}"))
        buttons.append(nav)

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
