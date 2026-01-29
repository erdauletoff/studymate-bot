import asyncio
import csv
import html
import io
import time
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

QUESTION_TIMEOUT = 20  # seconds per question
QUESTIONS_PER_PAGE = 5
ANSWERS_PER_PAGE = 10  # answers per review page
QUIZ_SESSION_TIMEOUT = 420  # 7 minutes - auto-reset quiz state

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
from bot.texts import t
from bot.db import (
    is_mentor, get_mentor_by_telegram_id, get_student_by_telegram_id,
    get_student_mentor, get_user_language,
    create_quiz, get_quizzes_by_mentor, get_active_quizzes_by_mentor, get_quiz_by_id,
    create_quiz_question, get_questions_by_quiz, get_question_by_id,
    create_quiz_attempt, finish_quiz_attempt, get_student_attempt,
    get_quiz_attempts, get_quiz_average_score,
    get_quiz_stats, get_quiz_stats_by_ids, get_quiz_top_students, save_quiz_answer,
    get_attempt_by_id, get_attempt_answers, set_quiz_active,
    delete_quiz_question, get_next_quiz_question_order, update_quiz_question,
    archive_quizzes_by_title, quiz_title_exists
)
from bot.utils.quiz_parser import parse_quiz_file

router = Router()


class QuizStates(StatesGroup):
    waiting_quiz_file = State()
    waiting_quiz_confirm = State()
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
        await show_mentor_quizzes(message, lang)
    else:
        mentor = await get_student_mentor(message.from_user.id)
        if mentor:
            await show_student_quizzes(message, mentor, lang)
        else:
            await message.answer(t("not_assigned", lang))


async def show_mentor_quizzes(message: Message, lang: str):
    mentor = await get_mentor_by_telegram_id(message.from_user.id)
    quizzes = await get_quizzes_by_mentor(mentor, include_inactive=True)
    stats_map = await get_quiz_stats_by_ids([quiz.id for quiz in quizzes])

    buttons = []
    for quiz in quizzes:
        stats = stats_map.get(quiz.id, {'questions': 0, 'attempts': 0, 'avg': 0})
        title = quiz.title if quiz.is_active else f"🗄️ {quiz.title}"
        buttons.append([InlineKeyboardButton(
            text=t("quiz_item_mentor", lang, title=title, questions=stats['questions'], attempts=stats['attempts']),
            callback_data=f"quizmanage_{quiz.id}"
        )])

    buttons.append([InlineKeyboardButton(text=t("btn_upload_quiz", lang), callback_data="upload_quiz")])

    if not quizzes:
        text = t("no_quizzes", lang)
    else:
        text = t("quiz_mentor_list", lang)

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


async def show_student_quizzes(message: Message, mentor, lang: str):
    quizzes = await get_active_quizzes_by_mentor(mentor)
    student = await get_student_by_telegram_id(message.from_user.id)

    if not quizzes:
        await message.answer(t("no_quizzes", lang))
        return

    buttons = []
    for quiz in quizzes:
        attempt = await get_student_attempt(student, quiz)
        if attempt and attempt.finished_at:
            # Already completed - show score and allow retake
            text = f"✅ {quiz.title} — {attempt.score}/{attempt.total}"
            callback = f"viewquiz_{quiz.id}"
        else:
            # Not attempted yet
            text = f"📝 {quiz.title} — {t('quiz_not_attempted', lang)}"
            callback = f"startquiz_{quiz.id}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=callback)])

    await message.answer(t("select_quiz", lang), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


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
    await state.update_data(parsed=parsed, title=title, topic=parsed.get("topic"))

    preview_text = build_quiz_preview_text(parsed, title, lang)

    if await quiz_title_exists(mentor, title):
        buttons = [
            [InlineKeyboardButton(text=t("btn_replace_quiz", lang), callback_data="quizsave_replace")],
            [InlineKeyboardButton(text=t("btn_copy_quiz", lang), callback_data="quizsave_copy")],
            [InlineKeyboardButton(text=t("btn_cancel_quiz", lang), callback_data="quizcancel")]
        ]
        await message.answer(
            t("quiz_duplicate_found", lang, title=title) + "\n\n" + preview_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )
        return

    buttons = [
        [InlineKeyboardButton(text=t("btn_save_quiz", lang), callback_data="quizsave")],
        [InlineKeyboardButton(text=t("btn_cancel_quiz", lang), callback_data="quizcancel")]
    ]
    await message.answer(preview_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


async def save_quiz_from_state(callback: CallbackQuery, state: FSMContext, lang: str, mode: str):
    data = await state.get_data()
    parsed = data.get("parsed")
    title = data.get("title")
    topic = data.get("topic")

    if not parsed or not title:
        await state.clear()
        await callback.answer(t("error", lang))
        return

    mentor = await get_mentor_by_telegram_id(callback.from_user.id)
    if not mentor:
        await state.clear()
        await callback.answer(t("error", lang))
        return

    if mode == "replace":
        await archive_quizzes_by_title(mentor, title)
    elif mode == "copy":
        title = await ensure_unique_quiz_title(mentor, title)

    quiz = await create_quiz(mentor, title, topic)
    for i, q in enumerate(parsed["questions"], 1):
        await create_quiz_question(
            quiz=quiz,
            question_text=q["text"],
            option_a=q["option_a"],
            option_b=q["option_b"],
            option_c=q["option_c"],
            option_d=q["option_d"],
            correct_answer=q["correct"],
            order=i
        )

    await state.clear()
    await callback.message.edit_text(
        t("quiz_uploaded", lang, title=title, count=len(parsed["questions"])),
        parse_mode="HTML"
    )
    await callback.message.answer(t("quiz_ready_actions", lang), reply_markup=mentor_menu(lang))
    await callback.answer()


@router.callback_query(F.data == "quizsave")
async def quiz_save(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    await save_quiz_from_state(callback, state, lang, mode="save")


@router.callback_query(F.data == "quizsave_replace")
async def quiz_save_replace(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    await save_quiz_from_state(callback, state, lang, mode="replace")


@router.callback_query(F.data == "quizsave_copy")
async def quiz_save_copy(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    await save_quiz_from_state(callback, state, lang, mode="copy")


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


@router.callback_query(F.data == "back_quizzes")
async def back_to_quizzes(callback: CallbackQuery):
    lang = await get_user_language(callback.from_user.id)
    if await is_mentor(callback.from_user.id):
        mentor = await get_mentor_by_telegram_id(callback.from_user.id)
        quizzes = await get_quizzes_by_mentor(mentor, include_inactive=True)
        stats_map = await get_quiz_stats_by_ids([quiz.id for quiz in quizzes])

        buttons = []
        for quiz in quizzes:
            stats = stats_map.get(quiz.id, {'questions': 0, 'attempts': 0, 'avg': 0})
            title = quiz.title if quiz.is_active else f"рџ—„пёЏ {quiz.title}"
            buttons.append([InlineKeyboardButton(
                text=t("quiz_item_mentor", lang, title=title, questions=stats['questions'], attempts=stats['attempts']),
                callback_data=f"quizmanage_{quiz.id}"
            )])

        buttons.append([InlineKeyboardButton(text=t("btn_upload_quiz", lang), callback_data="upload_quiz")])

        if not quizzes:
            text = t("no_quizzes", lang)
        else:
            text = t("quiz_mentor_list", lang)

        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
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

    # Show updated list
    mentor = await get_mentor_by_telegram_id(callback.from_user.id)
    quizzes = await get_quizzes_by_mentor(mentor, include_inactive=True)
    stats_map = await get_quiz_stats_by_ids([quiz.id for quiz in quizzes])

    buttons = []
    for quiz in quizzes:
        stats = stats_map.get(quiz.id, {'questions': 0, 'attempts': 0, 'avg': 0})
        title = quiz.title if quiz.is_active else f"рџ—„пёЏ {quiz.title}"
        buttons.append([InlineKeyboardButton(
            text=t("quiz_item_mentor", lang, title=title, questions=stats['questions'], attempts=stats['attempts']),
            callback_data=f"quizmanage_{quiz.id}"
        )])

    buttons.append([InlineKeyboardButton(text=t("btn_upload_quiz", lang), callback_data="upload_quiz")])

    if not quizzes:
        text = t("no_quizzes", lang)
    else:
        text = t("quiz_mentor_list", lang)

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


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

    # Show result with options to view answers or retake quiz
    buttons = [
        [InlineKeyboardButton(text=t("quiz_view_answers", lang), callback_data=f"reviewquiz_{attempt.id}")],
        [InlineKeyboardButton(text=t("quiz_retake", lang), callback_data=f"startquiz_{quiz_id}")]
    ]

    await callback.message.edit_text(
        t("quiz_already_taken", lang, score=attempt.score, total=attempt.total),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop_handler(callback: CallbackQuery):
    """Handle no-operation callbacks (like page number display)"""
    await callback.answer()


@router.callback_query(F.data.startswith("reviewquiz_"))
async def review_quiz_answers(callback: CallbackQuery):
    lang = await get_user_language(callback.from_user.id)
    parts = callback.data.split("_")
    attempt_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0

    attempt = await get_attempt_by_id(attempt_id)

    if not attempt:
        await callback.answer(t("error", lang))
        return

    # Build review text for current page
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

    # Create new attempt (allow multiple attempts)
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
        score=0
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

    # Show question with initial timer
    text_with_timer = base_text + f"\n\n⏱ {QUESTION_TIMEOUT} {t('quiz_seconds', lang)}"

    if edit:
        sent_message = await message.edit_text(text_with_timer, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
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
    end_time = start_time + QUESTION_TIMEOUT

    # Start countdown updater task
    countdown_task = asyncio.create_task(
        update_countdown(sent_message if not edit else message, base_text, buttons, end_time, lang)
    )

    # Start timeout task
    timeout_task = asyncio.create_task(
        question_timeout(sent_message if not edit else message, attempt_id, question.id, current, total, lang, state, end_time, bot)
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
            quiz = await get_quiz_by_id(data["quiz_id"])
            avg = await get_quiz_average_score(quiz)

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

            # Build result with review (first page)
            result_text = t("quiz_finished", lang, score=score, total=len(question_ids), avg=f"{round(avg, 1)}/{len(question_ids)}")

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
                await message.edit_text(result_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
            else:
                await message.edit_text(result_text, parse_mode="HTML")
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
        quiz = await get_quiz_by_id(data["quiz_id"])
        avg = await get_quiz_average_score(quiz)

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

        # Build result with review (first page)
        result_text = t("quiz_finished", lang, score=score, total=len(question_ids), avg=f"{round(avg, 1)}/{len(question_ids)}")

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
            await callback.message.edit_text(result_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
        else:
            await callback.message.edit_text(result_text, parse_mode="HTML")
    else:
        # Show next question
        await state.update_data(current_index=current_index, score=score)
        next_question = await get_question_by_id(question_ids[current_index])
        await show_question(callback.message, next_question, current_index + 1, len(question_ids), lang, attempt_id, state, bot, edit=True)

    await callback.answer()
