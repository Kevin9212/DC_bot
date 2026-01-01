import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from db import init_db, add_shop_item
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

# ===== Intents =====
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True  # on_message 統計/經驗需要

class XiaoPiYanBot(commands.Bot):
    async def setup_hook(self):
        # 初始化資料庫
        await init_db()

        # 載入 cogs（順序無關）
        await self.load_extension("cogs.core")
        await self.load_extension("cogs.social")
        await self.load_extension("cogs.stats")
        await self.load_extension("cogs.economy")
        await self.load_extension("cogs.title")
        await self.load_extension("cogs.shop")
        await self.load_extension("cogs.achievements")
        
        # ===== Slash 指令同步（只在這裡做）=====
        guild = discord.Object(id=GUILD_ID)
        self.tree.clear_commands(guild=guild)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        print("Slash 指令同步完成")

bot = XiaoPiYanBot(
    command_prefix="!",
    intents=intents
)

@bot.event
async def on_ready():
    print(f"已登入：{bot.user} ({bot.user.id})")
    print("我目前加入的伺服器：")
    for g in bot.guilds:
        print(f"- {g.name} ({g.id})")
    title_items = [
        ("title_001", "夜貓子", 500, "凌晨還在聊天的專屬稱號"),
        ("title_002", "話匣子", 0, "成就獎勵稱號"),
        ("title_003", "社群常客", 0, "成就獎勵稱號"),
        ("title_004", "新手冒險者", 0, "成就獎勵稱號"),
        ("title_005", "資深玩家", 0, "成就獎勵稱號"),
        ("title_006", "三日不墜", 0, "成就獎勵稱號"),
        ("title_007", "打卡達人", 0, "成就獎勵稱號"),
    ]
    for guild in bot.guilds:
        for item_id, name, price, desc in title_items:
            await add_shop_item(guild.id, item_id, name, price, desc)
bot.run(TOKEN)
