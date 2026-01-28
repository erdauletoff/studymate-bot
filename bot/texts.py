TEXTS = {
    "ru": {
        # ===== LANGUAGE =====
        "choose_language": "🌐 Выберите язык:",
        "language_changed": "✅ Язык изменён на русский",
        "btn_language": "🌐 Язык",
        
        # ===== START =====
        "welcome_mentor": "👋 Добро пожаловать, {name}!\n\nВы можете загружать и управлять учебными материалами.",
        "welcome_student": "👋 Добро пожаловать в StudyMate!\n\n📚 Ваш ментор: {name}\n\nЗдесь вы можете найти учебные материалы и задать вопросы анонимно.",
        "access_denied": "⛔ Доступ запрещён.\n\nВы должны быть участником группы курса.\nОбратитесь к вашему ментору.",
        
        # ===== MENU BUTTONS =====
        "btn_upload": "📤 Загрузить",
        "btn_manage": "📂 Управление",
        "btn_view": "📚 Материалы",
        "btn_statistics": "📊 Статистика",
        "btn_questions": "❓ Вопросы",
        "btn_lesson_materials": "📚 Материалы",
        "btn_ask_question": "❓ Задать вопрос",
        "btn_cancel": "❌ Отмена",
        
        # ===== UPLOAD =====
        "choose_topic_upload": "📤 Выберите тему для загрузки:",
        "create_new_topic": "➕ Создать тему",
        "enter_topic_name": "📝 Введите название темы (например: HTML, CSS, JavaScript):",
        "topic_created": "✅ Тема «{name}» создана!\n\nТеперь используйте 📤 Загрузить для добавления файлов.",
        "send_file": "📁 Тема: {name}\n\n📎 Отправьте файл (PDF, Word, изображение и т.д.)",
        "file_received": "📝 Файл получен: {name}\n\nВведите название для этого материала:",
        "photo_received": "📝 Фото получено!\n\nВведите название для этого материала:",
        "material_added": "✅ Материал добавлен!\n\n📁 Тема: {topic}\n📄 Название: {title}",
        
        # ===== MANAGE =====
        "no_topics": "📭 Тем пока нет. Используйте 📤 Загрузить для создания.",
        "select_topic_manage": "📂 Выберите тему для управления:",
        "tap_to_delete": "📂 <b>{name}</b>\n\nНажмите на файл для удаления:",
        "no_topics_left": "📭 Тем не осталось.",
        
        # ===== DELETE CONFIRMATION =====
        "confirm_delete_file": "🗑️ <b>Удалить этот файл?</b>\n\n📄 {title}",
        "btn_yes_delete": "✅ Да",
        "btn_no_cancel": "❌ Нет",
        "file_deleted": "✅ Файл удалён!",
        "confirm_delete_topic": "⚠️ <b>Удалить всю тему?</b>\n\n📁 {name}\n📄 {count} файл(ов) будет удалено\n\nЭто действие нельзя отменить!",
        "btn_yes_delete_all": "✅ Да, удалить",
        "topic_deleted": "✅ Тема «{name}» удалена!",
        
        # ===== VIEW MATERIALS =====
        "your_materials": "📚 <b>Ваши материалы:</b>",
        "lesson_materials": "📚 <b>Учебные материалы</b>\n\nВыберите тему:",
        "no_materials": "📭 Материалов пока нет.",
        "no_materials_yet": "📭 Материалов пока нет.\n\nЗагляните позже!",
        "topic_files": "📂 <b>{name}</b>\n\n📄 {count} материал(ов)\n\nНажмите для скачивания:",
        "file_sent": "✅ Отправлено!",
        "file_not_found": "❌ Файл не найден",
        "btn_back": "⬅️ Назад",
        "btn_back_topics": "⬅️ К темам",
        "btn_prev": "◀️",
        "btn_next": "▶️",
        
        # ===== STATISTICS =====
        "statistics": "📊 <b>Статистика</b>\n\n",
        "stats_students": "👥 Учеников: <b>{count}</b>\n",
        "stats_topics": "📁 Тем: <b>{count}</b>\n",
        "stats_materials": "📄 Материалов: <b>{count}</b>\n",
        "stats_questions": "❓ Вопросов: <b>{total}</b>",
        "stats_unanswered": " ({count} без ответа)",
        "stats_active_today": "📈 Активных сегодня: <b>{count}</b>\n",
        "stats_active_week": "📅 Активных за неделю: <b>{count}</b>\n",
        "stats_popular": "\n🔥 <b>Популярные материалы:</b>\n",
        "stats_popular_item": "{num}. {title} — {count} скач.\n",
        
        # ===== QUESTIONS =====
        "write_question": "✏️ Напишите ваш вопрос.\n\nВаше имя НЕ будет показано учителю.",
        "question_sent": "✅ Вопрос отправлен!",
        "cancelled": "❌ Отменено",
        "no_questions": "📭 Новых вопросов нет.\n\nВопросы от учеников появятся здесь.",
        "unanswered_questions": "❓ Вопросов без ответа ({count}):\n\n",
        "anonymous_question": "❓ <b>Анонимный вопрос:</b>\n\n{text}",
        "btn_answered": "✅ Отвечено",
        "marked_answered": "✅ Отмечено!",
        "and_more": "...и ещё {count}.",
        
        # ===== ERRORS =====
        "error": "⚠️ Ошибка. Используйте /start",
        "not_assigned": "⚠️ Вы не привязаны к ментору. Используйте /start",
        
        # ===== MANAGE FILES =====
        "btn_delete_topic": "🗑️ Удалить тему",

        # ===== QUIZZES =====
        "btn_quizzes": "📝 Квизы",
        "no_quizzes": "📭 Квизов пока нет.",
        "select_quiz": "📝 Выберите квиз:",
        "upload_quiz": "📄 Отправьте .txt файл с квизом.",
        "quiz_uploaded": "✅ Квиз «{title}» создан!\n\n📊 Вопросов: {count}",
        "quiz_parse_error": "❌ Ошибка парсинга файла. Проверьте формат.",
        "quiz_question": "❓ <b>Вопрос {current}/{total}</b>\n\n{text}\n\nA) {a}\nB) {b}\nC) {c}\nD) {d}",
        "quiz_finished": "🎉 <b>Квиз завершён!</b>\n\n✅ Ваш результат: <b>{score}/{total}</b>\n📊 Среднее по группе: <b>{avg}</b>",
        "quiz_review_header": "\n\n📋 <b>Ваши ответы:</b>\n",
        "quiz_review_correct": "✅ {num}. {question}\n   Ваш ответ: <b>{answer}</b> ✓\n",
        "quiz_review_wrong": "❌ {num}. {question}\n   Ваш ответ: <b>{answer}</b> | Правильно: <b>{correct}</b>\n",
        "quiz_results": "📊 <b>Результаты: {title}</b>\n\n👥 Прошли: {attempts}\n📈 Средний балл: {avg}\n\n🏆 <b>Топ учеников:</b>\n{top}",
        "quiz_no_attempts": "Ещё никто не прошёл этот квиз.",
        "quiz_your_result": "Ваш результат: {score}/{total}",
        "quiz_not_attempted": "Ещё не пройден",
        "quiz_already_taken": "⚠️ Вы уже проходили этот квиз.\n\nВаш результат: {score}/{total}",
        "quiz_view_answers": "📋 Посмотреть ответы",
        "quiz_time_expired": "⏱ Время вышло",
        "quiz_seconds": "сек.",
        "quiz_in_progress": "⏳ Вы сейчас проходите квиз!\n\nСначала завершите текущий квиз, чтобы получить доступ к другим функциям бота.",
        "btn_upload_quiz": "📤 Загрузить квиз",
        "btn_delete_quiz": "🗑️ Удалить квиз",
        "btn_quiz_results": "📊 Результаты",
        "confirm_delete_quiz": "🗑️ <b>Удалить квиз?</b>\n\n📝 {title}\n❓ {count} вопросов\n\nВсе результаты учеников будут удалены!",
        "quiz_deleted": "✅ Квиз удалён!",
        "quiz_mentor_list": "📝 <b>Ваши квизы:</b>",
        "quiz_item_mentor": "📝 {title} • {questions} вопр. • {attempts} попыток",
        "quiz_item_student": "📝 {title}",
        "quiz_item_student_score": "📝 {title} • {score}/{total}",
    },
    
    "qq": {
        # ===== LANGUAGE =====
        "choose_language": "🌐 Tildi tanlań:",
        "language_changed": "✅ Til qaraqalpaqshaǵa ózgertildi",
        "btn_language": "🌐 Til",

        # ===== START =====
        "welcome_mentor": "👋 Xosh kelipsiz, {name}!\n\nSiz oqıw materialların júklewińiz hám basqarıwıńız múmkin.",
        "welcome_student": "👋 StudyMate'ǵa xosh kelipsiz!\n\n📚 Mentorıńız: {name}\n\nBul jerde oqıw materialların tabıwıńız hám anonim soraw beriwińiz múmkin.",
        "access_denied": "⛔ Kiriw qadaǵan etilgen.\n\nSiz kurs toparınıń aǵzası bolıwıńız kerek.\nMentorińizǵa xabarlasıń.",
        
        # ===== MENU BUTTONS =====
        "btn_upload": "📤 Júklew",
        "btn_manage": "📂 Basqarıw",
        "btn_view": "📚 Materiallar",
        "btn_statistics": "📊 Statistika",
        "btn_questions": "❓ Sorawlar",
        "btn_lesson_materials": "📚 Materiallar",
        "btn_ask_question": "❓ Soraw beriw",
        "btn_cancel": "❌ Biykar etiw",
        
        # ===== UPLOAD =====
        "choose_topic_upload": "📤 Júklew ushın temanı tańlań:",
        "create_new_topic": "➕ Jana tema",
        "enter_topic_name": "📝 Tema atın kirgiziń (máselen: HTML, CSS, JavaScript):",
        "topic_created": "✅ «{name}» teması jaratıldı!\n\nEndi fayllardı qosıw ushın 📤 Júklew knopkasin basıń.",
        "send_file": "📁 Tema: {name}\n\n📎 Fayl jiberiń (PDF, Word, súwret hám t.b.)",
        "file_received": "📝 Fayl qabil etildi: {name}\n\nBul material ushin atama kirgiziń:",
        "photo_received": "📝 Súwret qabıl etildi!\n\nBul material ushın atama kirgiziń:",
        "material_added": "✅ Material qosıldı!\n\n📁 Tema: {topic}\n📄 Atı: {title}",
        
        # ===== MANAGE =====
        "no_topics": "📭 Házirshe temalar joq. Jaratıw ushın 📤 Júklew knopkasin basıń.",
        "select_topic_manage": "📂 Basqarıw ushın temanı tańlań:",
        "tap_to_delete": "📂 <b>{name}</b>\n\nOshırıw ushın fayldı basıń:",
        "no_topics_left": "📭 Temalar qalmadı.",
        
        # ===== DELETE CONFIRMATION =====
        "confirm_delete_file": "🗑️ <b>Bul fayldı óshiresiz be?</b>\n\n📄 {title}",
        "btn_yes_delete": "✅ Awa",
        "btn_no_cancel": "❌ Yaq",
        "file_deleted": "✅ Fayl óshirildi!",
        "confirm_delete_topic": "⚠️ <b>Pútkil temanı óshiresiz be?</b>\n\n📁 {name}\n📄 {count} fayl óshiriledi\n\nBunı qaytarıp bolmaydı!",
        "btn_yes_delete_all": "✅ Awa, óshiriw",
        "topic_deleted": "✅ «{name}» teması óshirildi!",
        
        # ===== VIEW MATERIALS =====
        "your_materials": "📚 <b>Materiallarıńız:</b>",
        "lesson_materials": "📚 <b>Oqiw materialları</b>\n\nTema tanlań:",
        "no_materials": "📭 Házirshe materiallar joq.",
        "no_materials_yet": "📭 Házirshe materiallar joq.\n\nKeyinirek tekseriń!",
        "topic_files": "📂 <b>{name}</b>\n\n📄 {count} material\n\nJúklew ushın basıń:",
        "file_sent": "✅ Jiberildi!",
        "file_not_found": "❌ Fayl tabilmadi",
        "btn_back": "⬅️ Arqaǵa",
        "btn_back_topics": "⬅️ Temalarǵa",
        "btn_prev": "◀️",
        "btn_next": "▶️",
        
        # ===== STATISTICS =====
        "statistics": "📊 <b>Statistika</b>\n\n",
        "stats_students": "👥 Oqıwshılar: <b>{count}</b>\n",
        "stats_topics": "📁 Temalar: <b>{count}</b>\n",
        "stats_materials": "📄 Materiallar: <b>{count}</b>\n",
        "stats_questions": "❓ Sorawlar: <b>{total}</b>",
        "stats_unanswered": " ({count} juwapsız)",
        "stats_active_today": "📈 Búgin aktiv: <b>{count}</b>\n",
        "stats_active_week": "📅 Háptede aktiv: <b>{count}</b>\n",
        "stats_popular": "\n🔥 <b>Kóp tarqalgan materiallar</b>\n",
        "stats_popular_item": "{num}. {title} — {count} júklew\n",
        
        # ===== QUESTIONS =====
        "write_question": "✏️ Sorawıńızdı jazıń.\n\nAtıńız oqıtıwshıǵa KÓRSETILMEYDI",
        "question_sent": "✅ Soraw jiberildi!",
        "cancelled": "❌ Biykar etildi",
        "no_questions": "📭 Jańa sorawlar joq.\n\nOqıwshılardan sorawlar usı jerde payda boladı.",
        "unanswered_questions": "❓ Juwap berilmegen sorawlar ({count}):\n\n",
        "anonymous_question": "❓ <b>Anonim soraw:</b>\n\n{text}",
        "btn_answered": "✅ Juwap berildi",
        "marked_answered": "✅ Belgilendi!",
        "and_more": "...hám jáne {count}.",
        
        # ===== ERRORS =====
        "error": "⚠️ Qátelik. /start buyrıgın paydalanıń",
        "not_assigned": "⚠️ Siz mentorǵa biriktirilmegensiz. /start buyrıgın paydalanıń",
        
        # ===== MANAGE FILES =====
        "btn_delete_topic": "🗑️ Temani óshiriw",

        # ===== QUIZZES =====
        "btn_quizzes": "📝 Kvizler",
        "no_quizzes": "📭 Házirshe kvizler joq.",
        "select_quiz": "📝 Kvizdi tańlań:",
        "upload_quiz": "📄 Kviz menen .txt fayl jiberiń.",
        "quiz_uploaded": "✅ «{title}» kvizi jaratıldı!\n\n📊 Sorawlar: {count}",
        "quiz_parse_error": "❌ Fayl parsingi qátesi. Formatın tekseriń.",
        "quiz_question": "❓ <b>Soraw {current}/{total}</b>\n\n{text}\n\nA) {a}\nB) {b}\nC) {c}\nD) {d}",
        "quiz_finished": "🎉 <b>Kviz tamam boldı!</b>\n\n✅ Nátiyjeńiz: <b>{score}/{total}</b>\n📊 Ortasha ball: <b>{avg}</b>",
        "quiz_review_header": "\n\n📋 <b>Juwaplarıńız:</b>\n",
        "quiz_review_correct": "✅ {num}. {question}\n   Juwabıńız: <b>{answer}</b> ✓\n",
        "quiz_review_wrong": "❌ {num}. {question}\n   Juwabıńız: <b>{answer}</b> | Durıs: <b>{correct}</b>\n",
        "quiz_results": "📊 <b>Nátiyje: {title}</b>\n\n👥 Ótkenler: {attempts}\n📈 Ortasha ball: {avg}\n\n🏆 <b>Top oqıwshılar:</b>\n{top}",
        "quiz_no_attempts": "Házirshe heshkim bul kvizdi ótpedi.",
        "quiz_your_result": "Nátiyjeńiz: {score}/{total}",
        "quiz_not_attempted": "Házirshe ótilmegen",
        "quiz_already_taken": "⚠️ Siz bul kvizdi álle qashan óttińiz.\n\nNátiyjeńiz: {score}/{total}",
        "quiz_view_answers": "📋 Juwaplardı kóriw",
        "quiz_time_expired": "⏱ Waqıt bitti",
        "quiz_seconds": "sek.",
        "quiz_in_progress": "⏳ Siz házir kviz ótip atırsız!\n\nBottıń basqa funkciyalarınan paydalanıw ushın házirgi kvizdi juwmaqlań.",
        "btn_upload_quiz": "📤 Kviz júklew",
        "btn_delete_quiz": "🗑️ Kvizdi óshiriw",
        "btn_quiz_results": "📊 Nátiyje",
        "confirm_delete_quiz": "🗑️ <b>Kvizdi óshiresiz be?</b>\n\n📝 {title}\n❓ {count} soraw\n\nBarlıq nátijeler óshiriledi!",
        "quiz_deleted": "✅ Kviz óshirildi!",
        "quiz_mentor_list": "📝 <b>Sizdiń kvizler:</b>",
        "quiz_item_mentor": "📝 {title} • {questions} soraw • {attempts} talaban",
        "quiz_item_student": "📝 {title}",
        "quiz_item_student_score": "📝 {title} • {score}/{total}",
    },
    
    "en": {
        # ===== LANGUAGE =====
        "choose_language": "🌐 Choose language:",
        "language_changed": "✅ Language changed to English",
        "btn_language": "🌐 Language",

        # ===== START =====
        "welcome_mentor": "👋 Welcome, {name}!\n\nYou can upload and manage lesson materials.",
        "welcome_student": "👋 Welcome to StudyMate!\n\n📚 Your mentor: {name}\n\nHere you can find lesson materials and ask questions anonymously.",
        "access_denied": "⛔ Access denied.\n\nYou must be a member of a course group.\nContact your mentor.",
        
        # ===== MENU BUTTONS =====
        "btn_upload": "📤 Upload",
        "btn_manage": "📂 Manage",
        "btn_view": "📚 Materials",
        "btn_statistics": "📊 Statistics",
        "btn_questions": "❓ Questions",
        "btn_lesson_materials": "📚 Materials",
        "btn_ask_question": "❓ Ask Question",
        "btn_cancel": "❌ Cancel",
        
        # ===== UPLOAD =====
        "choose_topic_upload": "📤 Choose topic for upload:",
        "create_new_topic": "➕ New Topic",
        "enter_topic_name": "📝 Enter topic name (e.g., HTML, CSS, JavaScript):",
        "topic_created": "✅ Topic '{name}' created!\n\nNow use 📤 Upload to add files.",
        "send_file": "📁 Topic: {name}\n\n📎 Send a file (PDF, Word, image, etc.)",
        "file_received": "📝 File received: {name}\n\nEnter a title for this material:",
        "photo_received": "📝 Photo received!\n\nEnter a title for this material:",
        "material_added": "✅ Material added!\n\n📁 Topic: {topic}\n📄 Title: {title}",
        
        # ===== MANAGE =====
        "no_topics": "📭 No topics yet. Use 📤 Upload to create one.",
        "select_topic_manage": "📂 Select topic to manage:",
        "tap_to_delete": "📂 <b>{name}</b>\n\nTap on file to delete:",
        "no_topics_left": "📭 No topics left.",
        
        # ===== DELETE CONFIRMATION =====
        "confirm_delete_file": "🗑️ <b>Delete this file?</b>\n\n📄 {title}",
        "btn_yes_delete": "✅ Yes",
        "btn_no_cancel": "❌ No",
        "file_deleted": "✅ File deleted!",
        "confirm_delete_topic": "⚠️ <b>Delete entire topic?</b>\n\n📁 {name}\n📄 {count} file(s) will be deleted\n\nThis cannot be undone!",
        "btn_yes_delete_all": "✅ Yes, delete",
        "topic_deleted": "✅ Topic '{name}' deleted!",
        
        # ===== VIEW MATERIALS =====
        "your_materials": "📚 <b>Your materials:</b>",
        "lesson_materials": "📚 <b>Lesson Materials</b>\n\nSelect a topic:",
        "no_materials": "📭 No materials yet.",
        "no_materials_yet": "📭 No materials yet.\n\nCheck back later!",
        "topic_files": "📂 <b>{name}</b>\n\n📄 {count} material(s)\n\nTap to download:",
        "file_sent": "✅ Sent!",
        "file_not_found": "❌ File not found",
        "btn_back": "⬅️ Back",
        "btn_back_topics": "⬅️ To Topics",
        "btn_prev": "◀️",
        "btn_next": "▶️",
        
        # ===== STATISTICS =====
        "statistics": "📊 <b>Statistics</b>\n\n",
        "stats_students": "👥 Students: <b>{count}</b>\n",
        "stats_topics": "📁 Topics: <b>{count}</b>\n",
        "stats_materials": "📄 Materials: <b>{count}</b>\n",
        "stats_questions": "❓ Questions: <b>{total}</b>",
        "stats_unanswered": " ({count} unanswered)",
        "stats_active_today": "📈 Active today: <b>{count}</b>\n",
        "stats_active_week": "📅 Active this week: <b>{count}</b>\n",
        "stats_popular": "\n🔥 <b>Popular materials:</b>\n",
        "stats_popular_item": "{num}. {title} — {count} downloads\n",
        
        # ===== QUESTIONS =====
        "write_question": "✏️ Write your question.\n\nYour name will NOT be shown to the teacher.",
        "question_sent": "✅ Question sent!",
        "cancelled": "❌ Cancelled",
        "no_questions": "📭 No new questions.\n\nQuestions from students will appear here.",
        "unanswered_questions": "❓ Unanswered questions ({count}):\n\n",
        "anonymous_question": "❓ <b>Anonymous question:</b>\n\n{text}",
        "btn_answered": "✅ Answered",
        "marked_answered": "✅ Marked!",
        "and_more": "...and {count} more.",
        
        # ===== ERRORS =====
        "error": "⚠️ Error. Use /start",
        "not_assigned": "⚠️ You are not assigned to a mentor. Use /start",
        
        # ===== MANAGE FILES =====
        "btn_delete_topic": "🗑️ Delete Topic",

        # ===== QUIZZES =====
        "btn_quizzes": "📝 Quizzes",
        "no_quizzes": "📭 No quizzes yet.",
        "select_quiz": "📝 Select a quiz:",
        "upload_quiz": "📄 Send a .txt file with the quiz.",
        "quiz_uploaded": "✅ Quiz '{title}' created!\n\n📊 Questions: {count}",
        "quiz_parse_error": "❌ File parsing error. Check the format.",
        "quiz_question": "❓ <b>Question {current}/{total}</b>\n\n{text}\n\nA) {a}\nB) {b}\nC) {c}\nD) {d}",
        "quiz_finished": "🎉 <b>Quiz completed!</b>\n\n✅ Your result: <b>{score}/{total}</b>\n📊 Group average: <b>{avg}</b>",
        "quiz_review_header": "\n\n📋 <b>Your answers:</b>\n",
        "quiz_review_correct": "✅ {num}. {question}\n   Your answer: <b>{answer}</b> ✓\n",
        "quiz_review_wrong": "❌ {num}. {question}\n   Your answer: <b>{answer}</b> | Correct: <b>{correct}</b>\n",
        "quiz_results": "📊 <b>Results: {title}</b>\n\n👥 Completed: {attempts}\n📈 Average score: {avg}\n\n🏆 <b>Top students:</b>\n{top}",
        "quiz_no_attempts": "No one has taken this quiz yet.",
        "quiz_your_result": "Your result: {score}/{total}",
        "quiz_not_attempted": "Not attempted yet",
        "quiz_already_taken": "⚠️ You have already taken this quiz.\n\nYour result: {score}/{total}",
        "quiz_view_answers": "📋 View answers",
        "quiz_time_expired": "⏱ Time expired",
        "quiz_seconds": "sec.",
        "quiz_in_progress": "⏳ You are currently taking a quiz!\n\nPlease finish the current quiz to access other bot functions.",
        "btn_upload_quiz": "📤 Upload Quiz",
        "btn_delete_quiz": "🗑️ Delete Quiz",
        "btn_quiz_results": "📊 Results",
        "confirm_delete_quiz": "🗑️ <b>Delete quiz?</b>\n\n📝 {title}\n❓ {count} questions\n\nAll student results will be deleted!",
        "quiz_deleted": "✅ Quiz deleted!",
        "quiz_mentor_list": "📝 <b>Your quizzes:</b>",
        "quiz_item_mentor": "📝 {title} • {questions} q. • {attempts} attempts",
        "quiz_item_student": "📝 {title}",
        "quiz_item_student_score": "📝 {title} • {score}/{total}",
    },
}

DEFAULT_LANG = "qq"


def t(key: str, lang: str = None, **kwargs) -> str:
    """Get text by key with optional formatting"""
    if lang is None:
        lang = DEFAULT_LANG
    text = TEXTS.get(lang, TEXTS[DEFAULT_LANG]).get(key, key)
    return text.format(**kwargs) if kwargs else text
