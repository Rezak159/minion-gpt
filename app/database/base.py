from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DB_PATH = "database.db"


engine = create_async_engine(
    url=f"sqlite+aiosqlite:///{DB_PATH}",
    echo=True,
)

session_factory = async_sessionmaker(engine)


class Base(DeclarativeBase):
    pass


class BaseStorage:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
