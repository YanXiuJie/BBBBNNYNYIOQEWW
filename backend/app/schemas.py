from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class ClassRequest(BaseModel):
    name: str
    year_level: int = 5
    section: str


class ChapterRequest(BaseModel):
    number: int
    title_ms: str


class SubtopicRequest(BaseModel):
    chapter_id: int
    title_ms: str
    activity_type: str = "lesson"


class StudentRequest(BaseModel):
    username: str
    password: str = "password123"
    full_name: str
    parent_email: str | None = None
    class_id: int


class AttemptRequest(BaseModel):
    question_id: int
    answer_text: str = Field(min_length=1)
    time_seconds: int = Field(ge=1, le=1800)


class DiagnosticSubmissionRequest(BaseModel):
    answers: list[AttemptRequest] = Field(min_length=1)


class DiagnosticStartResponse(BaseModel):
    session_id: int
    status: str
    total_questions: int
    chapters: list[dict]


class DiagnosticAnswerSubmitRequest(BaseModel):
    session_id: int
    question_id: int
    answer_text: str = Field(min_length=1)
    time_seconds: int = Field(ge=1, le=1800)


class QuestionRequest(BaseModel):
    chapter_id: int
    subtopic_id: int
    difficulty: str
    question_type: str = "short_answer"
    prompt_ms: str
    expected_answer: str
    options: list[str] = Field(default_factory=list)
    explanation_ms: str
    hint_ms: str = ""
    hint_level2_ms: str = ""
    hint_level3_ms: str = ""


class GenerateQuestionRequest(BaseModel):
    chapter_id: int
    subtopic_id: int
    difficulty: str
    question_type: str = "short_answer"


class ComprehensivePracticeStartResponse(BaseModel):
    session_id: int
    total_questions: int
    weak_subtopics: list[dict]
    message: str


class ComprehensiveQuestionResponse(BaseModel):
    session_id: int
    question_number: int
    phase: str
    phase_info: dict
    question: dict
    hint_config: dict


class ComprehensiveSubmitRequest(BaseModel):
    session_id: int
    question_id: int
    answer_text: str = Field(min_length=1)
    time_seconds: int
    hints_used: list[str] = []


class ComprehensiveSubmitResponse(BaseModel):
    is_correct: bool
    feedback_ms: str
    mastery_updated: dict
