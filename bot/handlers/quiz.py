from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.keyboards import mentor_menu, student_menu
from bot.texts import t
from bot.db import (
    is_mentor, get_mentor_by_telegram_id, get_student_by_telegram_id,
    get_student_mentor, get_user_language,
    create_quiz, get_quizzes_by_mentor, get_quiz_by_id, delete_quiz,
    create_quiz_question, get_questions_by_quiz, get_question_by_id,
    create_quiz_attempt, finish_quiz_attempt, get_student_attempt,
    has_student_attempted, get_quiz_attempts, get_quiz_average_score,
    get_quiz_stats, get_quiz_top_students, save_quiz_answer,
    get_attempt_by_id, get_attempt_answers
)
from bot.utils.quiz_parser import parse_quiz_file

router = Router()


class QuizStates(StatesGroup):
    waiting_quiz_file = State()
    taking_quiz = State()


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
    quizzes = await get_quizzes_by_mentor(mentor)

    buttons = []
    for quiz in quizzes:
        stats = await get_quiz_stats(quiz)
        buttons.append([InlineKeyboardButton(
            text=t("quiz_item_mentor", lang, title=quiz.title, questions=stats['questions'], attempts=stats['attempts']),
            callback_data=f"quizmanage_{quiz.id}"
        )])

    buttons.append([InlineKeyboardButton(text=t("btn_upload_quiz", lang), callback_data="upload_quiz")])

    if not quizzes:
        text = t("no_quizzes", lang)
    else:
        text = t("quiz_mentor_list", lang)

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


async def show_student_quizzes(message: Message, mentor, lang: str):
    quizzes = await get_quizzes_by_mentor(mentor)
    student = await get_student_by_telegram_id(message.from_user.id)

    if not quizzes:
        await message.answer(t("no_quizzes", lang))
        return

    buttons = []
    for quiz in quizzes:
        attempt = await get_student_attempt(student, quiz)
        if attempt and attempt.finished_at:
            # Already completed - show score
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

    # Create quiz
    mentor = await get_mentor_by_telegram_id(message.from_user.id)
    title = parsed.get("title") or message.document.file_name.replace(".txt", "")
    quiz = await create_quiz(mentor, title, parsed.get("topic"))

    # Create questions
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
    await message.answer(
        t("quiz_uploaded", lang, title=title, count=len(parsed["questions"])),
        reply_markup=mentor_menu(lang)
    )


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

    buttons = [
        [InlineKeyboardButton(text=t("btn_delete_quiz", lang), callback_data=f"quizdelete_{quiz_id}")],
        [InlineKeyboardButton(text=t("btn_back", lang), callback_data="back_quizzes")]
    ]

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "back_quizzes")
async def back_to_quizzes(callback: CallbackQuery):
    lang = await get_user_language(callback.from_user.id)
    if await is_mentor(callback.from_user.id):
        mentor = await get_mentor_by_telegram_id(callback.from_user.id)
        quizzes = await get_quizzes_by_mentor(mentor)

        buttons = []
        for quiz in quizzes:
            stats = await get_quiz_stats(quiz)
            buttons.append([InlineKeyboardButton(
                text=t("quiz_item_mentor", lang, title=quiz.title, questions=stats['questions'], attempts=stats['attempts']),
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
        t("confirm_delete_quiz", lang, title=quiz.title, count=stats['questions']),
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

    await delete_quiz(quiz_id)
    await callback.answer(t("quiz_deleted", lang))

    # Show updated list
    mentor = await get_mentor_by_telegram_id(callback.from_user.id)
    quizzes = await get_quizzes_by_mentor(mentor)

    buttons = []
    for quiz in quizzes:
        stats = await get_quiz_stats(quiz)
        buttons.append([InlineKeyboardButton(
            text=t("quiz_item_mentor", lang, title=quiz.title, questions=stats['questions'], attempts=stats['attempts']),
            callback_data=f"quizmanage_{quiz.id}"
        )])

    buttons.append([InlineKeyboardButton(text=t("btn_upload_quiz", lang), callback_data="upload_quiz")])

    if not quizzes:
        text = t("no_quizzes", lang)
    else:
        text = t("quiz_mentor_list", lang)

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


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

    # Show already taken message with view answers button
    buttons = [[InlineKeyboardButton(text=t("quiz_view_answers", lang), callback_data=f"reviewquiz_{attempt.id}")]]

    await callback.message.edit_text(
        t("quiz_already_taken", lang, score=attempt.score, total=attempt.total),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("reviewquiz_"))
async def review_quiz_answers(callback: CallbackQuery):
    lang = await get_user_language(callback.from_user.id)
    attempt_id = int(callback.data.replace("reviewquiz_", ""))
    attempt = await get_attempt_by_id(attempt_id)

    if not attempt:
        await callback.answer(t("error", lang))
        return

    # Build review text
    answers = await get_attempt_answers(attempt)
    review_text = t("quiz_review_header", lang)

    for answer in answers:
        q = answer.question
        q_text = q.question_text[:50] + "..." if len(q.question_text) > 50 else q.question_text
        if answer.is_correct:
            review_text += t("quiz_review_correct", lang, num=q.order, question=q_text, answer=answer.selected_answer)
        else:
            review_text += t("quiz_review_wrong", lang, num=q.order, question=q_text, answer=answer.selected_answer, correct=q.correct_answer)

    text = t("quiz_your_result", lang, score=attempt.score, total=attempt.total) + review_text

    buttons = [[InlineKeyboardButton(text=t("btn_back", lang), callback_data=f"viewquiz_{attempt.quiz_id}")]]

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await callback.answer()


# ==================== STUDENT: TAKE QUIZ ====================

@router.callback_query(F.data.startswith("startquiz_"))
async def start_quiz(callback: CallbackQuery, state: FSMContext):
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

    # Check if already attempted
    if await has_student_attempted(student, quiz):
        attempt = await get_student_attempt(student, quiz)
        buttons = [[InlineKeyboardButton(text=t("quiz_view_answers", lang), callback_data=f"reviewquiz_{attempt.id}")]]
        await callback.message.edit_text(
            t("quiz_already_taken", lang, score=attempt.score, total=attempt.total),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    # Create attempt
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

    # Show first question
    await show_question(callback.message, questions[0], 1, len(questions), lang, attempt.id, edit=True)
    await callback.answer()


async def show_question(message, question, current: int, total: int, lang: str, attempt_id: int, edit: bool = False):
    text = t("quiz_question", lang,
             current=current,
             total=total,
             text=question.question_text,
             a=question.option_a,
             b=question.option_b,
             c=question.option_c,
             d=question.option_d)

    buttons = [[
        InlineKeyboardButton(text="A", callback_data=f"ans_{attempt_id}_{question.id}_A"),
        InlineKeyboardButton(text="B", callback_data=f"ans_{attempt_id}_{question.id}_B"),
        InlineKeyboardButton(text="C", callback_data=f"ans_{attempt_id}_{question.id}_C"),
        InlineKeyboardButton(text="D", callback_data=f"ans_{attempt_id}_{question.id}_D"),
    ]]

    if edit:
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


@router.callback_query(F.data.startswith("ans_"))
async def handle_answer(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)

    # Parse callback data
    parts = callback.data.split("_")
    attempt_id = int(parts[1])
    question_id = int(parts[2])
    selected = parts[3]

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

        await state.clear()

        # Build result with review
        result_text = t("quiz_finished", lang, score=score, total=len(question_ids), avg=f"{round(avg, 1)}/{len(question_ids)}")

        # Add review
        answers = await get_attempt_answers(attempt)
        result_text += t("quiz_review_header", lang)

        for answer in answers:
            q = answer.question
            q_text = q.question_text[:50] + "..." if len(q.question_text) > 50 else q.question_text
            if answer.is_correct:
                result_text += t("quiz_review_correct", lang, num=q.order, question=q_text, answer=answer.selected_answer)
            else:
                result_text += t("quiz_review_wrong", lang, num=q.order, question=q_text, answer=answer.selected_answer, correct=q.correct_answer)

        await callback.message.edit_text(result_text, parse_mode="HTML")
        await callback.message.answer(t("select_quiz", lang), reply_markup=student_menu(lang))
    else:
        # Show next question
        await state.update_data(current_index=current_index, score=score)
        next_question = await get_question_by_id(question_ids[current_index])
        await show_question(callback.message, next_question, current_index + 1, len(question_ids), lang, attempt_id, edit=True)

    await callback.answer()
