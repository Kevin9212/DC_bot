import discord
from discord import app_commands
from discord.ext import commands
from utils.interaction import auto_defer, reply

class Core(commands.Cog):
    """
    Phase 0 / Core
    - /ping
    - /help
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="ping",
        description="測試小皮炎是否在線"
    )
    @auto_defer(ephemeral=True)
    async def ping(self, interaction: discord.Interaction):
        await reply(interaction, "🏓 Pong！小皮炎在線中", ephemeral=False)
    @app_commands.command(
        name="help",
        description="顯示小皮炎的指令列表"
    )
    @auto_defer(ephemeral=True)
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📖 小皮炎指令列表",
            color=discord.Color.blurple()
        )
        embed.add_field(
            name="🎮 基礎",
            value="/ping\n/help",
            inline=False
        )
        embed.add_field(
            name="👋 社群",
            value="/welcome channel\n/welcome message\n"
                  "/goodbye channel\n/goodbye message",
            inline=False
        )
        embed.add_field(
            name="📊 統計",
            value="/leaderboard\n/rank",
            inline=False
        )
        embed.add_field(
            name="💰 經濟",
            value="/daily\n/coins\n/level\n/give\n/top",
            inline=False
        )

        await reply(interaction, embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Core(bot))
