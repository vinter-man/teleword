"""`python -m teleword.db` creates the schema. Run once before the bot and the API start."""

import asyncio
import logging

from teleword.config import get_settings
from teleword.db.session import create_engine, init_db


async def main() -> None:
    engine = create_engine(get_settings().database_url)
    await init_db(engine)
    await engine.dispose()
    logging.getLogger(__name__).info("Database schema is up to date")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
