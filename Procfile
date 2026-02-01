release: python manage.py migrate --noinput
web: gunicorn backend.core.wsgi --log-file -
worker: python run_bot.py
