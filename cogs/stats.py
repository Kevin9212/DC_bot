import discord
from discord import app_commands
from discord.ext import commands
from db import bump_message_stats, top_leaderboard, get_user_rank

class Stats(commands.Cog):
    """
    Phase 1：訊息統計
    - 自動統計訊息數（含冷卻，避免洗版）
    - /leaderboard
    - /rank
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ===== 事件：訊息統計 =====
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return
        if message.author.bot:
            return

        # 30 秒冷卻，避免洗訊息
        await bump_message_stats(
            message.guild.id,
            message.author.id,
            cooldown_sec=30
        )

    # ===== /leaderboard =====
    @app_commands.command(
        name="leaderboard",
        description="查看伺服器訊息數排行榜（前 10 名）"
    )
    async def leaderboard(self, interaction: discord.Interaction):
        rows = await top_leaderboard(interaction.guild_id, limit=10)

        if not rows:
            return await interaction.response.send_message(
                "目前還沒有任何統計資料。",
                ephemeral=True
            )

        embed = discord.Embed(
            title="📊 訊息數排行榜（Top 10）",
            color=discord.Color.green()
        )

        medals = ["🥇", "🥈", "🥉"]
        lines = []

        for i, (user_id, count) in enumerate(rows, start=1):
            member = interaction.guild.get_member(user_id)
            name = member.display_name if member else f"User({user_id})"
            prefix = medals[i - 1] if i <= 3 else f"{i}."
            lines.append(f"{prefix} **{name}** — `{count}` 則")

        embed.description = "\n".join(lines)
        await interaction.response.send_message(embed=embed)

    # ===== /rank =====
    @app_commands.command(
        name="rank",
        description="查看你在訊息排行榜中的名次"
    )
    async def rank(self, interaction: discord.Interaction):
        result = await get_user_rank(
            interaction.guild_id,
            interaction.user.id
        )

        if not result:
            return await interaction.response.send_message(
                "你目前還沒有被列入統計，多發幾則訊息試試吧！",
                ephemeral=True
            )

        rank, count, total = result
        await interaction.response.send_message(
            f"你的排名：**{rank}/{total}**\n"
            f"訊息數：`{count}` 則",
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(Stats(bot))
