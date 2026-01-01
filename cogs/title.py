import discord
from discord import app_commands
from discord.ext import commands
from db import (
    list_owned_titles,
    set_active_title,
    get_active_title
)

title_group = app_commands.Group(
    name="title",
    description="稱號系統"
)

class Title(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

@title_group.command(
    name="list",
    description="查看你擁有的稱號"
)
async def title_list(interaction: discord.Interaction):
    titles = await list_owned_titles(
        interaction.guild_id,
        interaction.user.id
    )

    if not titles:
        return await interaction.response.send_message(
            "你目前沒有任何稱號。",
            ephemeral=True
        )

    active = await get_active_title(
        interaction.guild_id,
        interaction.user.id
    )

    lines = []
    for t in titles:
        mark = "⭐" if t == active else "▫️"
        lines.append(f"{mark} {t}")

    await interaction.response.send_message(
        "🎖️ **你的稱號**\n" + "\n".join(lines),
        ephemeral=True
    )

@title_group.command(
    name="equip",
    description="佩戴一個你擁有的稱號"
)
@app_commands.describe(
    name="要佩戴的稱號名稱（需完全一致）"
)
async def title_equip(
    interaction: discord.Interaction,
    name: str
):
    titles = await list_owned_titles(
        interaction.guild_id,
        interaction.user.id
    )

    if name not in titles:
        return await interaction.response.send_message(
            "你沒有這個稱號。",
            ephemeral=True
        )

    await set_active_title(
        interaction.guild_id,
        interaction.user.id,
        name
    )

    await interaction.response.send_message(
        f"✅ 已佩戴稱號：**{name}**",
        ephemeral=True
    )

@title_group.command(
    name="unequip",
    description="卸下目前佩戴的稱號"
)
async def title_unequip(interaction: discord.Interaction):
    await set_active_title(
        interaction.guild_id,
        interaction.user.id,
        None
    )
    await interaction.response.send_message(
        "已卸下稱號。",
        ephemeral=True
    )

async def setup(bot: commands.Bot):
    await bot.add_cog(Title(bot))
    if bot.tree.get_command("title") is None:
        bot.tree.add_command(title_group)
