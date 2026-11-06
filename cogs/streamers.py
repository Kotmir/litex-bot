import re
import json
import time
import aiohttp
import aiosqlite
import discord
from discord.ext import commands, tasks
from discord import app_commands
import config

# Константы настроек
STREAM_CHANNEL_ID = 1536061816248209461  # Канал для уведомлений о стримах
EMBED_COLOR = discord.Color.from_rgb(186, 85, 211)  # Розово-фиолетовый цвет Litex
SPACER_URL = "https://raw.githubusercontent.com/Androz2091/AtlantaBot/master/assets/img/invisible.png"
DB_PATH = getattr(config, "DB_PATH", "litex.db")


class Streamers(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None
        # Защита от повторных уведомлений при коротких реконнектах: {user_id: timestamp}
        self.stream_cooldowns: dict[int, float] = {}

    async def cog_load(self) -> None:
        self.session = aiohttp.ClientSession(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
            }
        )
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """CREATE TABLE IF NOT EXISTS streamers (
                    user_id INTEGER PRIMARY KEY,
                    platform TEXT NOT NULL,
                    channel_name TEXT NOT NULL,
                    channel_url TEXT NOT NULL,
                    ping_role_id INTEGER,
                    is_live INTEGER DEFAULT 0
                )"""
            )
            # Если таблица уже была создана ранее без колонки is_live — добавляем её
            try:
                await db.execute("ALTER TABLE streamers ADD COLUMN is_live INTEGER DEFAULT 0")
            except Exception:
                pass
            await db.commit()

        self.check_streams_loop.start()

    async def cog_unload(self) -> None:
        self.check_streams_loop.cancel()
        if self.session and not self.session.closed:
            await self.session.close()

    async def check_twitch_live(self, channel_name: str, channel_url: str) -> tuple[bool, str | None]:
        """Проверяет без API-ключей, идет ли сейчас стрим на Twitch, и возвращает (is_live, stream_title)"""
        if not self.session:
            return False, None

        # Извлекаем логин Twitch из URL или имени канала
        login = channel_url.rstrip("/").split("/")[-1].lower() if "twitch.tv/" in channel_url.lower() else channel_name.lower()

        gql_query = {
            "query": """
            query($login: String!) {
                user(login: $login) {
                    stream {
                        id
                        title
                    }
                }
            }
            """,
            "variables": {"login": login},
        }
        headers = {
            # Публичный веб Client-ID плеера Twitch
            "Client-ID": "kimne78kx3ncx6brgo4mv6wki5h1ko",
            "Content-Type": "application/json",
        }
        try:
            async with self.session.post(
                "https://gql.twitch.tv/gql",
                json=gql_query,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    user_data = (data.get("data") or {}).get("user")
                    if user_data and user_data.get("stream"):
                        title = user_data["stream"].get("title") or "—"
                        return True, title
        except Exception:
            pass
        return False, None

    async def check_youtube_live(self, channel_url: str) -> tuple[bool, str | None]:
        """Проверяет страницу канала YouTube на наличие активной прямой трансляции"""
        if not self.session:
            return False, None

        live_url = channel_url.rstrip("/") + "/live"
        try:
            async with self.session.get(
                live_url,
                timeout=aiohttp.ClientTimeout(total=10),
                cookies={"CONSENT": "YES+cb.20210328-17-p0.en+FX+410"},
            ) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    if '"isLive":true' in html or '"isLiveBroadcast":true' in html:
                        title_match = re.search(r'<meta name="title" content="(.*?)">', html)
                        title = title_match.group(1) if title_match else "Прямой эфир на YouTube"
                        return True, title
        except Exception:
            pass
        return False, None

    def build_stream_embed(
        self,
        member: discord.Member | discord.User,
        guild: discord.Guild | None,
        platform: str,
        channel_name: str,
        channel_url: str,
        comment: str | None = None,
    ) -> discord.Embed:
        """Собирает карточку анонса в розово-фиолетовом стиле Litex"""
        embed = discord.Embed(
            title=f"📺 Новый стрим на {platform}",
            url=channel_url,
            description="Трансляция доступна по ссылке ниже.",
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow(),
        )

        embed.set_author(
            name=f"Контент-мейкер: {member.display_name}",
            icon_url=member.display_avatar.url,
        )

        embed.add_field(name="🎤 Канал", value=channel_name, inline=True)
        embed.add_field(name="🏷️ Платформа", value=platform, inline=True)
        embed.add_field(
            name="🔗 Ссылка на эфир",
            value=f"[Открыть {platform}]({channel_url})",
            inline=False,
        )
        embed.add_field(
            name="💬 Комментарий автора",
            value=comment if comment else "—",
            inline=False,
        )

        embed.set_image(url=SPACER_URL)
        embed.set_footer(
            text="LITEX • Контент-шеринг",
            icon_url=guild.icon.url if guild and guild.icon else None,
        )
        return embed

    async def send_stream_notification(
        self,
        user_id: int,
        platform: str,
        channel_name: str,
        channel_url: str,
        ping_role_id: int | None,
        stream_title: str | None = None,
    ):
        """Отправляет сообщение о начале стрима в канал STREAM_CHANNEL_ID"""
        channel = self.bot.get_channel(STREAM_CHANNEL_ID)
        if not channel or not isinstance(channel, discord.TextChannel):
            return

        guild = channel.guild
        member = guild.get_member(user_id) or await self.bot.fetch_user(user_id)
        if not member:
            return

        embed = self.build_stream_embed(
            member=member,
            guild=guild,
            platform=platform,
            channel_name=channel_name,
            channel_url=channel_url,
            comment=stream_title,
        )

        role_mention = f"<@&{ping_role_id}>\n" if ping_role_id else ""
        content = f"{role_mention}🎬 Новый контент от {member.mention}!"

        await channel.send(
            content=content,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(users=True, roles=True),
        )

    @tasks.loop(minutes=2)
    async def check_streams_loop(self):
        """Фоновая проверка всех стримеров каждые 2 минуты"""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT user_id, platform, channel_name, channel_url, ping_role_id, is_live FROM streamers"
            ) as cursor:
                rows = await cursor.fetchall()

            for user_id, platform, channel_name, channel_url, ping_role_id, was_live in rows:
                is_live_now = False
                stream_title = None

                if platform.lower() == "twitch":
                    is_live_now, stream_title = await self.check_twitch_live(channel_name, channel_url)
                elif platform.lower() == "youtube":
                    is_live_now, stream_title = await self.check_youtube_live(channel_url)

                # Если стрим только что начался
                if is_live_now and not was_live:
                    now = time.time()
                    # Защита от повторного спама, если стрим перезапустили в течение 30 минут
                    if now - self.stream_cooldowns.get(user_id, 0) > 1800:
                        self.stream_cooldowns[user_id] = now
                        await self.send_stream_notification(
                            user_id=user_id,
                            platform=platform,
                            channel_name=channel_name,
                            channel_url=channel_url,
                            ping_role_id=ping_role_id,
                            stream_title=stream_title,
                        )
                    await db.execute("UPDATE streamers SET is_live = 1 WHERE user_id = ?", (user_id,))
                    await db.commit()

                # Если стрим закончился — сбрасываем флаг is_live в 0
                elif not is_live_now and was_live:
                    await db.execute("UPDATE streamers SET is_live = 0 WHERE user_id = ?", (user_id,))
                    await db.commit()

    @check_streams_loop.before_loop
    async def before_check_streams(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        """Мгновенное авто-уведомление, если у стримера загорелся статус 'Стримит' в Discord"""
        was_streaming = any(isinstance(a, discord.Streaming) for a in before.activities)
        stream_activity = next((a for a in after.activities if isinstance(a, discord.Streaming)), None)

        if was_streaming or not stream_activity:
            return

        now = time.time()
        if now - self.stream_cooldowns.get(after.id, 0) < 1800:
            return

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT platform, channel_name, channel_url, ping_role_id, is_live FROM streamers WHERE user_id = ?",
                (after.id,),
            ) as cursor:
                row = await cursor.fetchone()

            if not row:
                return

            platform, channel_name, channel_url, ping_role_id, was_live = row
            if was_live:
                return

            self.stream_cooldowns[after.id] = now
            await db.execute("UPDATE streamers SET is_live = 1 WHERE user_id = ?", (after.id,))
            await db.commit()

        await self.send_stream_notification(
            user_id=after.id,
            platform=platform,
            channel_name=channel_name,
            channel_url=stream_activity.url or channel_url,
            ping_role_id=ping_role_id,
            stream_title=stream_activity.name,
        )

    @app_commands.command(
        name="streamer_add",
        description="Добавить стримера для автоматического отслеживания (Только для Администрации)",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        member="Пользователь Discord (контент-мейкер)",
        platform="Платформа (Twitch, YouTube, TikTok)",
        channel_name="Название канала / ник на Twitch (например: duh_or)",
        channel_url="Полная ссылка на канал (например: https://twitch.tv/duh_or)",
        ping_role="Роль для пинга над сообщением (необязательно)",
    )
    @app_commands.choices(
        platform=[
            app_commands.Choice(name="Twitch", value="Twitch"),
            app_commands.Choice(name="YouTube", value="YouTube"),
            app_commands.Choice(name="TikTok", value="TikTok"),
        ]
    )
    async def streamer_add(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        platform: app_commands.Choice[str],
        channel_name: str,
        channel_url: str,
        ping_role: discord.Role | None = None,
    ):
        await interaction.response.defer(ephemeral=True)

        if not channel_url.startswith(("http://", "https://")):
            channel_url = f"https://{channel_url}"

        role_id = ping_role.id if ping_role else None

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO streamers (user_id, platform, channel_name, channel_url, ping_role_id, is_live)
                   VALUES (?, ?, ?, ?, ?, 0)
                   ON CONFLICT(user_id) DO UPDATE SET
                       platform = excluded.platform,
                       channel_name = excluded.channel_name,
                       channel_url = excluded.channel_url,
                       ping_role_id = excluded.ping_role_id""",
                (member.id, platform.value, channel_name, channel_url, role_id),
            )
            await db.commit()

        await interaction.followup.send(
            f"✅ Стример {member.mention} (**{channel_name}** на **{platform.value}**) добавлен в авто-отслеживание!",
            ephemeral=True,
        )

    @app_commands.command(
        name="streamer_remove",
        description="Удалить стримера из авто-отслеживания (Только для Администрации)",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(member="Пользователь Discord, которого нужно убрать из стримеров")
    async def streamer_remove(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer(ephemeral=True)

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("DELETE FROM streamers WHERE user_id = ?", (member.id,))
            await db.commit()
            deleted = cursor.rowcount

        if deleted:
            await interaction.followup.send(f"🗑️ Стример {member.mention} удалён из базы.", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ Пользователь {member.mention} не найден в базе стримеров.", ephemeral=True)

    @app_commands.command(
        name="streamer_list",
        description="Показать список всех отслеживаемых стримеров проекта",
    )
    @app_commands.default_permissions(administrator=True)
    async def streamer_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT user_id, platform, channel_name, channel_url, is_live FROM streamers"
            ) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            return await interaction.followup.send("📭 Список стримеров пока пуст.", ephemeral=True)

        lines = [
            f"{'🟢 В эфире' if is_live else '⚫ Оффлайн'} | <@{uid}> — **{platform}**: [{cname}]({curl})"
            for uid, platform, cname, curl, is_live in rows
        ]
        embed = discord.Embed(
            title="🎥 Отслеживаемые стримеры Litex",
            description="\n".join(lines),
            color=EMBED_COLOR,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Streamers(bot))