from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.db import is_mentor, get_student_mentor, get_user_language
from bot.texts import t


class StudentMentorCheckMiddleware(BaseMiddleware):
    """
    Middleware to check if student is assigned to a mentor.
    Blocks all handlers except /start and language change if student is not assigned.
    Also blocks all commands during quiz taking.
    """

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id

        # Allow mentors to pass through
        if await is_mentor(user_id):
            return await handler(event, data)

        # Check if student is taking a quiz
        state: FSMContext = data.get("state")
        if state:
            current_state = await state.get_state()
            # QuizStates.taking_quiz = "QuizStates:taking_quiz"
            if current_state == "QuizStates:taking_quiz":
                # During quiz, only allow quiz answer callbacks
                if isinstance(event, CallbackQuery):
                    if event.data and event.data.startswith("ans_"):
                        return await handler(event, data)

                # Block everything else during quiz
                lang = await get_user_language(user_id)
                if isinstance(event, Message):
                    await event.answer(t("quiz_in_progress", lang))
                elif isinstance(event, CallbackQuery):
                    await event.answer(t("quiz_in_progress", lang), show_alert=True)
                return

        # Allow /start and /cancel commands
        if isinstance(event, Message):
            if event.text and (event.text.startswith('/start') or event.text.startswith('/cancel')):
                return await handler(event, data)

            # Allow language change buttons
            if event.text and event.text in ["🌐 Язык", "🌐 Til", "🌐 Language"]:
                return await handler(event, data)

            # Allow cancel buttons
            if event.text and event.text in ["❌ Отмена", "❌ Biykar etiw", "❌ Cancel"]:
                return await handler(event, data)

        # Allow language change callback
        if isinstance(event, CallbackQuery):
            if event.data and event.data.startswith("lang_"):
                return await handler(event, data)

        # Check if student has a mentor
        mentor = await get_student_mentor(user_id)
        if not mentor:
            lang = await get_user_language(user_id)

            if isinstance(event, Message):
                await event.answer(t("access_denied", lang))
            elif isinstance(event, CallbackQuery):
                await event.answer(t("access_denied", lang), show_alert=True)

            return

        # Student has mentor, allow to proceed
        return await handler(event, data)
