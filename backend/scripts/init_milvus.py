import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.core.config import get_settings
from app.repositories.milvus_repo import MilvusRepo


def parse_args():
    parser = argparse.ArgumentParser(description="Initialize Milvus collection for rag_sth.")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop existing collection then recreate it (development only).",
    )
    parser.add_argument(
        "--no-sparse",
        action="store_true",
        help="Create collection without sparse_vector field.",
    )
    parser.add_argument(
        "--collection",
        type=str,
        default="",
        help="Only init one collection; default initializes all configured collections.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    try:
        target_collections = [args.collection] if args.collection else settings.milvus.collections
        enable_sparse = settings.milvus.enable_sparse and (not args.no_sparse)
        for name in target_collections:
            current_repo = MilvusRepo(
                host=settings.milvus.host,
                port=settings.milvus.port,
                collection_name=name,
            )
            if args.recreate:
                current_repo.drop_collection()
                print(f"Dropped collection: {name}")
            current_repo.ensure_collection(dim=settings.embedding_api.dim, enable_sparse=enable_sparse)
            print(f"Milvus collection ready: {name}")
        print(f"Config: enable_sparse={enable_sparse}, dim={settings.embedding_api.dim}, total={len(target_collections)}")
    except Exception as exc:  # noqa: BLE001
        print("Milvus init failed.")
        print(f"Target: {settings.milvus.host}:{settings.milvus.port}")
        print("Please check:")
        print("1) backend/.env 的 MILVUS_HOST/MILVUS_PORT 是否正确")
        print("2) Milvus 服务是否已启动并可从当前机器访问")
        print("3) 防火墙/安全组是否放通 19530")
        print(f"Original error: {exc}")
        raise


if __name__ == "__main__":
    main()
