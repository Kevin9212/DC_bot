import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone

from utils.interaction import auto_defer, reply

from db import (
    utc_now_ts,
    get_coins, add_coins,
    get_checkin, update_checkin,
    get_level_info, add_xp,
    top_coins, top_levels,
    can_transfer, transfer_coins,
    get_profile_data, get_user_rank,
    get_active_title,
)

# ===== 工具 =====
def human_utc(ts: int) -> str:
    if ts <= 0:
        return "從未"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# ===== Group：/top =====
top = app_commands.Group(
    name="top",
    description="排行榜相關指令"
)

@top.command(name="coins", description="查看金幣排行榜（前 10 名）")
@auto_defer(ephemeral=True)
async def top_coins_cmd(interaction: discord.Interaction):
    rows = await top_coins(interaction.guild_id, limit=10)
    if not rows:
        return await reply(interaction, "目前還沒有金幣資料。", ephemeral=True)

    embed = discord.Embed(title="🪙 金幣排行榜（Top 10）", color=discord.Color.gold())
    medals = ["🥇", "🥈", "🥉"]
    lines = []

    for i, (user_id, coins) in enumerate(rows, start=1):
        member = interaction.guild.get_member(user_id)
        name = member.display_name if member else f"User({user_id})"
        prefix = medals[i - 1] if i <= 3 else f"{i}."
        lines.append(f"{prefix} **{name}** — `🪙 {coins}`")

    embed.description = "\n".join(lines)
    await reply(interaction, embed=embed, ephemeral=False)


@top.command(name="levels", description="查看等級排行榜（前 10 名）")
@auto_defer(ephemeral=True)
async def top_levels_cmd(interaction: discord.Interaction):
    rows = await top_levels(interaction.guild_id, limit=10)
    if not rows:
        return await reply(interaction, "目前還沒有等級資料。", ephemeral=True)

    embed = discord.Embed(title="🎖️ 等級排行榜（Top 10）", color=discord.Color.purple())
    medals = ["🥇", "🥈", "🥉"]
    lines = []

    for i, (user_id, level, xp) in enumerate(rows, start=1):
        member = interaction.guild.get_member(user_id)
        name = member.display_name if member else f"User({user_id})"
        prefix = medals[i - 1] if i <= 3 else f"{i}."
        lines.append(f"{prefix} **{name}** — **Lv.{level}**（XP `{xp}`）")

    embed.description = "\n".join(lines)
    await reply(interaction, embed=embed, ephemeral=False)


# ===== Cog =====
class Economy(commands.Cog):
    """
    Phase 2 / 3：經濟系統
    - XP / 等級（自動）
    - /daily
    - /coins
    - /level
    - /give
    - /profile
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ===== 事件：每則訊息給 XP =====
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        did_gain, xp, lvl, leveled = await add_xp(
            message.guild.id,
            message.author.id,
            amount=15,
            cooldown_sec=60
        )

        if did_gain and leveled:
            try:
                await message.channel.send(
                    f"🎉 {message.author.mention} 升到 **Lv.{lvl}** 了！"
                )
            except Exception:
                pass

        # ===== 成就檢查（發言 / 等級類）=====
        ach_cog = self.bot.get_cog("Achievements")
        if ach_cog:
            try:
                await ach_cog.check_and_unlock(
                    message.guild.id,
                    message.author.id,
                    announce_channel=None  # None = 不公告頻道，避免洗版
                )
            except Exception:
                pass

    # ===== /daily =====
    @app_commands.command(name="daily", description="每日簽到領取金幣（含連續簽到加成）")
    @auto_defer(ephemeral=True)
    async def daily(self, interaction: discord.Interaction):
        gid = interaction.guild_id
        uid = interaction.user.id

        now = utc_now_ts()
        last_ts, streak = await get_checkin(gid, uid)

        if last_ts > 0 and (now - last_ts) < 24 * 3600:
            remain = 24 * 3600 - (now - last_ts)
            return await reply(
                interaction,
                "你今天已簽到過了。\n"
                f"上次簽到：{human_utc(last_ts)}\n"
                f"剩餘冷卻：約 {remain // 3600} 小時 {(remain % 3600) // 60} 分鐘",
                ephemeral=True
            )

        streak = streak + 1 if last_ts > 0 and (now - last_ts) <= 48 * 3600 else 1
        reward = 100 + min(200, (streak - 1) * 20)

        await update_checkin(gid, uid, now, streak)
        coins = await add_coins(gid, uid, reward)

        # ===== 成就檢查（連續簽到類）=====
        ach_cog = self.bot.get_cog("Achievements")
        if ach_cog:
            try:
                await ach_cog.check_and_unlock(
                    interaction.guild_id,
                    interaction.user.id,
                    announce_channel=interaction.channel  # 想公告就用 channel，不想就 None
                )
            except Exception:
                pass

        embed = discord.Embed(title="✅ 每日簽到成功", color=discord.Color.gold())
        embed.add_field(name="獲得金幣", value=f"`+{reward}`", inline=True)
        embed.add_field(name="連續簽到", value=f"`{streak} 天`", inline=True)
        embed.add_field(name="目前餘額", value=f"`🪙 {coins}`", inline=True)

        await reply(interaction, embed=embed, ephemeral=True)

    # ===== /profile =====
    @app_commands.command(name="profile", description="查看你的個人資料（等級 / 金幣 / 排名）")
    @auto_defer(ephemeral=True)
    async def profile(self, interaction: discord.Interaction):
        gid = interaction.guild_id
        uid = interaction.user.id

        data = await get_profile_data(gid, uid)
        rank_info = await get_user_rank(gid, uid)
        active_title = await get_active_title(gid, uid) or "無"

        rank_text = "未上榜"
        if rank_info:
            rank, _, total = rank_info
            rank_text = f"{rank} / {total}"

        embed = discord.Embed(
            title=f"👤 {interaction.user.display_name} 的個人資料",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="🎖️ 等級", value=f"Lv. {data['level']}", inline=True)
        embed.add_field(name="✨ XP", value=str(data["xp"]), inline=True)
        embed.add_field(name="🪙 金幣", value=str(data["coins"]), inline=True)
        embed.add_field(name="💬 訊息數", value=str(data["messages"]), inline=True)
        embed.add_field(name="🏆 訊息排行", value=rank_text, inline=True)
        embed.add_field(name="🏷️ 稱號", value=active_title, inline=True)

        await reply(interaction, embed=embed, ephemeral=True)

    # ===== /coins =====
    @app_commands.command(name="coins", description="查看你目前擁有的金幣")
    @auto_defer(ephemeral=True)
    async def coins(self, interaction: discord.Interaction):
        coins = await get_coins(interaction.guild_id, interaction.user.id)
        await reply(interaction, f"你目前有 `🪙 {coins}` 金幣。", ephemeral=True)

    # ===== /level =====
    @app_commands.command(name="level", description="查看你的等級與 XP")
    @auto_defer(ephemeral=True)
    async def level(self, interaction: discord.Interaction):
        xp, lvl, last_ts = await get_level_info(interaction.guild_id, interaction.user.id)
        await reply(
            interaction,
            f"等級：**Lv.{lvl}**\n"
            f"XP：`{xp}`\n"
            f"上次獲得 XP：{human_utc(last_ts)}",
            ephemeral=True
        )

    # ===== /give =====
    @app_commands.command(name="give", description="轉帳金幣給其他成員（含手續費）")
    @app_commands.describe(member="接收金幣的成員", amount="轉帳金額")
    @auto_defer(ephemeral=True)
    async def give(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if member.bot:
            return await reply(interaction, "不能轉帳給機器人。", ephemeral=True)

        ok, remain = await can_transfer(interaction.guild_id, interaction.user.id, cooldown_sec=60)
        if not ok:
            return await reply(interaction, f"轉帳冷卻中，請再等 {remain} 秒。", ephemeral=True)

        success, msg = await transfer_coins(interaction.guild_id, interaction.user.id, member.id, amount)
        if not success:
            return await reply(interaction, msg, ephemeral=True)

        await reply(interaction, f"💸 {interaction.user.mention} → {member.mention}\n{msg}", ephemeral=False)


# ===== setup =====
async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))

    # 安全註冊 group（避免重複）
    if bot.tree.get_command("top") is None:
        bot.tree.add_command(top)
