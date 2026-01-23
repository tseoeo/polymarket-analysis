#!/usr/bin/env python3
"""Initialize database tables."""

import asyncio
import sys
sys.path.insert(0, "backend")

from database import init_db


async def main():
    print("Initializing database...")
    await init_db()
    print("Database initialized successfully!")


if __name__ == "__main__":
    asyncio.run(main())
