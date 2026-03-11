from __future__ import annotations

import logging
import os
from pathlib import Path


def setup_logging(log_file: str = "logs/app.log") -> None:
    path = Path(log_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(path, encoding="utf-8"),
        ],
    )
