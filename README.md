# litex bot

Discord-бот для сервера **litex**: верификация новичков, аналитика саппортов и отзывы об их работе.

## Что умеет

| Функция | Как работает |
|---|---|
| Автовыдача роли | Стартовая роль выдаётся при входе на сервер, а также всем, у кого нет ни одной роли: при запуске бота выдаёт её уже сидящим на сервере без ролей, а позже — если у человека пропали все роли |
| `/accept пользователь` | Выдаёт роль «Участник», снимает стартовую (и роль отказа, если была), пишет проверку в БД и лог, просит оценку в ЛС |
| `/denied пользователь причина` | Выдаёт роль «Недопущен», снимает стартовую, в лог — кто проверял, кому отказано, возраст аккаунта, причина |
| Оценка саппорта | После проверки в ЛС приходят кнопки `1 ⭐` … `5 ⭐` → форма с необязательным комментарием. Один отзыв на одну проверку |
| `/support_top` | Топ саппортов по числу проверок (виден только вам) |
| `/support_profile member` | Профиль саппорта: статистика за сутки / неделю / месяц / всё время, время в проходной, рейтинг, кнопка с отзывами (по 5 на странице) |
| `/cheatsheet` | Шпаргалка по функционалу бота. Саппорты могут отправить её в канал: `/cheatsheet public:True` |
| Учёт голоса | Время саппортов в трёх голосовых каналах «проходной» суммируется автоматически |

`/accept` и `/denied` доступны только ролям из `STAFF_ROLE_IDS` и администраторам.
Нельзя проверять ботов и самого себя.

## Требования

- Python **3.10+**
- Бот, созданный в [Discord Developer Portal](https://discord.com/developers/applications)

## Настройка бота в Developer Portal

1. **New Application** → вкладка **Bot** → **Reset Token** → скопируйте токен.
2. Там же, в **Privileged Gateway Intents**, включите **Server Members Intent** (без него бот не запустится).
3. **OAuth2 → URL Generator**: scopes `bot` и `applications.commands`; права бота:
   *Manage Roles*, *View Channels*, *Send Messages*, *Embed Links*. Откройте ссылку и добавьте бота на сервер.
4. На сервере поднимите **роль бота выше** ролей «Участник», «Недопущен» и стартовой — иначе Discord не даст ему их выдавать.

## Установка и запуск

```bash
cd litex_bot

# 1. виртуальное окружение (рекомендуется)
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. зависимости
pip install -r requirements.txt

# 3. настройки
cp .env.example .env             # Windows: copy .env.example .env
# откройте .env и впишите DISCORD_TOKEN (и GUILD_ID — ID вашего сервера)

# 4. запуск
python main.py
```

При первом запуске бот сам создаёт файл базы `litex.db` и таблицы. В логе должно появиться
`Синхронизировано слэш-команд: 5` и `Бот запущен как ...`.

> Если указан `GUILD_ID`, команды появляются на сервере сразу. Без него синхронизация глобальная и может занять до часа.

## Структура проекта

```
litex_bot/
├── main.py              # запуск бота, intents, синхронизация команд
├── config.py            # токен из .env + все ID ролей и каналов
├── database.py          # SQLite (aiosqlite): таблицы и запросы
├── utils.py             # проверка прав staff, форматирование времени
├── cogs/
│   ├── verification.py  # автороль, /accept, /denied, оценка в ЛС
│   ├── voice.py         # учёт времени в проходной
│   ├── profile.py       # /support_top, /support_profile, пагинация отзывов
│   └── help.py          # /cheatsheet
├── requirements.txt
├── .env.example
└── README.md
```

## База данных

SQLite-файл `litex.db` (путь можно поменять через `DB_PATH` в `.env`). Таблицы:

- `verifications` — саппорт, пользователь, действие (`accept` / `denied`), причина, время
- `reviews` — саппорт, автор, оценка 1–5, комментарий (или `NULL`), дата `ДД.ММ.ГГГГ`
- `voice_time` — суммарные секунды каждого саппорта в проходной

Для бэкапа достаточно копировать `litex.db` (пока бот остановлен).

## Как поменять ID ролей и каналов

Все ID лежат в `config.py`: `START_ROLE_ID`, `MEMBER_ROLE_ID`, `DENIED_ROLE_ID`, `STAFF_ROLE_IDS`,
`LOG_CHANNEL_ID`, `GATE_VOICE_CHANNEL_IDS`. После правки перезапустите бота.

## Особенности

- Кнопки оценки в ЛС продолжают работать и после перезапуска бота.
- Время в проходной учитывается только у участников с ролью саппорта / администраторов. Переход между каналами проходной не обрывает сессию. Накопленное время дописывается в БД каждые 5 минут и при остановке бота.
- Если у пользователя закрыты ЛС, саппорт увидит предупреждение — проверка при этом всё равно засчитывается.
- Если канал логов недоступен боту, проверка засчитывается, а саппорт получает предупреждение.

## Если что-то не работает

| Симптом | Причина |
|---|---|
| `PrivilegedIntentsRequired` при запуске | Не включён Server Members Intent (шаг 2 настройки) |
| Команд не видно | Не указан `GUILD_ID` (ждите до часа) или бот добавлен без scope `applications.commands` |
| «У бота не хватает прав на выдачу ролей» | Роль бота ниже выдаваемых ролей или нет права *Manage Roles* |
| Нет записей в канале логов | У бота нет доступа к каналу `LOG_CHANNEL_ID` (View Channel / Send Messages / Embed Links) |
| Новичкам не выдаётся стартовая роль | Та же причина с иерархией ролей, либо не включён Members Intent |
| `ZoneInfoNotFoundError` на Windows | Установите зависимости заново: `pip install -r requirements.txt` (нужен пакет `tzdata`) |

## Запуск на сервере 24/7 (Linux, systemd)

`/etc/systemd/system/litex-bot.service`:

```ini
[Unit]
Description=litex Discord bot
After=network-online.target

[Service]
WorkingDirectory=/opt/litex_bot
ExecStart=/opt/litex_bot/.venv/bin/python main.py
Restart=always
User=litex

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now litex-bot
journalctl -u litex-bot -f      # логи
```
