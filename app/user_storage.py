import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, Dict


class UserStorage:
    """Класс для управления данными пользователей в SQLite"""
    
    def __init__(self, db_path: str = "database.db"):
        """
        Инициализация хранилища пользователей
        
        Args:
            db_path: путь к файлу базы данных
        """
        self.db_path = db_path
        
        # Конфигурация лимитов для тарифных планов
        self.TARIFF_LIMITS = {
            'free': {
                'requests_per_day': 15,
                'tokens_per_day': 7500,
                'model': 'gpt-oss-120b'
            },
            'pro': {
                'requests_per_day': 200,
                'tokens_per_day': 200000,
                'model': 'gpt-oss-120b'
            },
            'ultra': {
                'requests_per_day': -1,
                'tokens_per_day': -1,
                'model': 'gpt-oss-120b'
            }
        }
    
    async def init_db(self):
        """
        Создает таблицу для хранения данных пользователей
        Вызывается один раз при старте бота
        """
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.cursor()
            
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    tariff_plan TEXT DEFAULT 'free',
                    requests_today INTEGER DEFAULT 0,
                    total_requests INTEGER DEFAULT 0,
                    tokens_today INTEGER DEFAULT 0,
                    limits_updated_at TEXT,
                    subscription_expires_at TEXT,
                    created_at TEXT
                )
            """)
            
            await conn.commit()
    
    async def get_user(self, user_id: int) -> Optional[Dict]:
        """
        Получает данные пользователя из БД
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Dict с данными пользователя или None, если пользователь не найден
        """
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.cursor()
            
            await cursor.execute("""
                SELECT * FROM users WHERE user_id = ?
            """, (user_id,))
            
            row = await cursor.fetchone()
            
            if row:
                return dict(row)
            return None
    
    async def create_user(self, user_id: int, username: Optional[str] = None):
        """
        Создает нового пользователя в БД с тарифом 'free'
        
        Args:
            user_id: Telegram user ID
            username: Telegram username (может быть None)
        """
        now = datetime.now().isoformat()
        
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.cursor()
            
            await cursor.execute("""
                INSERT OR IGNORE INTO users 
                (user_id, username, tariff_plan, requests_today, total_requests, 
                 tokens_today, limits_updated_at, created_at)
                VALUES (?, ?, 'free', 0, 0, 0, ?, ?)
            """, (user_id, username, now, now))
            
            await conn.commit()
            
            if cursor.rowcount > 0:
                print(f"✅ Создан новый пользователь: {user_id} (@{username})")
    
    async def update_usage(self, user_id: int, requests_delta: int = 1, tokens_delta: int = 0):
        """
        Обновляет статистику использования (запросы и токены)
        
        Args:
            user_id: Telegram user ID
            requests_delta: Количество добавляемых запросов (по умолчанию 1)
            tokens_delta: Количество добавляемых токенов
        """
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.cursor()
            
            await cursor.execute("""
                UPDATE users 
                SET requests_today = requests_today + ?,
                    total_requests = total_requests + ?,
                    tokens_today = tokens_today + ?
                WHERE user_id = ?
            """, (requests_delta, requests_delta, tokens_delta, user_id))
            
            await conn.commit()
    
    async def reset_daily_limits(self, user_id: int):
        """
        Сбрасывает дневные лимиты пользователя
        
        Args:
            user_id: Telegram user ID
        """
        now = datetime.now().isoformat()
        
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.cursor()
            
            await cursor.execute("""
                UPDATE users 
                SET requests_today = 0,
                    tokens_today = 0,
                    limits_updated_at = ?
                WHERE user_id = ?
            """, (now, user_id))
            
            await conn.commit()
            print(f"🔄 Сброшены дневные лимиты для пользователя {user_id}")
    
    async def check_and_reset_limits(self, user_id: int):
        """
        Проверяет, нужно ли сбросить дневные лимиты
        Сбрасывает, если прошло больше суток с последнего обновления
        
        Args:
            user_id: Telegram user ID
        """
        user = await self.get_user(user_id)
        if not user:
            return
        
        # Если limits_updated_at не установлен, сбрасываем лимиты
        if not user['limits_updated_at']:
            await self.reset_daily_limits(user_id)
            return
        
        # Парсим дату последнего обновления
        last_update = datetime.fromisoformat(user['limits_updated_at'])
        now = datetime.now()
        
        # Проверяем, прошло ли больше суток
        if (now - last_update) > timedelta(days=1):
            await self.reset_daily_limits(user_id)
        # Или если это новый день (сброс в полночь)
        elif last_update.date() < now.date():
            await self.reset_daily_limits(user_id)
    
    async def update_subscription(
        self, 
        user_id: int, 
        tariff: str, 
        expires_at: Optional[str] = None
    ):
        """
        Обновляет тарифный план и дату окончания подписки
        
        Args:
            user_id: Telegram user ID
            tariff: Тарифный план ('free', 'pro', 'ultra')
            expires_at: Дата окончания подписки в ISO формате (опционально)
        """
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.cursor()
            
            await cursor.execute("""
                UPDATE users 
                SET tariff_plan = ?,
                    subscription_expires_at = ?
                WHERE user_id = ?
            """, (tariff, expires_at, user_id))
            
            await conn.commit()
            print(f"💳 Обновлена подписка для пользователя {user_id}: {tariff}")
    
    def get_limits(self, tariff_plan: str) -> Dict:
        """
        Возвращает лимиты для указанного тарифного плана
        
        Args:
            tariff_plan: Название тарифа ('free', 'pro', 'ultra')
            
        Returns:
            Dict с лимитами (requests_per_day, tokens_per_day, model)
        """
        return self.TARIFF_LIMITS.get(tariff_plan, self.TARIFF_LIMITS['free'])
    
    async def check_limits(self, user_id: int) -> tuple[bool, str]:
        """
        Проверяет, не превышены ли лимиты пользователя
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            tuple: (можно_использовать: bool, сообщение_об_ошибке: str)
        """
        user = await self.get_user(user_id)
        if not user:
            return False, "Пользователь не найден"
        
        # Получаем лимиты для тарифа
        limits = self.get_limits(user['tariff_plan'])
        
        # Проверяем лимит запросов (если не безлимит)
        if limits['requests_per_day'] != -1:
            if user['requests_today'] >= limits['requests_per_day']:
                return False, (
                    f"❌ Достигнут дневной лимит запросов ({limits['requests_per_day']}).\n"
                    f"Попробуйте завтра или обновите тариф!"
                )
        
        # Проверяем лимит токенов (если не безлимит)
        if limits['tokens_per_day'] != -1:
            if user['tokens_today'] >= limits['tokens_per_day']:
                return False, (
                    f"❌ Достигнут дневной лимит токенов ({limits['tokens_per_day']}).\n"
                    f"Попробуйте завтра или обновите тариф!"
                )
        
        return True, ""
