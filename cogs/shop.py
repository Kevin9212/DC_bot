import discord
from discord import app_commands
from discord.ext import commands

from utils.interaction import auto_defer, reply

from db import (
    list_shop,
    buy_item,
    list_inventory
)

shop = app_commands.Group(
    name="shop",
    description="商店系統"
)

class Shop(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot


@shop.command(name="list", description="查看目前商店販售的商品")
@auto_defer(ephemeral=True)
async def shop_list(interaction: discord.Interaction):
    items = await list_shop(interaction.guild_id)

    if not items:
        return await reply(interaction, "商店目前沒有商品。", ephemeral=True)

    embed = discord.Embed(title="🛒 商店商品列表", color=discord.Color.green())

    for item_id, name, price, desc in items:
        embed.add_field(
            name=f"{name}（{price} 金幣）",
            value=f"`ID：{item_id}`\n{desc}",
            inline=False
        )

    await reply(interaction, embed=embed, ephemeral=True)


@shop.command(name="buy", description="購買商店商品")
@app_commands.describe(
    item_id="商品 ID（例如 title_001）",
    qty="購買數量（預設 1）"
)
async def shop_buy(
    interaction: discord.Interaction,
    item_id: str,
    qty: int = 1
):
    await interaction.response.defer(ephemeral=True)

    ok, msg, _ = await buy_item(
        interaction.guild_id,
        interaction.user.id,
        item_id,
        qty
    )

    if not ok:
        return await reply(interaction, msg, ephemeral=True)

    await reply(interaction, f"✅ {msg}", ephemeral=True)


@shop.command(name="inventory", description="查看你的背包")
@auto_defer(ephemeral=True)
async def inventory(interaction: discord.Interaction):
    items = await list_inventory(
        interaction.guild_id,
        interaction.user.id
    )

    if not items:
        return await reply(interaction, "你的背包是空的。", ephemeral=True)

    embed = discord.Embed(
        title="🎒 你的背包",
        color=discord.Color.blurple()
    )

    for item_id, qty, name in items:
        embed.add_field(
            name=name,
            value=f"數量：{qty}\nID：`{item_id}`",
            inline=False
        )

    await reply(interaction, embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Shop(bot))
    if bot.tree.get_command("shop") is None:
        bot.tree.add_command(shop)