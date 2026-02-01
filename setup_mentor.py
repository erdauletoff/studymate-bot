import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.core.settings')
django.setup()

from backend.mentors.models import Mentor

mentor, created = Mentor.objects.get_or_create(
    telegram_id=5871171104,
    defaults={
        'name': 'Darkhan',
        'group_chat_id': -1003686154949,
    }
)

if created:
    print(f"✅ Mentor '{mentor.name}' created!")
else:
    print(f"ℹ️ Mentor already exists.")
