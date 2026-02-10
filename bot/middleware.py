from typing import Callable, Dict, Any, Awaitable
import time
from collections import defaultdict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.db import is_mentor, get_student_mentor, get_user_language
from bot.texts import t, TEXTS


def _all_localized_texts(key: str) -> set[str]:
    return {texts[key] for texts in TEXTS.values() if key in texts}


LANGUAGE_BUTTON_TEXTS = _all_localized_texts("btn_language")
CANCEL_BUTTON_TEXTS = _all_localized_texts("btn_cancel")


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
                # Auto-clear stale quiz state (survives bot restarts unlike asyncio tasks)
                state_data = await state.get_data()
                quiz_started_at = state_data.get("quiz_started_at", 0)
                if quiz_started_at and (time.time() - quiz_started_at) > 900:
                    await state.clear()
                    return await handler(event, data)

                # Allow /cancel to break out of stuck quiz (only for practice, not ranked)
                is_ranked = state_data.get("quiz_type") == "ranked"
                if not is_ranked and isinstance(event, Message):
                    if event.text and (event.text.startswith('/cancel') or event.text in CANCEL_BUTTON_TEXTS):
                        return await handler(event, data)

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
            if event.text and event.text in LANGUAGE_BUTTON_TEXTS:
                return await handler(event, data)

            # Allow cancel buttons
            if event.text and event.text in CANCEL_BUTTON_TEXTS:
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


class ErrorHandlerMiddleware(BaseMiddleware):
    """
    Global error handler middleware.
    Catches all exceptions in handlers and provides user feedback.
    Logs errors for monitoring.
    """

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        import logging
        import traceback

        try:
            return await handler(event, data)
        except Exception as e:
            # Log the error with full traceback
            logger = logging.getLogger('studymate')
            logger.error(
                f"Error handling update from user {event.from_user.id}: {e}",
                exc_info=True,
                extra={
                    'user_id': event.from_user.id,
                    'username': event.from_user.username,
                    'error_type': type(e).__name__,
                    'traceback': traceback.format_exc()
                }
            )

            # Get user language for error message
            user_id = event.from_user.id
            try:
                lang = await get_user_language(user_id)
            except:
                lang = 'ru'

            # Send user-friendly error message
            error_text = t("error", lang)

            try:
                if isinstance(event, Message):
                    await event.answer(error_text)
                elif isinstance(event, CallbackQuery):
                    await event.answer(error_text, show_alert=True)
            except:
                # If we can't send error message, just log it
                logger.error(f"Failed to send error message to user {user_id}")

            # Notify admins (if configured)
            await self._notify_admins(event, e, data)

    async def _notify_admins(self, event, error, data):
        """Send error notification to admins"""
        import os
        import logging

        admin_ids = os.getenv('ADMIN_TELEGRAM_IDS', '').split(',')
        if not admin_ids or admin_ids == ['']:
            return

        bot = data.get('bot')
        if not bot:
            return

        error_msg = (
            f"⚠️ <b>Error in bot</b>\n\n"
            f"👤 User: {event.from_user.id} (@{event.from_user.username or 'no username'})\n"
            f"❌ Error: <code>{type(error).__name__}: {str(error)[:200]}</code>\n"
            f"📝 Type: {type(event).__name__}"
        )

        for admin_id in admin_ids:
            try:
                await bot.send_message(int(admin_id.strip()), error_msg, parse_mode='HTML')
            except Exception as e:
                logging.getLogger('studymate').warning(f"Failed to notify admin {admin_id}: {e}")


class ThrottlingMiddleware(BaseMiddleware):
    """
    Rate limiting middleware to prevent spam and protect from flood attacks.

    Default limits:
    - 1 message per 0.5 seconds (general throttling)
    - Configurable per-user limits stored in memory

    Note: For production with multiple bot instances, use Redis-based throttling.
    """

    def __init__(self, rate_limit: float = 0.5):
        """
        Initialize throttling middleware.

        Args:
            rate_limit: Minimum seconds between messages from same user
        """
        super().__init__()
        self.rate_limit = rate_limit
        self.user_timestamps = defaultdict(float)
        self.user_warning_count = defaultdict(int)

        # Cleanup old entries periodically
        self.last_cleanup = time.time()
        self.cleanup_interval = 300  # 5 minutes

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        now = time.time()

        # Cleanup old entries periodically
        if now - self.last_cleanup > self.cleanup_interval:
            await self._cleanup_old_entries(now)
            self.last_cleanup = now

        # Check if user is throttled
        last_time = self.user_timestamps.get(user_id, 0)
        time_passed = now - last_time

        if time_passed < self.rate_limit:
            # User is sending messages too fast
            self.user_warning_count[user_id] += 1

            # Only send warning on first few violations to avoid spam
            if self.user_warning_count[user_id] <= 3:
                try:
                    lang = await get_user_language(user_id)
                except:
                    lang = 'ru'

                warning_text = self._get_throttle_message(lang, self.user_warning_count[user_id])

                if isinstance(event, Message):
                    await event.answer(warning_text)
                elif isinstance(event, CallbackQuery):
                    await event.answer(warning_text, show_alert=True)

            # Log excessive spam
            if self.user_warning_count[user_id] > 10:
                import logging
                logging.getLogger('studymate').warning(
                    f"User {user_id} is spamming: {self.user_warning_count[user_id]} violations"
                )

            return  # Block the request

        # Update timestamp
        self.user_timestamps[user_id] = now

        # Reset warning count if user behaves well
        if self.user_warning_count[user_id] > 0:
            self.user_warning_count[user_id] = max(0, self.user_warning_count[user_id] - 1)

        # Process the request
        return await handler(event, data)

    def _get_throttle_message(self, lang: str, violation_count: int) -> str:
        """Get appropriate throttle warning message"""
        idx = min(violation_count, 3)
        return t(f"throttle_warning_{idx}", lang)

    async def _cleanup_old_entries(self, now: float):
        """Remove old entries to prevent memory leak"""
        # Remove timestamps older than 10 minutes
        cutoff = now - 600

        old_users = [
            user_id for user_id, timestamp in self.user_timestamps.items()
            if timestamp < cutoff
        ]

        for user_id in old_users:
            del self.user_timestamps[user_id]
            if user_id in self.user_warning_count:
                del self.user_warning_count[user_id]
