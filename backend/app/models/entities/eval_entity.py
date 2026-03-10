from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class EvalEntity:
    id: str
    dataset_size: int
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float
    overall_score: float
    status: str
    created_at: datetime
