"""Точка входа бота litex: верификация, аналитика саппортов и отзывы."""
import logging
import sys

import discord
from discord import app_commands
from discord.ext import commands

import config
from database import Database

EXTENSIONS = (
    "cogs.verification",
    "cogs.voice",
    "cogs.profile",
    "cogs.help",
    "cogs.moderation",
    "cogs.staff_apply",
    "cogs.invite_logs",
    "cogs.bot_console",
    "cogs.donate",
    "cogs.streamers",
    "cogs.web_dashboard",
    "cogs.rules",
    "cogs.message_logs",
    "cogs.role_logs",
    "cogs.voice_logs",
    "cogs.mod_logs",
    "cogs.server_logs",
    "cogs.report",
    "cogs.voice_bot",
    "cogs.private_voices",
    "cogs.help_ping",
    "cogs.apply_ticket",
    "cogs.templates_cog",
    "cogs.staff_list",
    "cogs.voice_banner",
)

log = logging.getLogger("litex")


class LitexBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True        # привилегированный — включить в Developer Portal
        intents.voice_states = True
        intents.messages = True          # <-- Добавьте эту строчку
        intents.message_content = True
        intents.moderation = True

        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        self.db = Database(config.DB_PATH)
        self.tree.error(self.on_tree_error)

    async def setup_hook(self) -> None:
        await self.db.connect()

        for extension in EXTENSIONS:
            await self.load_extension(extension)
            log.info("Загружен модуль %s", extension)

        if config.GUILD_ID:
            guild = discord.Object(id=config.GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
        else:
            synced = await self.tree.sync()
        log.info("Синхронизировано слэш-команд: %d", len(synced))

    async def on_ready(self) -> None:
        log.info("Бот запущен как %s (ID: %s)", self.user, self.user.id if self.user else "?")

    async def close(self) -> None:
        # super().close() выгружает cogs (VoiceTracker сохраняет открытые сессии в БД),
        # поэтому базу закрываем только после него.
        await super().close()
        await self.db.close()

    async def on_tree_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.NoPrivateMessage):
            message = "⛔ Эта команда работает только на сервере."
        elif isinstance(error, app_commands.CheckFailure):
            message = "⛔ У вас нет доступа к этой команде."
        else:
            log.exception("Ошибка в команде /%s", interaction.command.name if interaction.command else "?", exc_info=error)
            message = "❌ Что-то пошло не так. Попробуйте ещё раз позже."

        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            pass


def main() -> None:
    if not config.TOKEN:
        sys.exit("❌ Не задан DISCORD_TOKEN. Скопируйте .env.example в .env и впишите токен бота.")
    LitexBot().run(config.TOKEN)


if __name__ == "__main__":
    main()