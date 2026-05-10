from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import create_engine

DB_PATH = "database.db"


engine = create_async_engine(
    url=f"sqlite:///{DB_PATH}",
    echo=True,
)

session_factory = async_sessionmaker(engine)


class Base(DeclarativeBase):
    pass
