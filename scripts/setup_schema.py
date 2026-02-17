"""
Manually create schema and tables in PostgreSQL.

This is a workaround for schema configuration issues during app startup.
"""
import asyncio
import asyncpg
import os
from pathlib import Path


async def main():
    # Read connection details from environment
    host = os.getenv("PGHOST")
    port = os.getenv("PGPORT", "5432")
    database = os.getenv("PGDATABASE")
    user = os.getenv("PGUSER")
    password = os.getenv("PGPASSWORD")

    if not all([host, database, user]):
        print("Error: Missing database connection environment variables")
        print(f"PGHOST: {host}")
        print(f"PGDATABASE: {database}")
        print(f"PGUSER: {user}")
        print("\nFor Databricks Apps, get these from the app logs")
        return

    # Read SQL file
    sql_file = Path(__file__).parent / "create_schema.sql"
    with open(sql_file) as f:
        sql = f.read()

    print(f"Connecting to {host}:{port}/{database} as {user}...")

    # Connect and execute
    try:
        conn = await asyncpg.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
        )

        print("Connected successfully")
        print("Executing schema creation SQL...")

        await conn.execute(sql)

        print("✅ Schema and tables created successfully!")

        await conn.close()

    except Exception as e:
        print(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
