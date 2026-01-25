# StudyMate Bot - Полное описание проекта

## Общая информация

**StudyMate** — это Telegram-бот для образования. Менторы (учителя) загружают учебные материалы, студенты скачивают их и могут задавать анонимные вопросы. Также реализована система квизов для проверки знаний.

**Технологии:**
- Python 3.11
- Django 4.2+ (бэкенд, ORM, админка)
- aiogram 3.x (Telegram Bot API)
- SQLite (по умолчанию) / PostgreSQL (продакшн)
- Heroku (деплой)

---

## Структура проекта

```
studymate-bot/
├── backend/                    # Django приложения
│   ├── core/                   # Настройки Django
│   │   ├── settings.py         # Конфигурация (DB, apps, middleware)
│   │   ├── urls.py             # URL маршруты (только /admin/)
│   │   └── wsgi.py             # WSGI для Gunicorn
│   ├── mentors/                # Менторы
│   │   ├── models.py           # Mentor модель
│   │   └── admin.py            # Регистрация в админке
│   ├── students/               # Студенты
│   │   ├── models.py           # Student модель
│   │   └── admin.py
│   ├── materials/              # Учебные материалы
│   │   ├── models.py           # Topic, Material модели
│   │   └── admin.py
│   ├── questions/              # Анонимные вопросы
│   │   ├── models.py           # Question модель
│   │   └── admin.py
│   ├── downloads/              # Отслеживание скачиваний
│   │   ├── models.py           # Download модель
│   │   └── admin.py
│   └── quizzes/                # Квизы (тесты)
│       ├── models.py           # Quiz, QuizQuestion, QuizAttempt, QuizAnswer
│       └── admin.py
├── bot/                        # Telegram бот (aiogram 3.x)
│   ├── handlers/               # Обработчики сообщений
│   │   ├── __init__.py         # Регистрация роутеров
│   │   ├── start.py            # /start, выбор языка
│   │   ├── mentor.py           # Функции ментора
│   │   ├── student.py          # Функции студента
│   │   ├── questions.py        # Анонимные вопросы
│   │   └── quiz.py             # Квизы
│   ├── keyboards/
│   │   ├── __init__.py         # Экспорт клавиатур
│   │   └── menus.py            # Все клавиатуры и кнопки
│   ├── utils/
│   │   └── quiz_parser.py      # Парсер .txt файлов квизов
│   ├── db.py                   # Все функции работы с БД (@sync_to_async)
│   └── texts.py                # Локализация (ru, qq, en)
├── manage.py                   # Django CLI
├── run_bot.py                  # Запуск бота
├── setup_mentor.py             # Скрипт добавления ментора
├── requirements.txt            # Зависимости
├── Procfile                    # Heroku процессы
├── runtime.txt                 # Версия Python для Heroku
└── .env                        # Переменные окружения (не в git)
```

---

## Модели базы данных

### Mentor (backend/mentors/models.py)
```python
class Mentor(models.Model):
    telegram_id = models.BigIntegerField(unique=True)  # Telegram ID ментора
    name = models.CharField(max_length=100)             # Имя ментора
    group_chat_id = models.BigIntegerField()            # ID группы курса в Telegram
    language = models.CharField(max_length=5, default='ru')  # Язык интерфейса
    is_active = models.BooleanField(default=True)       # Активен ли ментор
    created_at = models.DateTimeField(auto_now_add=True)
```

**Логика:** Ментор создаётся вручную через Django admin или скрипт `setup_mentor.py`. Студенты привязываются к ментору через `group_chat_id` — бот проверяет членство студента в группе.

### Student (backend/students/models.py)
```python
class Student(models.Model):
    telegram_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=100, blank=True, null=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    mentor = models.ForeignKey(Mentor, on_delete=models.SET_NULL, null=True, related_name='students')
    language = models.CharField(max_length=5, default='ru')
    joined_at = models.DateTimeField(auto_now_add=True)
    last_active = models.DateTimeField(auto_now=True)
```

**Логика:** Студент создаётся автоматически при первом `/start`. Привязка к ментору происходит через проверку членства в группе ментора.

### Topic (backend/materials/models.py)
```python
class Topic(models.Model):
    mentor = models.ForeignKey(Mentor, on_delete=models.CASCADE, related_name='topics')
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
```

### Material (backend/materials/models.py)
```python
class Material(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='materials')
    title = models.CharField(max_length=200)
    file_id = models.CharField(max_length=200)  # Telegram file_id
    file_name = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
```

**Логика:** Ментор создаёт темы (Topic), загружает файлы (Material). Файлы хранятся на серверах Telegram (`file_id`).

### Question (backend/questions/models.py)
```python
class Question(models.Model):
    mentor = models.ForeignKey(Mentor, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    is_answered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
```

**Логика:** Студент отправляет анонимный вопрос. Ментор видит список вопросов и может отметить их как отвеченные.

### Download (backend/downloads/models.py)
```python
class Download(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='downloads')
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='downloads')
    downloaded_at = models.DateTimeField(auto_now_add=True)
```

**Логика:** Отслеживание скачиваний для статистики.

### Quiz (backend/quizzes/models.py)
```python
class Quiz(models.Model):
    mentor = models.ForeignKey(Mentor, on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=200)
    topic = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### QuizQuestion (backend/quizzes/models.py)
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

### QuizAttempt (backend/quizzes/models.py)
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

### QuizAnswer (backend/quizzes/models.py)
```python
class QuizAnswer(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE)
    selected_answer = models.CharField(max_length=1)
    is_correct = models.BooleanField()

    class Meta:
        ordering = ['question__order']
```

**Логика квизов:**
- Ментор загружает .txt файл с вопросами
- Парсер извлекает тему, вопросы, варианты ответов, правильный ответ
- Студент может пройти квиз только ОДИН раз
- После прохождения показывается результат, среднее по группе и разбор всех ответов
- Студент может посмотреть свои ответы позже

---

## Паттерны и архитектура

### 1. Асинхронные вызовы БД

Все Django ORM операции в боте обёрнуты декоратором `@sync_to_async` в файле `bot/db.py`:

```python
from asgiref.sync import sync_to_async

@sync_to_async
def get_mentor_by_telegram_id(telegram_id: int):
    try:
        return Mentor.objects.get(telegram_id=telegram_id, is_active=True)
    except Mentor.DoesNotExist:
        return None
```

**Почему:** aiogram 3.x работает асинхронно, Django ORM — синхронно. `@sync_to_async` запускает синхронный код в отдельном потоке.

### 2. Локализация (3 языка)

Все тексты в `bot/texts.py`:

```python
TEXTS = {
    "ru": {"btn_upload": "📤 Загрузить", ...},
    "qq": {"btn_upload": "📤 Júklew", ...},
    "en": {"btn_upload": "📤 Upload", ...},
}

def t(key: str, lang: str = None, **kwargs) -> str:
    """Возвращает текст по ключу с форматированием"""
    if lang is None:
        lang = DEFAULT_LANG
    text = TEXTS.get(lang, TEXTS[DEFAULT_LANG]).get(key, key)
    return text.format(**kwargs) if kwargs else text
```

**Использование:**
```python
await message.answer(t("welcome_student", lang, name=mentor.name))
```

### 3. Многоязычные кнопки

Обработчики сопоставляют все варианты текста кнопки:

```python
@router.message(F.text.in_(["📤 Загрузить", "📤 Júklew", "📤 Upload"]))
async def upload_start(message: Message, state: FSMContext):
    ...
```

### 4. Клавиатуры с параметром языка

```python
def mentor_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn_upload", lang)), KeyboardButton(text=t("btn_manage", lang))],
            ...
        ],
        resize_keyboard=True
    )
```

### 5. FSM для многошаговых операций

```python
from aiogram.fsm.state import State, StatesGroup

class UploadStates(StatesGroup):
    waiting_topic_name = State()
    waiting_file = State()
    waiting_file_title = State()

# Установка состояния
await state.set_state(UploadStates.waiting_file)

# Обработчик состояния
@router.message(UploadStates.waiting_file, F.document)
async def receive_document(message: Message, state: FSMContext):
    ...

# Очистка состояния
await state.clear()
```

### 6. Регистрация роутеров

В `bot/handlers/__init__.py`:

```python
from .start import router as start_router
from .mentor import router as mentor_router
from .student import router as student_router
from .questions import router as questions_router
from .quiz import router as quiz_router

routers = [
    start_router,
    mentor_router,
    student_router,
    questions_router,
    quiz_router
]
```

В `run_bot.py`:
```python
from bot.handlers import routers

for router in routers:
    dp.include_router(router)
```

---

## Функционал бота

### Меню ментора
- 📤 Загрузить — загрузка файлов в темы
- 📂 Управление — удаление файлов и тем
- 📚 Материалы — просмотр своих материалов
- 📝 Квизы — создание/удаление квизов, просмотр результатов
- 📊 Статистика — количество студентов, скачиваний, популярные материалы
- ❓ Вопросы — просмотр анонимных вопросов от студентов
- 🌐 Язык — смена языка интерфейса

### Меню студента
- 📚 Материалы — скачивание учебных материалов
- 📝 Квизы — прохождение квизов
- ❓ Задать вопрос — отправка анонимного вопроса ментору
- 🌐 Язык — смена языка интерфейса

---

## Формат файла квиза

Ментор загружает .txt файл:

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
```

**Правила парсинга:**
- Первая строка `Тема: XXX` или `Topic: XXX` — название квиза (опционально)
- Вопросы начинаются с номера и точки: `1.`, `2.`
- Варианты: `A)`, `B)`, `C)`, `D)`
- Правильный ответ помечен звёздочкой: `B*)` или `A*)`

---

## Callback Data форматы

```python
# Управление квизами (ментор)
f"quizmanage_{quiz_id}"        # Просмотр результатов
f"quizdelete_{quiz_id}"        # Удаление
f"quizconfirmdelete_{quiz_id}" # Подтверждение удаления

# Квизы (студент)
f"startquiz_{quiz_id}"         # Начать квиз (только если не пройден)
f"viewquiz_{quiz_id}"          # Просмотр результата (если пройден)
f"reviewquiz_{attempt_id}"     # Просмотр ответов

# Ответы на вопросы квиза
f"ans_{attempt_id}_{question_id}_{A|B|C|D}"

# Материалы
f"upload_to_{topic_id}"        # Загрузка в тему
f"manage_{topic_id}"           # Управление темой
f"view_{topic_id}"             # Просмотр темы
f"getfile_{material_id}"       # Скачивание файла
f"delete_{topic_id}_{material_id}"  # Удаление файла
```

---

## Переменные окружения (.env)

```env
BOT_TOKEN=your_telegram_bot_token
DATABASE_URL=sqlite:///db.sqlite3
SECRET_KEY=your_django_secret_key
DEBUG=true
```

**Для продакшна (Heroku):**
```env
DATABASE_URL=postgres://...
DEBUG=false
```

---

## Команды

```bash
# Активация виртуального окружения
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux/Mac

# Запуск бота
python run_bot.py

# Django команды
python manage.py migrate
python manage.py createsuperuser
python manage.py makemigrations <app_name>

# Добавление ментора
python setup_mentor.py
```

---

## Деплой на Heroku

**Procfile:**
```
web: gunicorn backend.core.wsgi:application --bind 0.0.0.0:$PORT
bot: python run_bot.py
```

**runtime.txt:**
```
python-3.11.7
```

---

## Важные правила

1. **Один квиз = одна попытка.** Студент не может пройти квиз повторно.
2. **Все DB функции в `bot/db.py`** должны быть обёрнуты `@sync_to_async`.
3. **Все тексты в 3 языках** — ru, qq (Qaraqalpaq), en.
4. **Кнопки проверяются на все языки** — `F.text.in_(["...", "...", "..."])`.
5. **FSM состояние очищается** при нажатии на меню-кнопки.
6. **Файлы хранятся в Telegram** через `file_id`, не на сервере.

---

## Зависимости (requirements.txt)

```
Django>=4.2
aiogram>=3.10
psycopg2-binary>=2.9
python-dotenv>=1.0
gunicorn>=21.0
dj-database-url>=2.1
whitenoise>=6.6
```

---

## Что можно добавить

- [ ] Уведомления ментору о новых вопросах
- [ ] Экспорт результатов квизов в Excel
- [ ] Расписание занятий
- [ ] Домашние задания с проверкой
- [ ] Рейтинг студентов
- [ ] Отправка материалов в группу
