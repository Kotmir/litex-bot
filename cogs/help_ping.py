import time
import discord
from discord import app_commands
from discord.ext import commands

COLOR_EMBED = 0xEC4899  # Фирменный цвет Litex


class HelpPingCog(commands.Cog):
    """Команды /help и /ping для игроков."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="help",
        description="Показать список доступных команд"
    )
    @app_commands.guild_only()
    async def help_command(self, interaction: discord.Interaction) -> None:
        embed_main = discord.Embed(
            title="📌 Команды бота Litex",
            description=(
                "Все команды вводятся через `/` — начни писать название, и Discord подскажет параметры.\n"
                "В `[квадратных скобках]` — необязательные параметры."
            ),
            color=COLOR_EMBED,
        )

        embed_main.add_field(
            name="🛠️ Основное",
            value=(
                "/help — показать это меню справки\n"
                "/ping — проверить, как быстро отвечает бот"
            ),
            inline=False,
        )

        embed_main.set_footer(text="Litex Server • Уютное выживание")
        await interaction.response.send_message(embed=embed_main, ephemeral=True)

    @app_commands.command(
        name="ping",
        description="Проверить скорость отклика и задержку соединения бота"
    )
    @app_commands.guild_only()
    async def ping(self, interaction: discord.Interaction) -> None:
        start_time = time.monotonic()
        
        await interaction.response.send_message("🏓 **Понг!** Измеряем задержку...", ephemeral=True)
        
        end_time = time.monotonic()
        api_latency = (end_time - start_time) * 1000
        websocket_latency = self.bot.latency * 1000

        embed = discord.Embed(
            title="🏓 Понг!",
            description=(
                f"Нажатие дошло до бота за: **{api_latency / 1000:.2f} сек**\n"
                f"Задержка соединения (gateway): **{int(websocket_latency)} ms**"
            ),
            color=COLOR_EMBED,
        )
        embed.set_footer(text="✅ Связь в порядке.")

        await interaction.edit_original_response(content=None, embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HelpPingCog(bot))