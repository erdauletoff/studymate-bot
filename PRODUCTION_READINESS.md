# Production Readiness Analysis — StudyMate Bot

**Дата анализа:** 2026-02-01
**Статус:** ⚠️ **НЕ ГОТОВ к продакшену** — требуются критичные доработки

---

## 🔴 КРИТИЧНЫЕ ПРОБЛЕМЫ (блокируют запуск)

### 1. FSM Storage в памяти
**Файл:** `run_bot.py:25`
```python
dp = Dispatcher(storage=MemoryStorage())
```

**Проблема:**
- Все состояния FSM (прохождение квизов, загрузка материалов) теряются при рестарте
- Студент потеряет прогресс квиза при падении бота
- Невозможно горизонтальное масштабирование (несколько инстансов)

**Решение:**
```python
from aiogram.fsm.storage.redis import RedisStorage
storage = RedisStorage.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
dp = Dispatcher(storage=storage)
```

**Требует:** Redis в инфраструктуре

---

### 2. Отсутствие graceful shutdown
**Файл:** `run_bot.py:38-39`

**Проблема:**
- При остановке бота активные запросы обрываются
- Нет flush pending updates
- База данных может остаться в несогласованном состоянии

**Решение:**
```python
import signal

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=storage)

    # Setup handlers...

    async def shutdown(signal, loop):
        logging.info(f"Received exit signal {signal.name}...")
        await dp.stop_polling()
        await bot.session.close()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(s, loop)))

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
```

---

### 3. SQLite в продакшене
**Файл:** `backend/core/settings.py:71`

**Проблема:**
- SQLite не поддерживает concurrent writes
- Блокировки при одновременных запросах от студентов
- Нет репликации/backup механизмов из коробки

**Решение:**
- Использовать PostgreSQL
- `.env`: `DATABASE_URL=postgresql://user:pass@host:5432/dbname`

---

### 4. Отсутствие логирования ошибок
**Файл:** `run_bot.py:18`

**Проблема:**
- Только `logging.basicConfig(level=logging.INFO)`
- Ошибки Telegram API не логируются структурированно
- Невозможно отслеживать проблемы в production

**Решение:**
```python
import logging
import sys

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Aiogram logger
aiogram_logger = logging.getLogger('aiogram')
aiogram_logger.setLevel(logging.WARNING)

# Application logger
app_logger = logging.getLogger('studymate')
app_logger.setLevel(logging.INFO)
```

---

## 🟡 ВЫСОКИЙ ПРИОРИТЕТ (критично для стабильности)

### 5. Отсутствие обработки ошибок в handlers
**Найдено:** 26 try/except в 2 файлах из ~10 handler файлов

**Проблема:**
- Большинство handlers не обрабатывают исключения
- Любая ошибка приведет к краху обработки update
- Пользователь не получит feedback

**Решение:**
Добавить middleware для глобальной обработки ошибок:

```python
# bot/middleware.py
class ErrorHandlerMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        try:
            return await handler(event, data)
        except Exception as e:
            logging.error(f"Error handling update: {e}", exc_info=True)

            user_id = event.from_user.id if hasattr(event, 'from_user') else None
            lang = await get_user_language(user_id) if user_id else 'ru'

            if isinstance(event, Message):
                await event.answer(t("error", lang))
            elif isinstance(event, CallbackQuery):
                await event.answer(t("error", lang), show_alert=True)

            # Отправить уведомление админам
            # await notify_admins(f"Error: {e}")
```

---

### 6. Нет rate limiting
**Проблема:**
- Студент может спамить запросы → перегрузка БД
- Нет защиты от flood
- Telegram API rate limits могут сработать

**Решение:**
```python
from aiogram.utils.chat_action import ChatActionMiddleware
from aiogram.filters import Command

# Throttling middleware
class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate_limit=0.5):
        self.rate_limit = rate_limit
        self.cache = {}

    async def __call__(self, handler, event, data):
        user_id = event.from_user.id
        now = time.time()

        if user_id in self.cache:
            if now - self.cache[user_id] < self.rate_limit:
                return  # Ignore

        self.cache[user_id] = now
        return await handler(event, data)
```

---

### 7. BOT_TOKEN может быть None
**Файл:** `run_bot.py:20-24`

**Проблема:**
```python
BOT_TOKEN = os.getenv('BOT_TOKEN')
# Нет проверки!
bot = Bot(token=BOT_TOKEN)  # Упадет с cryptic error
```

**Решение:**
```python
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")
```

---

### 8. Отсутствие мониторинга и health checks
**Проблема:**
- Невозможно узнать, жив ли бот
- Нет метрик производительности
- Нет alerting при падении

**Решение:**
```python
# Health check endpoint (если используется webhook)
@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow()}

# Metrics (опционально)
from prometheus_client import Counter, Histogram

message_counter = Counter('bot_messages_total', 'Total messages processed')
response_time = Histogram('bot_response_seconds', 'Response time')
```

---

## 🟠 СРЕДНИЙ ПРИОРИТЕТ (важно для продакшена)

### 9. Нет deployment инфраструктуры
**Проблема:**
- Нет Dockerfile
- Нет docker-compose.yml
- Нет CI/CD
- Нет systemd service

**Решение:** Создать deployment файлы (см. раздел ниже)

---

### 10. Нет backup стратегии
**Проблема:**
- База данных может быть утеряна
- Uploaded файлы (file_id) привязаны к боту — при пересоздании бота файлы недоступны

**Решение:**
```bash
# PostgreSQL backup (cron job)
0 3 * * * pg_dump $DATABASE_URL > /backups/db_$(date +\%Y\%m\%d).sql

# File IDs backup
# Telegram file_id persistent, но стоит хранить file_unique_id для миграции
```

---

### 11. Нет переменной окружения для admin контактов
**Проблема:**
- При критических ошибках некуда отправить уведомление

**Решение:**
```python
# .env
ADMIN_TELEGRAM_IDS=123456789,987654321

# Notify admins on critical errors
async def notify_admins(text):
    admin_ids = os.getenv('ADMIN_TELEGRAM_IDS', '').split(',')
    for admin_id in admin_ids:
        try:
            await bot.send_message(int(admin_id), f"⚠️ {text}")
        except:
            pass
```

---

### 12. Middleware проверяет доступ через N API calls
**Файл:** `bot/handlers/start.py:43-44`

**Проблема:**
```python
for mentor in mentors:
    if await check_group_membership(bot, user_id, mentor.group_chat_id):
```

- Последовательные API вызовы ко всем менторам
- Медленно при большом количестве менторов
- Может привести к rate limiting

**Решение:**
- Кэшировать результаты проверки (Redis)
- Или использовать `asyncio.gather()` для параллельных проверок

---

## ✅ ЧТО УЖЕ ХОРОШО

1. ✅ SECRET_KEY требует env переменную
2. ✅ ALLOWED_HOSTS ограничен в production
3. ✅ DEBUG по умолчанию False
4. ✅ Индексы БД добавлены
5. ✅ N+1 запросы оптимизированы
6. ✅ Timezone обрабатывается корректно
7. ✅ PostgreSQL поддержка через DATABASE_URL
8. ✅ Whitenoise для статических файлов

---

## 📋 ЧЕКЛИСТ ДЛЯ ПРОДАКШЕНА

### Обязательно перед запуском:
- [ ] Заменить MemoryStorage на RedisStorage
- [ ] Добавить graceful shutdown
- [ ] Перейти с SQLite на PostgreSQL
- [ ] Добавить проверку BOT_TOKEN
- [ ] Настроить структурированное логирование
- [ ] Добавить error handling middleware
- [ ] Создать Dockerfile и docker-compose
- [ ] Настроить backup БД
- [ ] Добавить health check endpoint (если webhook)
- [ ] Протестировать на staging

### Желательно:
- [ ] Rate limiting / throttling
- [ ] Мониторинг (Prometheus + Grafana)
- [ ] Alerting (при ошибках → Telegram админам)
- [ ] CI/CD pipeline
- [ ] Load testing
- [ ] Документация deployment

---

## 🚀 МИНИМАЛЬНАЯ ГОТОВНОСТЬ К ЗАПУСКУ

Если нужно запустить СРОЧНО (не рекомендуется):

1. **Установить Redis:**
   ```bash
   docker run -d -p 6379:6379 redis:alpine
   ```

2. **Обновить `.env`:**
   ```env
   BOT_TOKEN=your-token
   SECRET_KEY=your-secret
   DATABASE_URL=postgresql://user:pass@host/db
   REDIS_URL=redis://localhost:6379/0
   DEBUG=False
   ALLOWED_HOSTS=your-domain.com
   ADMIN_TELEGRAM_IDS=your-admin-id
   ```

3. **Изменить `run_bot.py`:**
   - RedisStorage вместо MemoryStorage
   - Graceful shutdown
   - Проверка BOT_TOKEN

4. **Запустить:**
   ```bash
   python manage.py migrate
   python run_bot.py
   ```

5. **Мониторить логи:**
   ```bash
   tail -f bot.log
   ```

---

## 💡 РЕКОМЕНДАЦИИ

### Короткий срок (1-2 дня):
1. Исправить критичные проблемы (#1-4)
2. Добавить error handling middleware
3. Создать базовый Dockerfile
4. Настроить PostgreSQL + Redis

### Средний срок (1 неделя):
5. Rate limiting
6. Backup автоматизация
7. Health checks + мониторинг
8. Systemd service или Docker Compose

### Долгосрочно:
9. CI/CD
10. Staging окружение
11. Load testing
12. Observability (metrics, tracing)

---

## ⚖️ ИТОГОВАЯ ОЦЕНКА

| Категория | Оценка | Комментарий |
|-----------|--------|-------------|
| Безопасность | 7/10 | SECRET_KEY OK, но нет rate limiting |
| Надежность | 3/10 | MemoryStorage, нет error handling |
| Производительность | 8/10 | Оптимизирована после фиксов |
| Мониторинг | 1/10 | Минимальное логирование |
| Deployment | 2/10 | Нет Docker, нет CI/CD |
| **ОБЩАЯ** | **4/10** | **Не готов к продакшену** |

---

## 🎯 ВЫВОД

**Бот НЕ готов к production запуску** в текущем состоянии.

**Критичные блокеры:**
1. FSM в памяти → студенты потеряют прогресс квизов
2. SQLite → не выдержит concurrent нагрузку
3. Нет error handling → краши будут незаметны
4. Нет graceful shutdown → потеря данных при рестарте

**Минимальное время подготовки:** 2-3 дня работы для критичных фиксов.

**Рекомендация:** Сначала поднять staging окружение, протестировать под нагрузкой, затем production.
