import discord
from discord import app_commands
from discord.ext import commands
from utils.interaction import auto_defer, reply
from db import (
    list_owned_titles,
    set_active_title,
    get_active_title_item_id
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
@auto_defer(ephemeral=True)
async def title_list(interaction: discord.Interaction):
    titles = await list_owned_titles(
        interaction.guild_id,
        interaction.user.id
    )

    if not titles:
        return await reply(interaction, "你目前沒有任何稱號。", ephemeral=True)

    active_item_id = await get_active_title_item_id(
        interaction.guild_id,
        interaction.user.id
    )

    lines = []
    for item_id, name in titles:
        mark = "⭐" if item_id == active_item_id else "▫️"
        lines.append(f"{mark} {name}")

    await reply(interaction, "🎖️ **你的稱號**\n" + "\n".join(lines), ephemeral=True)

@title_group.command(
    name="equip",
    description="佩戴一個你擁有的稱號"
)
@app_commands.describe(
    name="要佩戴的稱號名稱（需完全一致）"
)
@auto_defer(ephemeral=True)
async def title_equip(
    interaction: discord.Interaction,
    name: str
):
    titles = await list_owned_titles(
        interaction.guild_id,
        interaction.user.id
    )

    item_id = None
    for owned_item_id, owned_name in titles:
        if owned_name == name:
            item_id = owned_item_id
            break

    if item_id is None:
        return await reply(interaction, "你沒有這個稱號。", ephemeral=True)

    await set_active_title(
        interaction.guild_id,
        interaction.user.id,
        item_id
    )

    await reply(interaction, f"✅ 已佩戴稱號：**{name}**", ephemeral=True)

@title_group.command(
    name="unequip",
    description="卸下目前佩戴的稱號"
)
@auto_defer(ephemeral=True)
async def title_unequip(interaction: discord.Interaction):
    await set_active_title(
        interaction.guild_id,
        interaction.user.id,
        None
    )
    await reply(interaction, "已卸下稱號。", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Title(bot))
    if bot.tree.get_command("title") is None:
        bot.tree.add_command(title_group)