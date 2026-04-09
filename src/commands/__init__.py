from src.commands.profile import register_profile_command
from src.commands.start import register_start_command


def register_commands(bot) -> None:
    register_start_command(bot)
    register_profile_command(bot)
