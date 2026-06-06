import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'database.db')


async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    db = await get_db()
    
    # Guild settings
    await db.execute('''
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id INTEGER PRIMARY KEY,
            log_channel_id INTEGER DEFAULT NULL,
            main_roles TEXT DEFAULT '[]'
        )
    ''')
    
    # AFK system
    await db.execute('''
        CREATE TABLE IF NOT EXISTS afk (
            user_id INTEGER,
            guild_id INTEGER,
            reason TEXT DEFAULT '',
            time_from TEXT DEFAULT '',
            time_to TEXT DEFAULT '',
            is_afk INTEGER DEFAULT 1,
            PRIMARY KEY (user_id, guild_id)
        )
    ''')
    
    # Inactive (vacation) system
    await db.execute('''
        CREATE TABLE IF NOT EXISTS inactive (
            user_id INTEGER,
            guild_id INTEGER,
            reason TEXT DEFAULT '',
            time_from TEXT DEFAULT '',
            time_to TEXT DEFAULT '',
            is_inactive INTEGER DEFAULT 1,
            PRIMARY KEY (user_id, guild_id)
        )
    ''')
    
    # Ticket settings
    await db.execute('''
        CREATE TABLE IF NOT EXISTS ticket_settings (
            guild_id INTEGER PRIMARY KEY,
            welcome_message TEXT DEFAULT 'Добро пожаловать в тикет!',
            call_message TEXT DEFAULT 'Обзвон начат!',
            questions TEXT DEFAULT '["Ваш вопрос 1", "Ваш вопрос 2"]',
            call_roles TEXT DEFAULT '[]',
            call_channels TEXT DEFAULT '[]',
            log_channel_id INTEGER DEFAULT NULL,
            category_id INTEGER DEFAULT NULL
        )
    ''')
    
    # Active tickets
    await db.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            channel_id INTEGER PRIMARY KEY,
            guild_id INTEGER,
            user_id INTEGER,
            answers TEXT DEFAULT '[]'
        )
    ''')
    
    # Car system
    await db.execute('''
        CREATE TABLE IF NOT EXISTS cars (
            car_id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            name TEXT,
            in_use INTEGER DEFAULT 0,
            used_by INTEGER DEFAULT NULL,
            used_at TEXT DEFAULT NULL
        )
    ''')
    
    await db.execute('''
        CREATE TABLE IF NOT EXISTS car_settings (
            guild_id INTEGER PRIMARY KEY,
            reset_time INTEGER DEFAULT 3600,
            activity_mode TEXT DEFAULT 'voice',
            required_roles TEXT DEFAULT '[]'
        )
    ''')
    
    # Warnings system
    await db.execute('''
        CREATE TABLE IF NOT EXISTS warnings (
            warning_id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            user_id INTEGER,
            admin_id INTEGER,
            reason TEXT DEFAULT '',
            warn_role_id INTEGER DEFAULT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    await db.execute('''
        CREATE TABLE IF NOT EXISTS warning_settings (
            guild_id INTEGER PRIMARY KEY,
            warn_roles TEXT DEFAULT '[]',
            admin_roles TEXT DEFAULT '[]'
        )
    ''')
    
    # Market system
    await db.execute('''
        CREATE TABLE IF NOT EXISTS market_products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            name TEXT,
            price INTEGER DEFAULT 0,
            description TEXT DEFAULT ''
        )
    ''')
    
    await db.execute('''
        CREATE TABLE IF NOT EXISTS market_settings (
            guild_id INTEGER PRIMARY KEY,
            log_channel_id INTEGER DEFAULT NULL,
            roles TEXT DEFAULT '[]',
            admin_roles TEXT DEFAULT '[]',
            welcome_message TEXT DEFAULT 'В данном магазине вы можете обменять свои очки на товары.',
            exchange_rate INTEGER DEFAULT 2500,
            exchange_enabled INTEGER DEFAULT 1
        )
    ''')
    
    # Points system
    await db.execute('''
        CREATE TABLE IF NOT EXISTS points (
            user_id INTEGER,
            guild_id INTEGER,
            amount INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, guild_id)
        )
    ''')
    
    await db.execute('''
        CREATE TABLE IF NOT EXISTS point_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            name TEXT,
            points INTEGER DEFAULT 0
        )
    ''')
    
    await db.execute('''
        CREATE TABLE IF NOT EXISTS point_settings (
            guild_id INTEGER PRIMARY KEY,
            log_channel_id INTEGER DEFAULT NULL,
            button_channel_id INTEGER DEFAULT NULL,
            button_message_id INTEGER DEFAULT NULL
        )
    ''')
    
    await db.commit()
    await db.close()


async def execute_query(query, params=None):
    db = await get_db()
    if params:
        cursor = await db.execute(query, params)
    else:
        cursor = await db.execute(query)
    await db.commit()
    result = cursor.lastrowid
    await db.close()
    return result


async def fetch_one(query, params=None):
    db = await get_db()
    if params:
        cursor = await db.execute(query, params)
    else:
        cursor = await db.execute(query)
    row = await cursor.fetchone()
    await db.close()
    return row


async def fetch_all(query, params=None):
    db = await get_db()
    if params:
        cursor = await db.execute(query, params)
    else:
        cursor = await db.execute(query)
    rows = await cursor.fetchall()
    await db.close()
    return rows
