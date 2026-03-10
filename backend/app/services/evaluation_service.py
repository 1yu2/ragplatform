from __future__ import annotations

import uuid
from datetime import datetime, timezone


class EvaluationService:
    def __init__(self, sqlite_repo):
        self.sqlite_repo = sqlite_repo

    def run_once(self, dataset_size: int = 50) -> dict:
        # MVP 占位实现：先跑通评估链路，后续替换为真实 RAGAS 计算。
        result = {
            "id": str(uuid.uuid4()),
            "dataset_size": dataset_size,
            "faithfulness": 0.76,
            "answer_relevancy": 0.74,
            "context_precision": 0.68,
            "context_recall": 0.73,
            "overall_score": 74.0,
            "status": "SUCCESS",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.sqlite_repo.insert_evaluation(result)
        return result

    def latest(self) -> dict | None:
        return self.sqlite_repo.latest_evaluation()

    def history(self, limit: int = 50) -> list[dict]:
        return self.sqlite_repo.list_evaluations(limit=limit)
