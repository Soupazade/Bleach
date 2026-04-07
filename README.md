# Bleach

Bleach RPG Bot starter built with `discord.py` and `PostgreSQL`.

## Tech Stack

- Python 3.11+
- discord.py
- PostgreSQL
- asyncpg

## Local Setup

1. Create a virtual environment:

```bash
python -m venv .venv
```

2. Activate it:

```bash
.venv\Scripts\Activate.ps1
```

3. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

4. Start the bot:

```bash
python main.py
```

## Required Environment Variables

- `DISCORD_TOKEN`
- `DISCORD_CLIENT_ID`
- `DISCORD_GUILD_ID`
- `DATABASE_URL`

## Commands

- `/ping` replies with bot latency information

## Notes

- The bot auto-syncs slash commands to the guild in `DISCORD_GUILD_ID` on startup.
- On startup, it also ensures a `player_profiles` table exists in PostgreSQL.
- `DISCORD_CLIENT_ID` is kept for future invite/deployment use, even though this starter does not need it to run.
