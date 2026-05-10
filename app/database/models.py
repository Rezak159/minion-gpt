from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey, func, BigInteger
from .base import Base

import enum
import datetime
from typing import Annotated

created_at = Annotated[datetime.datetime, mapped_column(server_default=func.now())]
updated_at = Annotated[
    datetime.datetime, mapped_column(server_default=func.now(), onupdate=func.now())
]


class User_Tariffs(enum.Enum):
    free = "free"
    pro = "pro"
    ultra = "ultra"


class UsersTable(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None]
    tariff_plan: Mapped[User_Tariffs] = mapped_column(default=User_Tariffs.free)
    requests_today: Mapped[int] = mapped_column(default=0)
    total_requests: Mapped[int] = mapped_column(default=0)
    limits_updated_at: Mapped[updated_at]
    subscription_expires_at: Mapped[datetime.datetime | None]
    registred_at: Mapped[created_at]


class MessagesTable(Base):
    __tablename__ = "messages"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id"),
        primary_key=True,
    )
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    thread_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        default=0,
    )
    messages: Mapped[str]
