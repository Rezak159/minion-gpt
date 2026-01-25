
DB_PATH = "database.db"

class BaseStorage:
    def __init__(self, db_path: str = DB_PATH):
        """
        Инициализация хранилища пользователей
        
        Args:
            db_path: путь к файлу базы данных
        """
        self.db_path = db_path
        