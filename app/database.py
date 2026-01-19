import aiosqlite
import json


class SimpleSQLiteStorage:
    """Класс для хранения истории чатов в SQLite"""
    
    def __init__(self, db_path: str = "chat_history.db"):
        """
        Инициализация хранилища
        
        Args:
            db_path: путь к файлу базы данных (по умолчанию chat_history.db)
        """
        self.db_path = db_path
        # При создании объекта нельзя использовать await,
        # поэтому инициализацию БД делаем в отдельном методе
    
    async def init_db(self):
        """
        Создает таблицу для хранения истории
        Вызывается один раз при старте бота
        """
        # async with автоматически открывает и закрывает соединение
        async with aiosqlite.connect(self.db_path) as conn:
            # Создаем курсор для выполнения SQL команд
            cursor = await conn.cursor()
            
            # Создаем таблицу, если её еще нет (IF NOT EXISTS)
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    user_id INTEGER,
                    chat_id INTEGER,
                    thread_id INTEGER,
                    messages TEXT,
                    PRIMARY KEY (user_id, chat_id, thread_id)
                )
            """)
            # PRIMARY KEY означает уникальную комбинацию этих трех полей
            # Для каждого user_id + chat_id + thread_id будет одна запись
            
            # Сохраняем изменения в БД
            await conn.commit()
            # После async with соединение автоматически закроется
    
    async def save_history(
        self, 
        user_id: int, 
        chat_id: int, 
        thread_id: int, 
        messages: list
    ):
        """
        Сохраняет историю сообщений для конкретной темы
        
        Args:
            user_id: ID пользователя в Telegram
            chat_id: ID чата в Telegram
            thread_id: ID темы в чате (или None для обычных чатов)
            messages: список сообщений [{"role": "user", "content": "..."}, ...]
        """
        # Открываем соединение с БД
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.cursor()
            
            # Преобразуем список сообщений в JSON строку
            # ensure_ascii=False чтобы русские буквы не превращались в \u0430
            messages_json = json.dumps(messages, ensure_ascii=False)
            
            # INSERT OR REPLACE = если запись существует - обновляем, если нет - создаем
            await cursor.execute("""
                INSERT OR REPLACE INTO chat_history 
                (user_id, chat_id, thread_id, messages)
                VALUES (?, ?, ?, ?)
            """, (
                user_id, 
                chat_id, 
                thread_id or 0,  # если thread_id None, ставим 0
                messages_json
            ))
            # Знаки ? - это плейсхолдеры, которые заменяются на значения из tuple
            # Это защита от SQL injection
            
            # Сохраняем изменения
            await conn.commit()
            
            print(f"✅ Сохранено {len(messages)} сообщений для юзера {user_id}")
    
    async def load_history(
        self, 
        user_id: int, 
        chat_id: int, 
        thread_id: int
    ) -> list:
        """
        Загружает историю сообщений для конкретной темы
        
        Args:
            user_id: ID пользователя
            chat_id: ID чата
            thread_id: ID темы
            
        Returns:
            list: список сообщений или пустой список, если истории нет
        """
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.cursor()
            
            # SELECT выбирает только колонку messages
            await cursor.execute("""
                SELECT messages FROM chat_history
                WHERE user_id = ? AND chat_id = ? AND thread_id = ?
            """, (user_id, chat_id, thread_id or 0))
            
            # fetchone() возвращает первую найденную строку или None
            result = await cursor.fetchone()
            
            # Если запись найдена
            if result:
                # result это tuple, берем первый элемент (JSON строка)
                # Парсим JSON обратно в список Python
                history = json.loads(result[0])
                # print(f"📖 Загружено {len(history)} сообщений для юзера {user_id}")
                return history
            
            # Если записи нет, возвращаем пустой список
            # print(f"📭 История пуста для юзера {user_id}")
            return []
    
    async def clear_history(
        self, 
        user_id: int, 
        chat_id: int, 
        thread_id: int
    ):
        """
        Удаляет историю для конкретной темы
        
        Args:
            user_id: ID пользователя
            chat_id: ID чата
            thread_id: ID темы
        """
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.cursor()
            
            # DELETE удаляет строку из таблицы
            await cursor.execute("""
                DELETE FROM chat_history
                WHERE user_id = ? AND chat_id = ? AND thread_id = ?
            """, (user_id, chat_id, thread_id or 0))
            
            await conn.commit()
            
            # print(f"🗑️ История очищена для юзера {user_id}")
    
    async def get_all_users(self) -> list:
        """
        Дополнительный метод: получает список всех пользователей в БД
        Полезно для статистики
        
        Returns:
            list: список кортежей [(user_id, chat_id, thread_id), ...]
        """
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.cursor()
            
            # Выбираем все записи
            await cursor.execute("""
                SELECT user_id, chat_id, thread_id FROM chat_history
            """)
            
            # fetchall() возвращает список всех строк
            results = await cursor.fetchall()
            return results
