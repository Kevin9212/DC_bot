import discord
from discord import app_commands
from discord.ext import commands
from utils.interaction import auto_defer, reply

from db import (
    upsert_achievement,
    unlock_achievement,
    list_achievements,
    list_user_achievements,
    get_message_count,
    get_level,
    get_streak,
    set_active_title,
)

# 你可以在這裡定義成就規格（code 必須唯一）
DEFAULT_ACHIEVEMENTS = [
    # 發言
    ("MSG_001", "初次發言", "累積發言 1 次", None),
    ("MSG_100", "話匣子", "累積發言 100 次", "title_002"),
    ("MSG_500", "社群常客", "累積發言 500 次", "title_003"),

    # 等級
    ("LV_005", "新手冒險者", "達到等級 5", "title_004"),
    ("LV_010", "資深玩家", "達到等級 10", "title_005"),

    # 連續簽到
    ("CK_003", "三日不墜", "連續簽到 3 天", "title_006"),
    ("CK_007", "打卡達人", "連續簽到 7 天", "title_007"),
]

# 成就條件判斷（你要加新的成就，就在這裡加規則）
def _should_unlock(code: str, msg_count: int, level: int, streak: int) -> bool:
    if code == "MSG_001":
        return msg_count >= 1
    if code == "MSG_100":
        return msg_count >= 100
    if code == "MSG_500":
        return msg_count >= 500

    if code == "LV_005":
        return level >= 5
    if code == "LV_010":
        return level >= 10

    if code == "CK_003":
        return streak >= 3
    if code == "CK_007":
        return streak >= 7

    return False


class Achievements(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def ensure_defaults(self, guild_id: int):
        # 將預設成就寫入資料庫（可重複執行）
        for code, name, desc, reward_item_id in DEFAULT_ACHIEVEMENTS:
            await upsert_achievement(guild_id, code, name, desc, reward_item_id)

    async def check_and_unlock(self, guild_id: int, user_id: int, announce_channel: discord.abc.Messageable | None = None):
        # 確保預設成就存在
        await self.ensure_defaults(guild_id)

        msg_count = await get_message_count(guild_id, user_id)
        level = await get_level(guild_id, user_id)
        streak = await get_streak(guild_id, user_id)

        achievements = await list_achievements(guild_id)

        unlocked_any = False
        for code, name, desc, reward_item_id in achievements:
            if not _should_unlock(code, msg_count, level, streak):
                continue

            unlocked, ach = await unlock_achievement(guild_id, user_id, code)
            if unlocked and ach:
                unlocked_any = True

                # ach = (code, name, description, reward_item_id)
                reward_item_id = ach[3]

                # ✅ 自動佩戴：只對稱號道具生效（title_ 開頭）
                if reward_item_id and reward_item_id.startswith("title_"):
                    await set_active_title(guild_id, user_id, reward_item_id)

                # 公告（可選）
                if announce_channel:
                    embed = discord.Embed(
                        title="🏆 成就解鎖！",
                        description=f"恭喜 <@{user_id}> 解鎖 **{ach[1]}**\n{ach[2]}",
                        color=discord.Color.gold()
                    )
                    if reward_item_id:
                        msg = f"已獲得稱號道具：`{reward_item_id}`"
                        if reward_item_id.startswith("title_"):
                            msg += "\n✅ 已自動佩戴該稱號"
                        embed.add_field(name="獎勵", value=msg, inline=False)
                    await announce_channel.send(embed=embed)
        return unlocked_any


    # Slash 指令：查看自己的成就
    @app_commands.command(name="achievements", description="查看你的成就解鎖狀態")
    @auto_defer(ephemeral=True)
    async def achievements(self, interaction: discord.Interaction):
        
        gid = interaction.guild_id
        uid = interaction.user.id

        await self.ensure_defaults(gid)

        all_achs = await list_achievements(gid)
        user_achs = await list_user_achievements(gid, uid)
        unlocked_set = {row[0] for row in user_achs}

        embed = discord.Embed(title="🏆 成就列表", color=discord.Color.blurple())
        embed.set_footer(text="小皮炎 • Achievements")

        for code, name, desc, reward_item_id in all_achs:
            status = "✅ 已解鎖" if code in unlocked_set else "❌ 未解鎖"
            reward_text = f" | 🎁 {reward_item_id}" if reward_item_id else ""
            embed.add_field(
                name=f"{status}  {name}",
                value=f"`{code}`  {desc}{reward_text}",
                inline=False
            )
        await reply(interaction, embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Achievements(bot))
