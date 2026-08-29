from pathlib import Path

import psycopg

from revenueflow.config import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"

CREATE_TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
)
"""


def setup_checkpointer(database_url: str) -> None:
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
    except ImportError:
        print("langgraph not installed; skipping checkpoint setup")
        return
    with PostgresSaver.from_conn_string(database_url) as saver:
        saver.setup()
    print("langgraph checkpoint tables ready")


def main() -> int:
    settings = get_settings()
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_TRACKING_TABLE)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT version FROM schema_migrations")
            applied = {row[0] for row in cur.fetchall()}

        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = path.stem
            if version in applied:
                continue
            with conn.cursor() as cur:
                cur.execute(path.read_text(encoding="utf-8"))
                cur.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)",
                    (version,),
                )
            conn.commit()
            print(f"applied {version}")

    setup_checkpointer(settings.database_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
