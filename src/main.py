import asyncio
import logging
import os

import discord
from discord import app_commands
from dotenv import load_dotenv

from src.commands import register_commands
from src.database import create_pool, ensure_schema
from src.services.combat_service import get_active_exploration_combat, restore_combat_tasks
from src.services.exploration_service import restore_exploration_tasks
from src.services.training_service import restore_training_tasks
from src.services.travel_service import restore_travel_tasks
from src.ui.exploration_combat_view import ExplorationCombatView
from src.ui.exploration_combat_view import build_active_combat_embed
from src.ui.exploration_choice_view import ExplorationChoiceView


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


class IgnoreDiscordNoise(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        ignored_messages = {
            "PyNaCl is not installed, voice will NOT be supported",
        }
        return record.getMessage() not in ignored_messages


logging.getLogger("discord.client").addFilter(IgnoreDiscordNoise())

load_dotenv()


class BleachCommandTree(app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        client = self.client
        if not isinstance(client, BleachBot) or client.db_pool is None:
            return True

        active_combat = await get_active_exploration_combat(client.db_pool, interaction.user.id)
        if active_combat is None:
            return True

        if interaction.response.is_done():
            await interaction.followup.send(
                embed=build_active_combat_embed(active_combat, interaction.user),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                embed=build_active_combat_embed(active_combat, interaction.user),
                ephemeral=True,
            )
        return False


class BleachBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.db_pool = None
        self.guild_id = self._parse_guild_id()
        self.tree = BleachCommandTree(self)
        self.exploration_tasks: dict[int, asyncio.Task] = {}
        self.exploration_message_refs: dict[int, int] = {}
        self.combat_tasks: dict[int, asyncio.Task] = {}
        self.training_tasks: dict[int, asyncio.Task] = {}
        self.travel_tasks: dict[int, asyncio.Task] = {}
        self.recent_combat_resolutions: dict[int, object] = {}
        register_commands(self)

    @staticmethod
    def _parse_guild_id() -> int | None:
        guild_id = os.getenv("DISCORD_GUILD_ID")
        if not guild_id:
            return None

        try:
            return int(guild_id)
        except ValueError:
            raise RuntimeError("DISCORD_GUILD_ID must be a valid integer.") from None

    async def setup_hook(self) -> None:
        self.db_pool = await create_pool()
        await ensure_schema(self.db_pool)
        self.add_view(ExplorationChoiceView(self))
        await restore_exploration_tasks(self)
        await restore_combat_tasks(self)
        await restore_training_tasks(self)
        await restore_travel_tasks(self)

        if self.guild_id is not None:
            guild = discord.Object(id=self.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logging.info("Synced %s command(s) to guild %s", len(synced), self.guild_id)
        else:
            synced = await self.tree.sync()
            logging.info("Synced %s global command(s)", len(synced))

    async def on_ready(self) -> None:
        if self.user is None:
            return

        logging.info("Logged in as %s", self.user)

    async def close(self) -> None:
        for task in self.exploration_tasks.values():
            task.cancel()
        for task in self.combat_tasks.values():
            task.cancel()
        for task in self.training_tasks.values():
            task.cancel()
        for task in self.travel_tasks.values():
            task.cancel()

        self.exploration_tasks.clear()
        self.exploration_message_refs.clear()
        self.combat_tasks.clear()
        self.training_tasks.clear()
        self.travel_tasks.clear()
        if self.db_pool is not None:
            await self.db_pool.close()
        await super().close()


bot = BleachBot()


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    if isinstance(error, app_commands.CheckFailure):
        message = str(error) or "You do not have permission to use that command."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
        return

    logging.error(
        "Unhandled app command error.",
        exc_info=(type(error), error, error.__traceback__),
    )
    if interaction.response.is_done():
        await interaction.followup.send(
            "Something went wrong while running that command.",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            "Something went wrong while running that command.",
            ephemeral=True,
        )


def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN is required.")

    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
