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
