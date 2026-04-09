from src.commands.explore import register_explore_command
from src.commands.profile import register_profile_command
from src.commands.rest import register_rest_command
from src.commands.staff import register_staff_commands
from src.commands.start import register_start_command


def register_commands(bot) -> None:
    register_start_command(bot)
    register_profile_command(bot)
    register_explore_command(bot)
    register_rest_command(bot)
    register_staff_commands(bot)
