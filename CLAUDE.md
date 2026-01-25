# StudyMate Bot - Quiz Feature Implementation

## Project Overview

StudyMate is a Telegram bot for education. A mentor (teacher) uploads lesson materials, students download them and can ask anonymous questions. The project uses Django (backend) + aiogram 3.x (bot).

### Current Structure
```
studymate/
├── backend/
│   ├── core/
│   │   └── settings.py
│   ├── mentors/
│   │   └── models.py          # Mentor model (telegram_id, name, group_chat_id, language)
│   ├── students/
│   │   └── models.py          # Student model (telegram_id, mentor FK, language)
│   ├── materials/
│   │   └── models.py          # Topic, Material models
│   ├── questions/
│   │   └── models.py          # Question model (anonymous questions)
│   └── downloads/
│       └── models.py          # Download tracking
├── bot/
│   ├── texts.py               # All UI texts in 3 languages (ru, qq, en)
│   ├── db.py                  # All database functions wrapped with @sync_to_async
│   ├── keyboards/
│   │   └── menus.py           # All keyboards and inline buttons
│   └── handlers/
│       ├── start.py           # /start command, language selection
│       ├── mentor.py          # Mentor features (upload, manage, view, stats)
│       ├── student.py         # Student features (view materials)
│       └── questions.py       # Anonymous questions feature
└── run_bot.py
```

### Key Patterns Used

1. **Async DB calls**: All Django ORM operations are wrapped with `@sync_to_async` decorator in `bot/db.py`

2. **Localization**: All texts are in `bot/texts.py` with structure:
```python
TEXTS = {
    "ru": {"key": "Русский текст", ...},
    "qq": {"key": "Qaraqalpaq tekst", ...},
    "en": {"key": "English text", ...},
}

def t(key: str, lang: str = None, **kwargs) -> str:
    # Returns localized text
```

3. **Multi-language button handling**: Buttons are matched by checking all language variants:
```python
@router.message(F.text.in_(["📤 Загрузить", "📤 Júklew", "📤 Upload"]))
```

4. **FSM for multi-step operations**: Using aiogram FSMContext for stateful flows

5. **Keyboards accept language parameter**: `mentor_menu(lang)`, `student_menu(lang)`

---

## Quiz Feature Requirements

### User Stories

**Mentor:**
1. Opens "📝 Quizzes" menu
2. Sees list of existing quizzes with stats
3. Can upload new quiz by sending a .txt file
4. Can view detailed results for each quiz
5. Can delete a quiz

**Student:**
1. Opens "📝 Quizzes" menu
2. Sees list of available quizzes (shows result if already attempted, or "not attempted")
3. Selects a quiz to start (only if NOT attempted before — one attempt only!)
4. Answers questions one by one using inline buttons (A, B, C, D)
5. At the end sees: result, group average, and review of all answers

### IMPORTANT RULES

1. **ONE ATTEMPT ONLY**: Student can take each quiz only ONCE. First result is final. No retakes.
2. **After quiz shows full review**: All questions with student's answers and correct answers highlighted
3. **Viewing results later**: Student can click completed quiz to see their answers again (read-only)

---

## Quiz File Format

Mentor uploads a .txt file with this format:
```
Тема: HTML

1. Какой тег создаёт ссылку?
A) <link>
B*) <a>
C) <href>
D) <url>

2. Что означает HTML?
A*) Hyper Text Markup Language
B) Home Tool Markup Language
C) Hyperlinks Text Mark Language
D) Hyper Tool Multi Language

3. Какой тег для изображения?
A) <picture>
B) <image>
C*) <img>
D) <photo>
```

**Parsing rules:**
- First line "Тема: XXX" or "Topic: XXX" → quiz title/topic (optional, use filename if missing)
- Questions start with number and dot: "1.", "2.", etc.
- Options start with A), B), C), D)
- Correct answer marked with asterisk: "B*)" or "A*)"
- Empty lines separate questions

---

## Database Models

Create new Django app: `backend/quizzes/`

### Quiz
```python
class Quiz(models.Model):
    mentor = models.ForeignKey(Mentor, on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=200)
    topic = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### QuizQuestion
```python
class QuizQuestion(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    option_a = models.CharField(max_length=500)
    option_b = models.CharField(max_length=500)
    option_c = models.CharField(max_length=500)
    option_d = models.CharField(max_length=500)
    correct_answer = models.CharField(max_length=1)  # "A", "B", "C", or "D"
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
```

### QuizAttempt
```python
class QuizAttempt(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    score = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-started_at']
```

### QuizAnswer
```python
class QuizAnswer(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE)
    selected_answer = models.CharField(max_length=1)  # "A", "B", "C", or "D"
    is_correct = models.BooleanField()

    class Meta:
        ordering = ['question__order']  # Sort by question order within attempt
```

---

## Django Admin

**IMPORTANT**: QuizAnswer must be sorted/grouped by QuizAttempt for easy viewing.
```python
@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'topic', 'mentor', 'questions_count', 'attempts_count', 'is_active', 'created_at')
    list_filter = ('mentor', 'is_active', 'created_at')

@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'order', 'question_text_short', 'correct_answer')
    list_filter = ('quiz',)
    ordering = ('quiz', 'order')

@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('student', 'quiz', 'score', 'total', 'percentage', 'finished_at')
    list_filter = ('quiz', 'finished_at')
    ordering = ('-finished_at',)

@admin.register(QuizAnswer)
class QuizAnswerAdmin(admin.ModelAdmin):
    list_display = ('get_student', 'get_quiz', 'question_short', 'selected_answer', 'correct_answer', 'is_correct')
    list_filter = ('attempt__quiz', 'attempt__student', 'is_correct')
    ordering = ('attempt', 'question__order')  # Group by attempt, then by question order
    
    def get_student(self, obj):
        return obj.attempt.student
    get_student.short_description = 'Student'
    
    def get_quiz(self, obj):
        return obj.attempt.quiz
    get_quiz.short_description = 'Quiz'
```

---

## Bot Implementation

### 1. Update Menus (`bot/keyboards/menus.py`)

Add quiz button to both menus:

**Mentor menu:**
```python
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
```

**Student menu:**
```python
def student_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn_lesson_materials", lang)), KeyboardButton(text=t("btn_quizzes", lang))],
            [KeyboardButton(text=t("btn_ask_question", lang))],
            [KeyboardButton(text=t("btn_language", lang))]
        ],
        resize_keyboard=True
    )
```

### 2. Add Texts (`bot/texts.py`)

Add these keys to all three languages (ru, qq, en):
```python
# Quiz texts
"btn_quizzes": "📝 Квизы",
"no_quizzes": "📭 Квизов пока нет.",
"select_quiz": "📝 Выберите квиз:",
"upload_quiz": "📄 Отправьте .txt файл с квизом.",
"quiz_uploaded": "✅ Квиз «{title}» создан!\n\n📊 Вопросов: {count}",
"quiz_parse_error": "❌ Ошибка парсинга файла. Проверьте формат.",
"quiz_question": "❓ <b>Вопрос {current}/{total}</b>\n\n{text}\n\nA) {a}\nB) {b}\nC) {c}\nD) {d}",
"quiz_finished": "🎉 <b>Квиз завершён!</b>\n\n✅ Ваш результат: <b>{score}/{total}</b>\n📊 Среднее по группе: <b>{avg}</b>",
"quiz_review_header": "\n\n📋 <b>Ваши ответы:</b>\n",
"quiz_review_correct": "✅ {num}. {question}\n   Ваш ответ: {answer} ✓\n",
"quiz_review_wrong": "❌ {num}. {question}\n   Ваш ответ: {answer} | Правильно: {correct}\n",
"quiz_results": "📊 <b>Результаты: {title}</b>\n\n👥 Прошли: {attempts}\n📈 Средний балл: {avg}\n\n🏆 <b>Топ учеников:</b>\n{top}",
"quiz_no_attempts": "Ещё никто не прошёл этот квиз.",
"quiz_your_result": "Ваш результат: {score}/{total}",
"quiz_not_attempted": "Ещё не пройден",
"quiz_already_taken": "⚠️ Вы уже проходили этот квиз.\n\nВаш результат: {score}/{total}\n\nПовторное прохождение недоступно.",
"quiz_view_answers": "📋 Посмотреть ответы",
"btn_upload_quiz": "📤 Загрузить квиз",
"btn_delete_quiz": "🗑️ Удалить квиз",
"btn_quiz_results": "📊 Результаты",
"confirm_delete_quiz": "🗑️ <b>Удалить квиз?</b>\n\n📝 {title}\n❓ {count} вопросов\n\nВсе результаты учеников будут удалены!",
```

### 3. Create Handler (`bot/handlers/quiz.py`)

New file for quiz handling:
```python
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

router = Router()

class QuizStates(StatesGroup):
    waiting_quiz_file = State()
    taking_quiz = State()
```

**Mentor handlers:**
- `📝 Квизы` button → show list of quizzes with "📤 Загрузить квиз" button
- `📤 Загрузить квиз` → set state, wait for .txt file
- Receive .txt file → parse, create Quiz and QuizQuestions, confirm
- Quiz item click → show results or delete option

**Student handlers:**
- `📝 Квизы` button → show list of available quizzes
  - Not attempted: "📝 Quiz Name — Ещё не пройден"
  - Attempted: "✅ Quiz Name — 8/10"
- Quiz click (not attempted) → start quiz, show first question
- Quiz click (already attempted) → show "already taken" message with option to view answers
- Answer button (A/B/C/D) → save answer, show next question or finish
- Finish → calculate score, show result with group average AND full review of all answers
- View answers → show all questions with student's answers and correct answers

### 4. Database Functions (`bot/db.py`)

Add these functions (all with `@sync_to_async`):
```python
# Quiz CRUD
def create_quiz(mentor, title, topic=None)
def get_quizzes_by_mentor(mentor)
def get_active_quizzes_by_mentor(mentor)  # For students
def get_quiz_by_id(quiz_id)
def delete_quiz(quiz_id)

# Questions
def create_quiz_question(quiz, question_text, option_a, option_b, option_c, option_d, correct_answer, order)
def get_questions_by_quiz(quiz)
def get_question_by_id(question_id)

# Attempts
def create_quiz_attempt(student, quiz, total)
def finish_quiz_attempt(attempt_id, score)
def get_student_attempt(student, quiz)  # Returns attempt or None (ONE attempt only!)
def has_student_attempted(student, quiz)  # Returns True/False
def get_quiz_attempts(quiz)
def get_quiz_average_score(quiz)

# Answers
def save_quiz_answer(attempt, question, selected_answer, is_correct)
def get_attempt_answers(attempt)  # For review
```

### 5. File Parser

Create `bot/utils/quiz_parser.py`:
```python
def parse_quiz_file(content: str) -> dict:
    """
    Parse quiz file content.
    
    Returns:
        {
            "title": "HTML",
            "topic": "HTML",
            "questions": [
                {
                    "text": "Какой тег создаёт ссылку?",
                    "option_a": "<link>",
                    "option_b": "<a>",
                    "option_c": "<href>",
                    "option_d": "<url>",
                    "correct": "B"
                },
                ...
            ]
        }
    
    Raises:
        ValueError: If format is invalid
    """
```

### 6. Register Router

In `run_bot.py` or main bot file, register the new router:
```python
from bot.handlers import quiz
dp.include_router(quiz.router)
```

---

## Quiz Flow Details

### Student Taking Quiz (First and Only Attempt)

1. Student clicks quiz → check if already attempted
2. If attempted → show "already taken" with score and "view answers" button
3. If not attempted → create QuizAttempt, start quiz
4. Show questions one by one with inline A/B/C/D buttons
5. Each answer saved to QuizAnswer
6. After last question → finish attempt, calculate score
7. Show results screen with:
   - Score (e.g., 8/10)
   - Group average
   - Full review of ALL questions with answers:
```
     ✅ 1. Какой тег создаёт ссылку?
        Ваш ответ: B ✓
     
     ❌ 2. Что означает HTML?
        Ваш ответ: C | Правильно: A
     
     ✅ 3. Какой тег для изображения?
        Ваш ответ: C ✓
```

### Viewing Previous Attempt

1. Student clicks completed quiz
2. Show: "Вы уже проходили этот квиз. Результат: 8/10"
3. Button: "📋 Посмотреть ответы"
4. Click → show same review as after completion

### Callback Data Format
```python
# Quiz selection (student)
f"startquiz_{quiz_id}"      # Start new quiz (only if not attempted)
f"viewquiz_{quiz_id}"       # View previous attempt answers

# Quiz management (mentor)
f"quizresults_{quiz_id}"    # View results
f"quizdelete_{quiz_id}"     # Delete quiz
f"quizconfirmdelete_{quiz_id}"  # Confirm delete

# Answer selection during quiz
f"ans_{attempt_id}_{question_id}_{answer}"  # answer = A/B/C/D
```

---

## Important Notes

1. **ONE ATTEMPT ONLY** - Check `has_student_attempted()` before starting quiz
2. **Show full review after quiz** - All questions, student answers, correct answers
3. **Allow viewing old answers** - Student can always see their answers for completed quizzes
4. **Admin sorting** - QuizAnswer sorted by attempt, then by question order
5. **Always use existing patterns** - look at how materials, questions, downloads are implemented
6. **Always add @sync_to_async** to DB functions in bot/db.py
7. **Always add texts in all 3 languages** (ru, qq, en) in bot/texts.py
8. **Button matching must include all language variants** in F.text.in_([...])
9. **Clear FSM state** when user clicks menu buttons

---

## Testing Checklist

- [ ] Mentor can upload .txt quiz file
- [ ] Parser correctly extracts questions and correct answers
- [ ] Quiz appears in mentor's quiz list
- [ ] Quiz appears in student's quiz list (with status)
- [ ] Student can take quiz ONCE only
- [ ] Second attempt blocked with message
- [ ] Answers are saved correctly
- [ ] Score is calculated correctly
- [ ] Group average is calculated correctly
- [ ] Full review shown after quiz completion
- [ ] Student can view old answers anytime
- [ ] Results shown in Django admin
- [ ] QuizAnswer sorted by attempt in admin
- [ ] Mentor can view quiz results
- [ ] Mentor can delete quiz
- [ ] All texts are localized
- [ ] FSM state is cleared properly