"""SQLite 连接、初始化与最小命令行入口。"""

from __future__ import annotations

import argparse
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "game_ops.db"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect_db(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """打开启用外键约束的短生命周期连接。"""

    path = Path(db_path).expanduser().resolve()
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


@contextmanager
def db_session(db_path: str | Path = DEFAULT_DB_PATH) -> Iterator[sqlite3.Connection]:
    """提供自动提交/回滚并确保关闭的 SQLite 会话。"""

    connection = connect_db(db_path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> Path:
    """创建数据库并幂等应用当前 Schema。"""

    path = Path(db_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with db_session(path) as connection:
        has_migrations = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
        ).fetchone()
        had_fts_migration = bool(
            has_migrations
            and connection.execute(
                "SELECT 1 FROM schema_migrations WHERE version = 2"
            ).fetchone()
        )
        connection.executescript(schema)
        if not had_fts_migration:
            connection.execute("INSERT INTO comments_fts(comments_fts) VALUES ('rebuild')")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="初始化可选的本地 SQLite 数据层。")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init", help="创建或更新数据库 Schema。")
    init_parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args()

    if args.command == "init":
        print(f"SQLite data store ready: {init_db(args.db)}")


if __name__ == "__main__":
    main()
