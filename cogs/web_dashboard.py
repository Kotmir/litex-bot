import aiosqlite
import discord
from aiohttp import web
from discord.ext import commands
import config

DB_PATH = getattr(config, "DB_PATH", "litex.db")
PORT = 8080
EMBED_COLOR = discord.Color.from_rgb(186, 85, 211)

# Ваша фирменная иконка-логотип
LOGO_URL = "https://cdn.discordapp.com/attachments/1564805779561783296/1565551796611584120/AJWXcNeLGS5H_JPGdVcUrbfuAF403UCwiB9kKuQUDWavot0wmWNXJ2XcyjyuWyMlIZHdpuLGjMnut-OqM6bQysVggiYYuAzXrEUFPYcsSls4R2eXgZhREuzYvZnx3EApGwFIvqCMIc54GG9w9YW10SjehkbFAjAvSXS48n3FMEeU3uevTNcTRDjyfBgeCQj8-8dIY-kkKShtPfxGgfXUkUd7uoGrlR7ID9FYeR--65wBYlOa2tnFGBV1wYaV5mrIxI_FaMYGkNdQlr8I3u8TsI0mLcjj-JEvx28FrHXF3aUMhX7JLEQOLUY76xOopAFcy74WFEvm-9Zee0XgtQOzddYRXvW_s1600.png"

HTML_PAGE = f"""<!DOCTYPE html>
<html lang="ru" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Litex Bot — Панель управления</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', sans-serif; background-color: #0b0713; color: #f3e8ff; }}
        .glass {{ background: rgba(24, 16, 38, 0.85); backdrop-filter: blur(12px); border: 1px solid rgba(186, 85, 211, 0.25); }}
        .neon-border:focus {{ outline: none; border-color: #ba55d3; box-shadow: 0 0 12px rgba(186, 85, 211, 0.4); }}
    </style>
</head>
<body class="min-h-screen p-6 md:p-10">
    <div class="max-w-6xl mx-auto space-y-8">
        <!-- Шапка с вашим логотипом -->
        <div class="glass rounded-2xl p-6 flex flex-col md:flex-row items-center justify-between gap-4">
            <div class="flex items-center gap-4">
                <img src="{LOGO_URL}" alt="Logo" class="w-14 h-14 rounded-2xl object-cover shadow-lg shadow-fuchsia-500/30 border border-fuchsia-500/40">
                <div>
                    <h1 class="text-2xl font-bold bg-gradient-to-r from-fuchsia-400 to-purple-300 bg-clip-text text-transparent">
                        Litex Helper Bot • Web Dashboard
                    </h1>
                    <p class="text-sm text-purple-300/70" id="bot-status">Загрузка статуса бота...</p>
                </div>
            </div>
            <div class="flex flex-wrap gap-3">
                <button onclick="sendPanel('staff')" class="px-4 py-2.5 rounded-xl bg-fuchsia-600 hover:bg-fuchsia-500 font-semibold text-sm transition shadow-lg shadow-fuchsia-600/30">
                    📋 Отправить Набор в состав
                </button>
                <button onclick="sendPanel('donate')" class="px-4 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 font-semibold text-sm transition shadow-lg shadow-purple-600/30">
                    👑 Отправить Панель Prime
                </button>
            </div>
        </div>

        <div id="toast" class="hidden fixed bottom-6 right-6 px-5 py-3 rounded-xl bg-fuchsia-600 text-white font-medium shadow-2xl z-50"></div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <!-- Настройки ID -->
            <div class="glass rounded-2xl p-6 space-y-4">
                <h2 class="text-lg font-bold text-fuchsia-300">⚙️ Основные ID каналов и категорий</h2>
                <div class="space-y-3 text-sm">
                    <div>
                        <label class="block text-purple-300/80 mb-1">ID канала для быстрой отправки панелей (кнопки сверху)</label>
                        <input id="target_channel_id" type="text" placeholder="1564805779561783296" class="w-full px-3.5 py-2 rounded-xl bg-black/40 border border-purple-500/30 neon-border">
                    </div>
                    <div>
                        <label class="block text-purple-300/80 mb-1">Категория тикетов набора (Staff Apply)</label>
                        <input id="staff_category_id" type="text" class="w-full px-3.5 py-2 rounded-xl bg-black/40 border border-purple-500/30 neon-border">
                    </div>
                    <div>
                        <label class="block text-purple-300/80 mb-1">Категория тикетов доната (Prime)</label>
                        <input id="donate_category_id" type="text" class="w-full px-3.5 py-2 rounded-xl bg-black/40 border border-purple-500/30 neon-border">
                    </div>
                    <div>
                        <label class="block text-purple-300/80 mb-1">ID пользователя для пинга в донате</label>
                        <input id="donate_ping_user_id" type="text" class="w-full px-3.5 py-2 rounded-xl bg-black/40 border border-purple-500/30 neon-border">
                    </div>
                    <div>
                        <label class="block text-purple-300/80 mb-1">Канал оповещений о стримах</label>
                        <input id="stream_channel_id" type="text" class="w-full px-3.5 py-2 rounded-xl bg-black/40 border border-purple-500/30 neon-border">
                    </div>
                    <div>
                        <label class="block text-purple-300/80 mb-1">Канал логов приглашений (Invite Logs)</label>
                        <input id="invite_channel_id" type="text" class="w-full px-3.5 py-2 rounded-xl bg-black/40 border border-purple-500/30 neon-border">
                    </div>
                    <div>
                        <label class="block text-purple-300/80 mb-1">Канал консоли бота (Bot Console)</label>
                        <input id="console_channel_id" type="text" class="w-full px-3.5 py-2 rounded-xl bg-black/40 border border-purple-500/30 neon-border">
                    </div>
                </div>
                <button onclick="saveSettings()" class="w-full py-2.5 rounded-xl bg-gradient-to-r from-fuchsia-600 to-purple-600 hover:opacity-95 font-semibold transition">
                    💾 Сохранить все настройки
                </button>
            </div>

            <!-- Управление стримерами -->
            <div class="glass rounded-2xl p-6 space-y-4">
                <h2 class="text-lg font-bold text-fuchsia-300">🎥 Управление стримерами (Авто-анонсы)</h2>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                    <input id="st_user_id" type="text" placeholder="Discord ID стримера" class="px-3.5 py-2 rounded-xl bg-black/40 border border-purple-500/30 neon-border">
                    <select id="st_platform" class="px-3.5 py-2 rounded-xl bg-black/40 border border-purple-500/30 neon-border">
                        <option value="Twitch">Twitch</option>
                        <option value="YouTube">YouTube</option>
                        <option value="TikTok">TikTok</option>
                    </select>
                    <input id="st_name" type="text" placeholder="Ник канала (duh_or)" class="px-3.5 py-2 rounded-xl bg-black/40 border border-purple-500/30 neon-border">
                    <input id="st_url" type="text" placeholder="https://twitch.tv/duh_or" class="px-3.5 py-2 rounded-xl bg-black/40 border border-purple-500/30 neon-border">
                </div>
                <button onclick="addStreamer()" class="w-full py-2.5 rounded-xl bg-fuchsia-600/80 hover:bg-fuchsia-600 font-semibold text-sm transition">
                    ➕ Добавить стримера в базу
                </button>
                <div id="streamers-list" class="space-y-2 max-h-80 overflow-y-auto pr-1 pt-2"></div>
            </div>
        </div>
    </div>

    <script>
        function showToast(msg) {{
            var t = document.getElementById('toast');
            t.textContent = msg;
            t.classList.remove('hidden');
            setTimeout(function() {{ t.classList.add('hidden'); }}, 3500);
        }}

        async function loadData() {{
            var res = await fetch('/api/status');
            var data = await res.json();
            document.getElementById('bot-status').textContent = 'В сети как ' + data.bot_name + ' | Серверов: ' + data.guilds + ' | Модулей: ' + data.cogs;
            document.getElementById('staff_category_id').value = data.settings.staff_category_id || '';
            document.getElementById('donate_category_id').value = data.settings.donate_category_id || '';
            document.getElementById('donate_ping_user_id').value = data.settings.donate_ping_user_id || '';
            document.getElementById('stream_channel_id').value = data.settings.stream_channel_id || '';
            document.getElementById('target_channel_id').value = data.settings.target_channel_id || '';
            document.getElementById('invite_channel_id').value = data.settings.invite_channel_id || '';
            document.getElementById('console_channel_id').value = data.settings.console_channel_id || '';

            var list = document.getElementById('streamers-list');
            list.innerHTML = '';
            if (data.streamers.length === 0) {{
                list.innerHTML = '<p class="text-sm text-purple-300/50 text-center py-4">Список стримеров пуст</p>';
            }}
            data.streamers.forEach(function(s) {{
                var item = document.createElement('div');
                item.className = 'flex items-center justify-between px-3.5 py-2.5 rounded-xl bg-black/30 border border-purple-500/20 text-sm';
                item.innerHTML = '<div><span class="font-semibold text-fuchsia-300">' + s.channel_name + '</span><span class="text-xs text-purple-300/60 ml-2">(' + s.platform + ' | ID: ' + s.user_id + ')</span></div><button onclick="removeStreamer(\\'' + s.user_id + '\\')" class="text-rose-400 hover:text-rose-300 text-xs font-semibold">Удалить</button>';
                list.appendChild(item);
            }});
        }}

        async function saveSettings() {{
            var payload = {{
                staff_category_id: document.getElementById('staff_category_id').value.trim(),
                donate_category_id: document.getElementById('donate_category_id').value.trim(),
                donate_ping_user_id: document.getElementById('donate_ping_user_id').value.trim(),
                stream_channel_id: document.getElementById('stream_channel_id').value.trim(),
                target_channel_id: document.getElementById('target_channel_id').value.trim(),
                invite_channel_id: document.getElementById('invite_channel_id').value.trim(),
                console_channel_id: document.getElementById('console_channel_id').value.trim()
            }};
            await fetch('/api/settings', {{ method: 'POST', body: JSON.stringify(payload) }});
            showToast('Настройки успешно сохранены!');
            loadData();
        }}

        async function addStreamer() {{
            var payload = {{
                user_id: document.getElementById('st_user_id').value.trim(),
                platform: document.getElementById('st_platform').value,
                channel_name: document.getElementById('st_name').value.trim(),
                channel_url: document.getElementById('st_url').value.trim()
            }};
            if (!payload.user_id || !payload.channel_name) return showToast('Заполните ID и название канала');
            await fetch('/api/streamers/add', {{ method: 'POST', body: JSON.stringify(payload) }});
            document.getElementById('st_user_id').value = '';
            document.getElementById('st_name').value = '';
            document.getElementById('st_url').value = '';
            showToast('Стример добавлен!');
            loadData();
        }}

        async function removeStreamer(user_id) {{
            await fetch('/api/streamers/remove', {{ method: 'POST', body: JSON.stringify({{ user_id: user_id }}) }});
            showToast('Стример удален');
            loadData();
        }}

        async function sendPanel(type) {{
            var channel_id = document.getElementById('target_channel_id').value.trim();
            if (!channel_id) return showToast('Укажите ID канала для отправки панелей!');
            var res = await fetch('/api/send_panel', {{
                method: 'POST',
                body: JSON.stringify({{ type: type, channel_id: channel_id }})
            }});
            var data = await res.json();
            showToast(data.message || 'Отправлено!');
        }}

        loadData();
    </script>
</body>
</html>
"""


class WebDashboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.runner: web.AppRunner | None = None

    async def cog_load(self) -> None:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """CREATE TABLE IF NOT EXISTS dashboard_config (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )"""
            )
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
            await db.commit()

        app = web.Application()
        app.router.add_get("/", self.handle_index)
        app.router.add_get("/api/status", self.handle_status)
        app.router.add_post("/api/settings", self.handle_save_settings)
        app.router.add_post("/api/streamers/add", self.handle_add_streamer)
        app.router.add_post("/api/streamers/remove", self.handle_remove_streamer)
        app.router.add_post("/api/send_panel", self.handle_send_panel)

        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", PORT)
        await site.start()
        print(f"🌐 Веб-панель управления запущена: http://localhost:{PORT}")

    async def cog_unload(self) -> None:
        if self.runner:
            await self.runner.cleanup()

    async def get_settings(self) -> dict[str, str]:
        defaults = {
            "staff_category_id": "1565495732067369061",
            "donate_category_id": "1565544404297457744",
            "donate_ping_user_id": "393700489881190411",
            "stream_channel_id": "1536061816248209461",
            "target_channel_id": "1564805779561783296",
            "invite_channel_id": "",
            "console_channel_id": "1564805779561783296",
        }
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT key, value FROM dashboard_config") as cursor:
                rows = await cursor.fetchall()
                for k, v in rows:
                    defaults[k] = v
        return defaults

    async def handle_index(self, request: web.Request) -> web.Response:
        return web.Response(text=HTML_PAGE, content_type="text/html")

    async def handle_status(self, request: web.Request) -> web.Response:
        settings = await self.get_settings()
        streamers = []
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT user_id, platform, channel_name, channel_url FROM streamers") as cursor:
                rows = await cursor.fetchall()
                for uid, plat, cname, curl in rows:
                    streamers.append({
                        "user_id": str(uid),
                        "platform": plat,
                        "channel_name": cname,
                        "channel_url": curl,
                    })

        return web.json_response({
            "bot_name": str(self.bot.user or "Litex Bot"),
            "guilds": len(self.bot.guilds),
            "cogs": len(self.bot.cogs),
            "settings": settings,
            "streamers": streamers,
        })

    async def handle_save_settings(self, request: web.Request) -> web.Response:
        data = await request.json()
        async with aiosqlite.connect(DB_PATH) as db:
            for k, v in data.items():
                await db.execute(
                    "INSERT INTO dashboard_config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (k, str(v)),
                )
            for guild in self.bot.guilds:
                if data.get("invite_channel_id", "").isdigit():
                    await db.execute(
                        "CREATE TABLE IF NOT EXISTS invite_settings (guild_id INTEGER PRIMARY KEY, invite_channel_id INTEGER)"
                    )
                    await db.execute(
                        "INSERT INTO invite_settings (guild_id, invite_channel_id) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET invite_channel_id = excluded.invite_channel_id",
                        (guild.id, int(data["invite_channel_id"])),
                    )
                if data.get("console_channel_id", "").isdigit():
                    await db.execute(
                        "CREATE TABLE IF NOT EXISTS console_settings (guild_id INTEGER PRIMARY KEY, console_channel_id INTEGER)"
                    )
                    await db.execute(
                        "INSERT INTO console_settings (guild_id, console_channel_id) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET console_channel_id = excluded.console_channel_id",
                        (guild.id, int(data["console_channel_id"])),
                    )
            await db.commit()
        return web.json_response({"status": "ok"})

    async def handle_add_streamer(self, request: web.Request) -> web.Response:
        data = await request.json()
        url = data.get("channel_url", "")
        if url and not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO streamers (user_id, platform, channel_name, channel_url, is_live)
                   VALUES (?, ?, ?, ?, 0)
                   ON CONFLICT(user_id) DO UPDATE SET
                       platform = excluded.platform,
                       channel_name = excluded.channel_name,
                       channel_url = excluded.channel_url""",
                (int(data["user_id"]), data["platform"], data["channel_name"], url),
            )
            await db.commit()
        return web.json_response({"status": "ok"})

    async def handle_remove_streamer(self, request: web.Request) -> web.Response:
        data = await request.json()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM streamers WHERE user_id = ?", (int(data["user_id"]),))
            await db.commit()
        return web.json_response({"status": "ok"})

    async def handle_send_panel(self, request: web.Request) -> web.Response:
        data = await request.json()
        channel_id = int(data["channel_id"]) if str(data.get("channel_id", "")).isdigit() else 0
        channel = self.bot.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            return web.json_response({"message": "Канал с таким ID не найден!"})

        panel_type = data.get("type")
        if panel_type == "donate":
            try:
                from cogs.donate import PrimeView, IMAGE_URL, SPACER_URL
                b_emb = discord.Embed(color=EMBED_COLOR).set_image(url=IMAGE_URL.strip())
                i_emb = discord.Embed(
                    title="👑 Подписка Prime",
                    description=(
                        "Получите максимальный набор привилегий и возможностей для комфортной игры на сервере по выгодной цене!\n\n"
                        "💰 **Стоимость подписки:**\n"
                        "> • **30 дней:** `150 коинов`\n"
                        "> • **90 дней:** `400 коинов` *(Выгодно)*\n"
                        "> • **180 дней:** `700 коинов` *(Максимальная выгода)*"
                    ),
                    color=EMBED_COLOR,
                ).set_image(url=SPACER_URL)
                f_emb = discord.Embed(
                    title="🛠️ Функционал и команды Prime:",
                    description=(
                        "**✨ Кастомизация и предметы:**\n"
                        "> • Надевание любого предмета на голову — `/hat`\n"
                        "> • Переименование предметов на наковальне с цветами (`&x`)\n"
                        "> • Добавление описания (лора) предметам — `/ie lore`\n\n"
                        "**⭐ Опыт и чат:**\n"
                        "> • Перевод опыта в бутыльки — `/expbottle`\n"
                        "> • Покраска сообщений в чате через `<color>`\n"
                        "> • Бесплатный супер-префикс перед ником\n\n"
                        "**💬 Твинки и Discord:**\n"
                        "> • Создание до **2 мульти-аккаунтов** (твинков)\n"
                        "> • Личный стикер в Discord-сервере\n\n"
                        "**🏛️ Привилегии сервера:**\n"
                        "> • Приоритетное рассмотрение идей Администрацией\n"
                        "> • Доступ к эксклюзивному чату донатеров (`💬・чат-донатеров`)\n\n"
                        "──────────────────────────────\n"
                        "📌 *По всем вопросам обращайтесь к **@AllCash** или создайте тикет.*"
                    ),
                    color=EMBED_COLOR,
                ).set_image(url=SPACER_URL)
                f_emb.set_footer(text="Проект Litex • Магазин привилегий")

                await channel.send(embeds=[b_emb, i_emb, f_emb], view=PrimeView())
                return web.json_response({"message": f"Панель Prime успешно отправлена в #{channel.name}!"})
            except Exception as e:
                return web.json_response({"message": f"Ошибка отправки Prime: {str(e)}"})

        elif panel_type == "staff":
            try:
                from cogs.staff_apply import StaffApplyView, STAFF_IMAGE_URL, STAFF_SPACER_URL
                b_emb = discord.Embed(color=EMBED_COLOR).set_image(url=STAFF_IMAGE_URL.strip())
                m_emb = discord.Embed(
                    title="📌 Набор в состав проекта Litex",
                    description=(
                        "Хотите стать частью нашей команды и помогать развитию сервера? Выберите желаемый отдел ниже и заполните заявку!\n\n"
                        "📋 **Доступные отделы для подачи:**\n"
                        "> • 🛡️ **Модерация** — следить за порядком и чистотой чатов.\n"
                        "> • 🎧 **Поддержка** — помогать игрокам и разбирать тикеты.\n"
                        "> • 🎬 **Медиа** — снимать контент, стримить и развивать проект."
                    ),
                    color=EMBED_COLOR,
                ).set_image(url=STAFF_SPACER_URL)
                m_emb.set_footer(text="Проект Litex • Центр набора персонала")

                await channel.send(embeds=[b_emb, m_emb], view=StaffApplyView())
                return web.json_response({"message": f"Панель набора успешно отправлена в #{channel.name}!"})
            except Exception as e:
                return web.json_response({"message": f"Ошибка отправки набора: {str(e)}"})

        return web.json_response({"message": "Неизвестный тип панели"})


async def setup(bot: commands.Bot):
    await bot.add_cog(WebDashboard(bot))