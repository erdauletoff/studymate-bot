# CLAUDE.md
## Ranked / Practice Quiz System — Implementation Notes

### Context
Currently all quizzes are homogeneous:
- all attempts affect leaderboard
- correct answers are always shown after completion

Goal: introduce **Ranked** and **Practice** quiz modes without background jobs or complex scheduling, and define a mentor-friendly quiz upload workflow in the bot.

---

## Quiz Types

### Ranked
- Exam-style quiz
- Affects leaderboard
- Limited availability window
- Correct answers hidden until window ends

### Practice
- Training quiz
- Unlimited attempts
- Does NOT affect leaderboard
- Correct answers always visible

---

## Core Rules

### Ranked Quiz
- `quiz_type = 'ranked'`
- Has `available_until`
- **Only 1 attempt allowed**
- Attempt is valid only if `now < quiz.available_until`
- After completion (during active window):
  - show only final score: `X / Y`
  - do NOT show correct answers
  - do NOT show per-question breakdown

### Practice Quiz
- `quiz_type = 'practice'`
- Always available
- Unlimited attempts
- After completion:
  - show final score
  - show each question
  - show student's answer + correct answer

---

## Auto Conversion (Variant A — No background jobs)

Quiz type in DB is NOT changed.

Effective mode is calculated dynamically:

```python
is_exam_mode =
    quiz.quiz_type == 'ranked'
    and now < quiz.available_until

is_practice_mode =
    quiz.quiz_type == 'practice'
    or (quiz.quiz_type == 'ranked' and now >= quiz.available_until)
```

- While `is_exam_mode == True` → Ranked behavior (exam mode)
- After `available_until` → quiz automatically behaves as Practice (review mode)
- Quiz lists must NOT rely only on `quiz_type`
- Use effective mode instead

---

## Attempts Logic

### Ranked
- `max_attempts = 1`
- Attempt allowed only while `now < quiz.available_until`
- Attempt data (answers) is stored but not shown during exam mode

### Practice
- Unlimited attempts
- Always allowed

---

## Leaderboard Logic

Only Ranked attempts are counted.

An attempt is included in leaderboard **iff**:

```python
quiz.quiz_type == 'ranked'
and attempt.created_at < quiz.available_until
```

Practice attempts are ignored completely.

---

## Data Storage Principle

- Student answers are ALWAYS stored
- UI decides what to show based on effective mode
- Ranked hides answers, Practice reveals them

---

## Minimal Required Fields

### Quiz
- `quiz_type` (`ranked` | `practice`)
- `available_from` (optional)
- `available_until` (required for ranked)
- `max_attempts` (ranked = 1)
- `is_active` (or `status`) to control visibility to students

### Attempt
- `created_at`
- `score`
- `answers` (full per-question data)

---

## UI / Menu Visibility Logic (IMPORTANT)

When using Variant A (no DB type change):

- `quiz.quiz_type == 'ranked'` remains unchanged in the database
- No physical conversion happens
- Behavior and visibility are controlled by time-based logic only

### Effective behavior
- Before `available_until`:
  - quiz behaves as **Ranked (exam mode)**
  - affects leaderboard
  - visible in 🏆 Ranked section
- After `available_until`:
  - quiz behaves as **Practice (review mode)**
  - does NOT affect leaderboard
  - correct answers become visible
  - visible in 📚 Practice section

### Menu visibility rules
Quiz lists must NOT rely only on `quiz_type`.

Use effective mode instead:

```python
def is_visible_as_ranked(quiz, now):
    return (
        quiz.quiz_type == 'ranked'
        and now < quiz.available_until
    )

def is_visible_as_practice(quiz, now):
    return (
        quiz.quiz_type == 'practice'
        or (
            quiz.quiz_type == 'ranked'
            and now >= quiz.available_until
        )
    )
```

### UX principle
- Ranked section shows only currently active exams
- Practice section includes:
  - all practice quizzes
  - all expired ranked quizzes

From the student's perspective:
> "This quiz was an exam, now it is a training quiz."

### Key rule
Never use `quiz_type` alone for UI filtering. Always combine it with time-based availability.

---

# Mentor Quiz Upload & Publishing Flow (Bot UX)

## Goal
Make quiz creation in the bot safe and convenient for mentors:
- prevent accidental publishing of broken/incorrect files
- allow scheduling ranked quizzes without background jobs
- support preparing quizzes in advance

This workflow assumes quizzes can be uploaded as `.txt` and parsed by an existing parser.

---

## Recommended Mentor Flow (Draft → Preview → Publish)

### Step 1 — Upload (Draft)
Mentor action: choose menu item “📤 Upload quiz” and send a `.txt` document.
Bot behavior:
- parse the file
- if parsing fails → show errors and cancel
- if parsing succeeds → store as **draft** (not visible to students yet)

### Step 2 — Preview / Confirm
Bot shows a short preview:
- quiz title/topic
- number of questions
- 1–2 sample questions (optional)
Mentor chooses:
- ✅ Save / Continue
- ❌ Cancel

### Step 3 — Choose publishing mode
After confirmation, mentor chooses one of:
- 📚 Publish as Practice (available immediately, unlimited attempts, no leaderboard)
- 🏆 Publish as Ranked (48h exam window, 1 attempt, affects leaderboard)
- 🗃 Keep as Draft (mentor can publish later)

---

## Ranked Scheduling UX (simple)
When mentor selects 🏆 Ranked:
- Bot asks: “Start now?”
  - ✅ Start now
  - 🗓 Choose start time (simple text input like `30.01 18:00`)

Rules:
- If start now:
  - `available_from = now`
  - `available_until = now + 48h`
- If scheduled start:
  - `available_from = parsed_start`
  - `available_until = available_from + 48h`

Ranked config:
- `quiz_type='ranked'`
- `max_attempts=1`
- `is_active=True`

---

## Student Visibility (ties to Variant A)
- 🏆 Ranked list shows only ranked quizzes where `now < available_until` (active exam window).
- 📚 Practice list shows:
  - all `practice` quizzes
  - all `ranked` quizzes where `now >= available_until` (expired ranked → review mode)

This achieves: “exam first, review later” without changing `quiz_type` in DB.

---

## Minimal Implementation Notes (Bot)
Recommended FSM states (or equivalent) for mentor upload:
- `waiting_quiz_file` → receive `.txt`
- `waiting_quiz_confirm` → preview + confirm
- `waiting_publish_mode` → choose Practice / Ranked / Draft
- optional `waiting_ranked_start_time` → parse start datetime

Key behaviors:
- always store full question/answer data on upload
- during ranked exam window, hide correct answers in student result UI
- after window ends, show full review UI (same as practice)

---

## Key Principle
**Ranked = exam. Practice = analysis.  
Data is preserved, visibility is conditional.**
