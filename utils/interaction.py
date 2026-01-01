# utils/interaction.py
from __future__ import annotations

import functools
import discord


async def safe_defer(interaction: discord.Interaction, ephemeral: bool = True) -> bool:
    """在 3 秒內先回應，避免 10062 Unknown interaction。"""
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)
        return True
    except discord.NotFound:
        # 10062 Unknown interaction
        return False
    except discord.InteractionResponded:
        return True


async def reply(
    interaction: discord.Interaction,
    content: str | None = None,
    *,
    embed: discord.Embed | None = None,
    embeds: list[discord.Embed] | None = None,
    ephemeral: bool = True
):
    """
    統一回覆函式：
    - 若尚未回覆過：用 response.send_message
    - 若已 defer/回覆過：用 followup.send
    """
    try:
        kwargs = {
            "content": content,
            "ephemeral": ephemeral,
        }
        if embed is not None:
            kwargs["embed"] = embed
        if embeds is not None:
            kwargs["embeds"] = embeds

        if not interaction.response.is_done():
            return await interaction.response.send_message(**kwargs)
        return await interaction.followup.send(**kwargs)
    except discord.NotFound:
        # interaction 已過期就忽略（避免噴 log 洗版）
        return None


def auto_defer(*, ephemeral: bool = True):
    """
    通用裝飾器：Slash command 自動 defer。
    使用方式：
        @app_commands.command(...)
        @auto_defer(ephemeral=True)
        async def xxx(self, interaction): ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 找出 interaction 參數（通常是 args[1] 或 kwargs['interaction']）
            interaction = kwargs.get("interaction", None)
            if interaction is None:
                for a in args:
                    if isinstance(a, discord.Interaction):
                        interaction = a
                        break

            # 找不到 interaction 就照常執行（避免炸）
            if interaction is None:
                return await func(*args, **kwargs)

            ok = await safe_defer(interaction, ephemeral=ephemeral)
            if not ok:
                return None

            return await func(*args, **kwargs)

        return wrapper
    return decorator
