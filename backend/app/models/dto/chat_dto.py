from pydantic import BaseModel


class ChatRequest(BaseModel):
    question: str


class ChatCitation(BaseModel):
    ref: str
    snippet: str
    score: float | None = None


class ChatFinalEvent(BaseModel):
    answer: str
    is_refused: bool
    top1_score: float
    citations: list[ChatCitation]
