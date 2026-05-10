import json
import logging

from database.database import engine, session_factory, Base

from database.models import UsersTable


def create_tables():
    # engine.echo = False
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    print(Base.metadata.tables)
    # engine.echo = True


def save_history(
    self,
    user_id: int,
    chat_id: int,
    thread_id: int,
    messages: list,
):

    messages_json = json.dumps(messages, ensure_ascii=False)

    maria = UsersTable(
        user_id=user_id,
        chat_id=chat_id,
        thread_id=thread_id,
        messages=messages_json,
    )

    with session_factory() as session:
        session.add(maria)
        session.commit()
