#!/usr/bin/env python
from src.db.schema import create_schema
from src.db.connection import test_connection


def main() -> None:
    print("🔌 Testing database connection...")
    test_connection()
    print("✅ Connection OK")

    print("🗄️  Creating schema (Timescale hypertables + indexes)...")
    create_schema()
    print("✅ Schema created")


if __name__ == "__main__":
    main()
