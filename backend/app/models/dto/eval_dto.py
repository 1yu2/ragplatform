from datetime import datetime

from pydantic import BaseModel


class EvaluationRecord(BaseModel):
    id: str
    dataset_size: int
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float
    overall_score: float
    status: str
    created_at: datetime
