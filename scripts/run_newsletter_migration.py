"""Apply newsletter DB migration to Supabase."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import psycopg2

def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    sql_path = Path(__file__).resolve().parent.parent / "sql" / "migrate_newsletters.sql"
    sql = sql_path.read_text()

    print("Connecting to Supabase...")
    conn = psycopg2.connect(db_url, sslmode="require", connect_timeout=30)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print("Migration applied: newsletters + newsletter_insights tables created.")

        # Verify
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM newsletters")
            print(f"newsletters table: {cur.fetchone()[0]} rows")
            cur.execute("SELECT COUNT(*) FROM newsletter_insights")
            print(f"newsletter_insights table: {cur.fetchone()[0]} rows")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
