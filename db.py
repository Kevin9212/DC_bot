import time
import aiosqlite

from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("data") / "bot.db"

# ===== 時間工具 =====
def utc_now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())

# ===== 初始化 =====
async def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:

        # ---------- Guild 設定 ----------
        await db.execute("""
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id INTEGER PRIMARY KEY,
            welcome_channel_id INTEGER,
            welcome_message TEXT,
            goodbye_channel_id INTEGER,
            goodbye_message TEXT
        );
        """)

        # ---------- 訊息統計 ----------
        await db.execute("""
        CREATE TABLE IF NOT EXISTS user_stats (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            message_count INTEGER NOT NULL DEFAULT 0,
            last_counted_ts INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        );
        """)

        # ---------- 金幣 ----------
        await db.execute("""
        CREATE TABLE IF NOT EXISTS wallet (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            coins INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        );
        """)

        # ---------- 等級 ----------
        await db.execute("""
        CREATE TABLE IF NOT EXISTS levels (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            xp INTEGER NOT NULL DEFAULT 0,
            level INTEGER NOT NULL DEFAULT 1,
            last_xp_ts INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        );
        """)

        # ---------- 簽到 ----------
        await db.execute("""
        CREATE TABLE IF NOT EXISTS checkins (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            last_checkin_ts INTEGER NOT NULL DEFAULT 0,
            streak INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        );
        """)

        # ---------- 轉帳 ----------
        await db.execute("""
        CREATE TABLE IF NOT EXISTS transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            from_user_id INTEGER NOT NULL,
            to_user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            fee INTEGER NOT NULL,
            created_ts INTEGER NOT NULL
        );
        """)
        # ---------- 商店系統 ----------
        await db.execute("""
            CREATE TABLE IF NOT EXISTS shop_items (
                guild_id INTEGER,
                item_id TEXT,
                name TEXT,
                price INTEGER,
                description TEXT,
                PRIMARY KEY (guild_id, item_id)
            );
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                guild_id INTEGER,
                user_id INTEGER,
                item_id TEXT,
                qty INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id, item_id)
            );
        """)

        await db.commit()

# =====================================================
# Guild Settings
# =====================================================
async def upsert_guild_setting(guild_id: int, **kwargs):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?);",
            (guild_id,)
        )
        for k, v in kwargs.items():
            await db.execute(
                f"UPDATE guild_settings SET {k}=? WHERE guild_id=?;",
                (v, guild_id)
            )
        await db.commit()

async def get_guild_settings(guild_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT welcome_channel_id, welcome_message,
                   goodbye_channel_id, goodbye_message
            FROM guild_settings WHERE guild_id=?;
        """, (guild_id,))
        row = await cur.fetchone()
        if not row:
            return {}
        return {
            "welcome_channel_id": row[0],
            "welcome_message": row[1],
            "goodbye_channel_id": row[2],
            "goodbye_message": row[3],
        }

# =====================================================
# 訊息統計
# =====================================================
async def bump_message_stats(guild_id, user_id, cooldown_sec=30):
    now = utc_now_ts()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO user_stats (guild_id, user_id) VALUES (?, ?);",
            (guild_id, user_id)
        )
        cur = await db.execute(
            "SELECT last_counted_ts FROM user_stats WHERE guild_id=? AND user_id=?;",
            (guild_id, user_id)
        )
        (last,) = await cur.fetchone()
        if now - last < cooldown_sec:
            return False

        await db.execute("""
            UPDATE user_stats
            SET message_count = message_count + 1,
                last_counted_ts = ?
            WHERE guild_id=? AND user_id=?;
        """, (now, guild_id, user_id))
        await db.commit()
        return True

async def top_leaderboard(guild_id, limit=10):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT user_id, message_count
            FROM user_stats
            WHERE guild_id=?
            ORDER BY message_count DESC
            LIMIT ?;
        """, (guild_id, limit))
        return await cur.fetchall()

async def get_user_rank(guild_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT user_id, message_count
            FROM user_stats
            WHERE guild_id=?
            ORDER BY message_count DESC;
        """, (guild_id,))
        rows = await cur.fetchall()
    for i, (uid, cnt) in enumerate(rows, start=1):
        if uid == user_id:
            return i, cnt, len(rows)
    return None

# =====================================================
# 金幣 / 簽到 / 等級
# =====================================================
async def get_coins(guild_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO wallet (guild_id, user_id) VALUES (?, ?);",
            (guild_id, user_id)
        )
        cur = await db.execute(
            "SELECT coins FROM wallet WHERE guild_id=? AND user_id=?;",
            (guild_id, user_id)
        )
        (coins,) = await cur.fetchone()
        return coins

async def add_coins(guild_id, user_id, delta):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO wallet (guild_id, user_id) VALUES (?, ?);",
            (guild_id, user_id)
        )
        await db.execute(
            "UPDATE wallet SET coins = coins + ? WHERE guild_id=? AND user_id=?;",
            (delta, guild_id, user_id)
        )
        await db.commit()
        return await get_coins(guild_id, user_id)

def xp_to_level(xp: int) -> int:
    return int((xp // 100) ** 0.5) + 1

async def add_xp(guild_id, user_id, amount, cooldown_sec=60):
    now = utc_now_ts()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO levels (guild_id, user_id) VALUES (?, ?);",
            (guild_id, user_id)
        )
        cur = await db.execute(
            "SELECT xp, level, last_xp_ts FROM levels WHERE guild_id=? AND user_id=?;",
            (guild_id, user_id)
        )
        xp, lvl, last = await cur.fetchone()
        if now - last < cooldown_sec:
            return False, xp, lvl, False

        xp += amount
        lvl2 = xp_to_level(xp)
        leveled = lvl2 > lvl

        await db.execute("""
            UPDATE levels
            SET xp=?, level=?, last_xp_ts=?
            WHERE guild_id=? AND user_id=?;
        """, (xp, lvl2, now, guild_id, user_id))
        await db.commit()
        return True, xp, lvl2, leveled

async def get_level_info(guild_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO levels (guild_id, user_id) VALUES (?, ?);",
            (guild_id, user_id)
        )
        cur = await db.execute(
            "SELECT xp, level, last_xp_ts FROM levels WHERE guild_id=? AND user_id=?;",
            (guild_id, user_id)
        )
        return await cur.fetchone()

async def get_checkin(guild_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO checkins (guild_id, user_id) VALUES (?, ?);",
            (guild_id, user_id)
        )
        await db.commit()

        cur = await db.execute(
            "SELECT last_checkin_ts, streak FROM checkins WHERE guild_id=? AND user_id=?;",
            (guild_id, user_id)
        )
        row = await cur.fetchone()
        if row:
            return int(row[0]), int(row[1])
        return 0, 0


async def update_checkin(guild_id, user_id, ts, streak):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE checkins
            SET last_checkin_ts=?, streak=?
            WHERE guild_id=? AND user_id=?;
        """, (ts, streak, guild_id, user_id))
        await db.commit()

# =====================================================
# 轉帳
# =====================================================
async def can_transfer(guild_id, from_user_id, cooldown_sec=60):
    now = utc_now_ts()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT created_ts FROM transfers
            WHERE guild_id=? AND from_user_id=?
            ORDER BY created_ts DESC LIMIT 1;
        """, (guild_id, from_user_id))
        row = await cur.fetchone()
        if not row:
            return True, 0
        remain = cooldown_sec - (now - row[0])
        return remain <= 0, max(0, remain)

async def transfer_coins(guild_id, from_user_id, to_user_id, amount, fee_rate=0.05):
    fee = max(1, int(amount * fee_rate))
    total = amount + fee
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT coins FROM wallet WHERE guild_id=? AND user_id=?;",
            (guild_id, from_user_id)
        )
        (coins,) = await cur.fetchone()
        if coins < total:
            return False, "金幣不足"

        await db.execute(
            "UPDATE wallet SET coins = coins - ? WHERE guild_id=? AND user_id=?;",
            (total, guild_id, from_user_id)
        )
        await db.execute(
            "UPDATE wallet SET coins = coins + ? WHERE guild_id=? AND user_id=?;",
            (amount, guild_id, to_user_id)
        )
        await db.execute("""
            INSERT INTO transfers
            (guild_id, from_user_id, to_user_id, amount, fee, created_ts)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (guild_id, from_user_id, to_user_id, amount, fee, utc_now_ts()))
        await db.commit()
        return True, f"已轉帳 {amount}（手續費 {fee}）"
# =====================================================
# 排行榜（給 economy.py 使用）
# =====================================================

async def top_coins(guild_id: int, limit: int = 10):
    """
    取得金幣排行榜
    回傳 [(user_id, coins), ...]
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT user_id, coins
            FROM wallet
            WHERE guild_id=?
            ORDER BY coins DESC, user_id ASC
            LIMIT ?;
        """, (guild_id, limit))
        rows = await cur.fetchall()
        return [(int(uid), int(coins)) for uid, coins in rows]


async def top_levels(guild_id: int, limit: int = 10):
    """
    取得等級排行榜
    回傳 [(user_id, level, xp), ...]
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT user_id, level, xp
            FROM levels
            WHERE guild_id=?
            ORDER BY level DESC, xp DESC, user_id ASC
            LIMIT ?;
        """, (guild_id, limit))
        rows = await cur.fetchall()
        return [(int(uid), int(level), int(xp)) for uid, level, xp in rows]
# =====================================================
# Profile 用：取得使用者完整統計
# =====================================================

async def get_profile_data(guild_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        # 訊息數
        cur = await db.execute("""
            SELECT message_count
            FROM user_stats
            WHERE guild_id=? AND user_id=?;
        """, (guild_id, user_id))
        row = await cur.fetchone()
        message_count = int(row[0]) if row else 0

        # 金幣
        cur = await db.execute("""
            SELECT coins
            FROM wallet
            WHERE guild_id=? AND user_id=?;
        """, (guild_id, user_id))
        row = await cur.fetchone()
        coins = int(row[0]) if row else 0

        # 等級 / XP
        cur = await db.execute("""
            SELECT level, xp
            FROM levels
            WHERE guild_id=? AND user_id=?;
        """, (guild_id, user_id))
        row = await cur.fetchone()
        level, xp = (int(row[0]), int(row[1])) if row else (1, 0)

    return {
        "messages": message_count,
        "coins": coins,
        "level": level,
        "xp": xp,
    }
# =====================================================
# 稱號系統
# =====================================================

async def set_active_title(guild_id: int, user_id: int, title: str | None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?);
        """, (guild_id,))
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_titles (
                guild_id INTEGER,
                user_id INTEGER,
                active_title TEXT,
                PRIMARY KEY (guild_id, user_id)
            );
        """)
        await db.execute("""
            INSERT OR REPLACE INTO user_titles (guild_id, user_id, active_title)
            VALUES (?, ?, ?);
        """, (guild_id, user_id, title))

        await db.commit()

async def ensure_title_tables():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS active_titles (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                item_id TEXT NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            );
        """)
        await db.commit()


async def set_active_title(guild_id: int, user_id: int, item_id: str):
    """設定使用者目前佩戴的稱號（item_id 例如 title_001）"""
    await ensure_title_tables()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO active_titles (guild_id, user_id, item_id)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id)
            DO UPDATE SET item_id=excluded.item_id;
        """, (guild_id, user_id, item_id))
        await db.commit()


async def get_active_title(guild_id: int, user_id: int):
    """
    回傳使用者目前佩戴稱號的「名稱」(shop_items.name)；
    若找不到就回傳 None
    """
    await ensure_title_tables()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT s.name
            FROM active_titles a
            JOIN shop_items s
              ON s.guild_id=a.guild_id AND s.item_id=a.item_id
            WHERE a.guild_id=? AND a.user_id=?;
        """, (guild_id, user_id))
        row = await cur.fetchone()
        return row[0] if row else None



async def list_owned_titles(guild_id: int, user_id: int):
    """
    從 inventory 中撈出稱號類商品（item_id 以 title_ 開頭）
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT s.name
            FROM inventory i
            JOIN shop_items s
              ON s.guild_id=i.guild_id AND s.item_id=i.item_id
            WHERE i.guild_id=? AND i.user_id=? AND i.qty > 0
              AND s.item_id LIKE 'title_%'
            ORDER BY s.name ASC;
        """, (guild_id, user_id))
        rows = await cur.fetchall()
        return [r[0] for r in rows]
# =====================================================
# 商店系統
# =====================================================
async def list_shop(guild_id: int):
    """
    取得商店所有商品
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT item_id, name, price, description
            FROM shop_items
            WHERE guild_id=?
            ORDER BY price ASC;
        """, (guild_id,))
        rows = await cur.fetchall()
        return rows


async def buy_item(guild_id: int, user_id: int, item_id: str, qty: int = 1):
    """
    購買商品
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # 商品是否存在
        cur = await db.execute("""
            SELECT price, name
            FROM shop_items
            WHERE guild_id=? AND item_id=?;
        """, (guild_id, item_id))
        row = await cur.fetchone()
        if not row:
            return False, "找不到這個商品。", None

        price, name = row
        total_cost = price * qty

        # 餘額是否足夠
        cur = await db.execute("""
            SELECT coins
            FROM wallet
            WHERE guild_id=? AND user_id=?;
        """, (guild_id, user_id))
        row = await cur.fetchone()
        coins = row[0] if row else 0

        if coins < total_cost:
            return False, "金幣不足。", None

        # 扣錢
        await db.execute("""
            INSERT OR IGNORE INTO wallet (guild_id, user_id, coins)
            VALUES (?, ?, 0);
        """, (guild_id, user_id))

        await db.execute("""
            UPDATE wallet
            SET coins = coins - ?
            WHERE guild_id=? AND user_id=?;
        """, (total_cost, guild_id, user_id))

        # 加進背包
        await db.execute("""
            INSERT OR IGNORE INTO inventory (guild_id, user_id, item_id, qty)
            VALUES (?, ?, ?, 0);
        """, (guild_id, user_id, item_id))

        await db.execute("""
            UPDATE inventory
            SET qty = qty + ?
            WHERE guild_id=? AND user_id=? AND item_id=?;
        """, (qty, guild_id, user_id, item_id))

        await db.commit()

    return True, f"成功購買 {name} × {qty}", name


async def list_inventory(guild_id: int, user_id: int):
    """
    查看使用者背包
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT i.item_id, i.qty, s.name
            FROM inventory i
            JOIN shop_items s
              ON s.guild_id=i.guild_id AND s.item_id=i.item_id
            WHERE i.guild_id=? AND i.user_id=? AND i.qty > 0
            ORDER BY s.name ASC;
        """, (guild_id, user_id))
        rows = await cur.fetchall()
        return rows
async def add_shop_item(
    guild_id: int,
    item_id: str,
    name: str,
    price: int,
    description: str
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO shop_items
            (guild_id, item_id, name, price, description)
            VALUES (?, ?, ?, ?, ?);
        """, (guild_id, item_id, name, price, description))
        await db.commit()
# =========================
# 成就系統（Achievements）
# =========================

async def ensure_achievement_tables():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS achievements (
                guild_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                reward_item_id TEXT,
                created_ts INTEGER NOT NULL,
                PRIMARY KEY (guild_id, code)
            );
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_achievements (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                unlocked_ts INTEGER NOT NULL,
                PRIMARY KEY (guild_id, user_id, code)
            );
        """)
        await db.commit()


async def upsert_achievement(
    guild_id: int,
    code: str,
    name: str,
    description: str,
    reward_item_id: str | None = None,
):
    await ensure_achievement_tables()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO achievements
            (guild_id, code, name, description, reward_item_id, created_ts)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (guild_id, code, name, description, reward_item_id, int(time.time())))
        await db.commit()


async def has_achievement(guild_id: int, user_id: int, code: str) -> bool:
    await ensure_achievement_tables()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT 1 FROM user_achievements
            WHERE guild_id=? AND user_id=? AND code=?;
        """, (guild_id, user_id, code))
        row = await cur.fetchone()
        return row is not None


async def grant_inventory_item(guild_id: int, user_id: int, item_id: str, qty: int = 1):
    # 確保 inventory 表存在（你 init_db 已建，但這裡再保底也可）
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                guild_id INTEGER,
                user_id INTEGER,
                item_id TEXT,
                qty INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id, item_id)
            );
        """)
        await db.execute("""
            INSERT OR IGNORE INTO inventory (guild_id, user_id, item_id, qty)
            VALUES (?, ?, ?, 0);
        """, (guild_id, user_id, item_id))
        await db.execute("""
            UPDATE inventory
            SET qty = qty + ?
            WHERE guild_id=? AND user_id=? AND item_id=?;
        """, (qty, guild_id, user_id, item_id))
        await db.commit()


async def unlock_achievement(guild_id: int, user_id: int, code: str):
    """
    解鎖成就（只會成功一次）。回傳 (unlocked: bool, achievement_row)
    achievement_row: (code, name, description, reward_item_id)
    """
    await ensure_achievement_tables()
    async with aiosqlite.connect(DB_PATH) as db:
        # 先取成就定義
        cur = await db.execute("""
            SELECT code, name, description, reward_item_id
            FROM achievements
            WHERE guild_id=? AND code=?;
        """, (guild_id, code))
        ach = await cur.fetchone()
        if not ach:
            return False, None

        # 是否已解鎖
        cur = await db.execute("""
            SELECT 1 FROM user_achievements
            WHERE guild_id=? AND user_id=? AND code=?;
        """, (guild_id, user_id, code))
        exists = await cur.fetchone()
        if exists:
            return False, ach

        await db.execute("""
            INSERT INTO user_achievements (guild_id, user_id, code, unlocked_ts)
            VALUES (?, ?, ?, ?);
        """, (guild_id, user_id, code, int(time.time())))
        await db.commit()

    # 發放獎勵（稱號道具等）
    reward_item_id = ach[3]
    if reward_item_id:
        await grant_inventory_item(guild_id, user_id, reward_item_id, qty=1)

    return True, ach


async def list_achievements(guild_id: int):
    await ensure_achievement_tables()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT code, name, description, reward_item_id
            FROM achievements
            WHERE guild_id=?
            ORDER BY code ASC;
        """, (guild_id,))
        return await cur.fetchall()


async def list_user_achievements(guild_id: int, user_id: int):
    await ensure_achievement_tables()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT ua.code, ua.unlocked_ts, a.name, a.description, a.reward_item_id
            FROM user_achievements ua
            JOIN achievements a
              ON a.guild_id=ua.guild_id AND a.code=ua.code
            WHERE ua.guild_id=? AND ua.user_id=?
            ORDER BY ua.unlocked_ts ASC;
        """, (guild_id, user_id))
        return await cur.fetchall()


# 取得玩家目前數值（給成就判斷用）
async def get_message_count(guild_id: int, user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT message_count FROM user_stats
            WHERE guild_id=? AND user_id=?;
        """, (guild_id, user_id))
        row = await cur.fetchone()
        return int(row[0]) if row else 0


async def get_level(guild_id: int, user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT level FROM levels
            WHERE guild_id=? AND user_id=?;
        """, (guild_id, user_id))
        row = await cur.fetchone()
        return int(row[0]) if row else 1


async def get_streak(guild_id: int, user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT streak FROM checkins
            WHERE guild_id=? AND user_id=?;
        """, (guild_id, user_id))
        row = await cur.fetchone()
        return int(row[0]) if row else 0