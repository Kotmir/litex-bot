from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands


class ModerationCog(commands.Cog):
    """Команды модерации чата."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="clear",
        description="Удалить последние сообщения в этом канале"
    )
    @app_commands.describe(
        amount="Количество сообщений для удаления (от 1 до 100)",
        member="Удалить сообщения только от конкретного пользователя (необязательно)"
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def clear(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 100],
        member: Optional[discord.Member] = None
    ) -> None:
        if not isinstance(interaction.user, discord.Member):
            return

        # Доступ: ТОЛЬКО администраторы сервера
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Эту команду могут использовать только администраторы.",
                ephemeral=True
            )
            return

        if not isinstance(interaction.channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel)):
            await interaction.response.send_message(
                "❌ В этом типе канала нельзя массово удалять сообщения.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            if member is not None:
                deleted_count = 0

                def check(msg: discord.Message) -> bool:
                    nonlocal deleted_count
                    if msg.author.id == member.id and deleted_count < amount:
                        deleted_count += 1
                        return True
                    return False

                deleted = await interaction.channel.purge(limit=min(amount * 5, 500), check=check)
            else:
                deleted = await interaction.channel.purge(limit=amount)

            target_text = f" от {member.mention}" if member else ""
            await interaction.followup.send(
                f"🗑️ Удалено сообщений{target_text}: **{len(deleted)}**",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ У бота нет права `Управлять сообщениями` (Manage Messages) в этом канале.",
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"❌ Ошибка при удалении (сообщения старше 14 дней нельзя удалить массово): {e}",
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModerationCog(bot))