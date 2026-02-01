#!/usr/bin/env python3
"""
Diagnostic script to check bot configuration and mentor setup
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.core.settings')
django.setup()

from backend.mentors.models import Mentor
from backend.students.models import Student

print("=" * 60)
print("StudyMate Bot - Configuration Check")
print("=" * 60)

# Check mentors
mentors = Mentor.objects.all()
print(f"\nTotal Mentors: {mentors.count()}")

for mentor in mentors:
    print(f"\n🎓 Mentor: {mentor.name}")
    print(f"   Telegram ID: {mentor.telegram_id}")
    print(f"   Group Chat ID: {mentor.group_chat_id}")
    print(f"   Active: {mentor.is_active}")
    print(f"   Language: {mentor.language}")

    # Count students
    students = Student.objects.filter(mentor=mentor)
    print(f"   Students: {students.count()}")

    # Validate group_chat_id format
    if mentor.group_chat_id:
        if mentor.group_chat_id > 0:
            print(f"   ⚠️  WARNING: Group Chat ID should be negative!")
            print(f"      Telegram group IDs are always negative numbers")
            print(f"      Current value: {mentor.group_chat_id}")
            print(f"      Expected format: -{mentor.group_chat_id}")
    else:
        print(f"   ❌ ERROR: Group Chat ID is not set!")

print("\n" + "=" * 60)
print("Students:")
print("=" * 60)

students = Student.objects.all()
print(f"Total Students: {students.count()}\n")

for student in students:
    print(f"👤 {student.first_name} {student.last_name}")
    print(f"   Telegram ID: {student.telegram_id}")
    print(f"   Username: @{student.username or 'no username'}")
    print(f"   Mentor: {student.mentor.name if student.mentor else 'NONE (❌ Not assigned!)'}")
    print()

print("=" * 60)
print("\nHow to get Group Chat ID:")
print("1. Add @RawDataBot to your mentor's group")
print("2. Send any message to the group")
print("3. @RawDataBot will reply with chat info")
print("4. Look for 'chat' -> 'id' (it should be a NEGATIVE number)")
print("5. Update mentor's group_chat_id in Django admin")
print("\nHow to make bot admin in group:")
print("1. Add your bot to the group")
print("2. Click group name → Administrators → Add Administrator")
print("3. Add your bot")
print("4. Bot needs permission to see members")
print("=" * 60)
