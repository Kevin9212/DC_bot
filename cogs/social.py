import discord
from discord import app_commands
from discord.ext import commands
from utils.interaction import auto_defer, reply
from db import upsert_guild_setting, get_guild_settings

# ===== Slash Groups（模組層級單例，避免重複註冊） =====

welcome = app_commands.Group(
    name="welcome",
    description="歡迎訊息相關設定"
)

goodbye = app_commands.Group(
    name="goodbye",
    description="離開訊息相關設定"
)

# ===== Helper =====
def render_template(template: str, member: discord.Member) -> str:
    """
    可用變數：
    {user}           -> @使用者
    {guild}          -> 伺服器名稱
    {member_count}   -> 目前人數
    """
    member_count = member.guild.member_count
    if member_count is None:
        member_count = len(member.guild.members)

    return (
        (template or "")
        .replace("{user}", member.mention)
        .replace("{guild}", member.guild.name)
        .replace("{member_count}", str(member_count))
    )


class Social(commands.Cog):
    """
    Phase 0 / Social
    - 進/退場訊息
    - /welcome
    - /goodbye
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- 事件：成員加入 ----------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        settings = await get_guild_settings(member.guild.id)
        channel_id = settings.get("welcome_channel_id")
        if not channel_id:
            return

        channel = member.guild.get_channel(channel_id)
        if not channel:
            return

        template = settings.get("welcome_message") or \
            "{user} 歡迎加入 {guild}！目前人數：{member_count}"

        await channel.send(render_template(template, member))

    # ---------- 事件：成員離開 ----------
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        settings = await get_guild_settings(member.guild.id)
        channel_id = settings.get("goodbye_channel_id")
        if not channel_id:
            return

        channel = member.guild.get_channel(channel_id)
        if not channel:
            return

        template = settings.get("goodbye_message") or \
            "{user} 已離開 {guild}。目前人數：{member_count}"

        await channel.send(render_template(template, member))


# ===== /welcome 子指令 =====

@welcome.command(
    name="channel",
    description="設定歡迎訊息要發送到哪個頻道（管理員）"
)
@auto_defer(ephemeral=True)
async def welcome_channel(
    interaction: discord.Interaction,
    channel: discord.TextChannel
):
    if not interaction.user.guild_permissions.manage_guild:
        return await reply(
            interaction,
            "你需要「管理伺服器」權限才能設定歡迎頻道。",
            ephemeral=True
        )

    await upsert_guild_setting(
        interaction.guild_id,
        welcome_channel_id=channel.id
    )
    await reply(
        interaction,
        f"✅ 已設定歡迎訊息頻道為 {channel.mention}",
        ephemeral=True
    )


@welcome.command(
    name="message",
    description="設定歡迎訊息內容（支援模板變數）"
)
@app_commands.describe(
    template="可用 {user} {guild} {member_count}"
)
@auto_defer(ephemeral=True)
async def welcome_message(
    interaction: discord.Interaction,
    template: str
):
    if not interaction.user.guild_permissions.manage_guild:
        return await reply(
            interaction,
            "你需要「管理伺服器」權限才能設定歡迎訊息。",
            ephemeral=True
        )

    await upsert_guild_setting(
        interaction.guild_id,
        welcome_message=template
    )
    await reply(interaction, "✅ 已更新歡迎訊息內容。", ephemeral=True)


# ===== /goodbye 子指令 =====

@goodbye.command(
    name="channel",
    description="設定離開訊息要發送到哪個頻道（管理員）"
)
@auto_defer(ephemeral=True)
async def goodbye_channel(
    interaction: discord.Interaction,
    channel: discord.TextChannel
):
    if not interaction.user.guild_permissions.manage_guild:
        return await reply(
            interaction,
            "你需要「管理伺服器」權限才能設定離開頻道。",
            ephemeral=True
        )

    await upsert_guild_setting(
        interaction.guild_id,
        goodbye_channel_id=channel.id
    )
    await reply(
        interaction,
        f"✅ 已設定離開訊息頻道為 {channel.mention}",
        ephemeral=True
    )


@goodbye.command(
    name="message",
    description="設定離開訊息內容（支援模板變數）"
)
@app_commands.describe(
    template="可用 {user} {guild} {member_count}"
)
@auto_defer(ephemeral=True)
async def goodbye_message(
    interaction: discord.Interaction,
    template: str
):
    if not interaction.user.guild_permissions.manage_guild:
        return await reply(
            interaction,
            "你需要「管理伺服器」權限才能設定離開訊息。",
            ephemeral=True
        )

    await upsert_guild_setting(
        interaction.guild_id,
        goodbye_message=template
    )
    await reply(interaction, "✅ 已更新離開訊息內容。", ephemeral=True)


# ===== setup =====

async def setup(bot: commands.Bot):
    await bot.add_cog(Social(bot))

    # 安全註冊（避免 CommandAlreadyRegistered）
    if bot.tree.get_command("welcome") is None:
        bot.tree.add_command(welcome)

    if bot.tree.get_command("goodbye") is None:
        bot.tree.add_command(goodbye)