from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.core.config import get_settings
from app.repositories.sqlite_repo import SqliteRepo


def main() -> None:
    settings = get_settings()
    repo = SqliteRepo(settings.sqlite.path)
    repo.init_schema()
    print(f"SQLite schema initialized: {settings.sqlite.path}")


if __name__ == "__main__":
    main()
