from src.commands.craft import register_craft_command
from src.commands.dungeon import register_dungeon_command
from src.commands.explore import register_explore_command
from src.commands.fightlog import register_fightlog_command
from src.commands.fighttest import register_fighttest_command
from src.commands.inventory import register_inventory_command
from src.commands.profile import register_profile_command
from src.commands.quest import register_quest_command
from src.commands.rest import register_rest_command
from src.commands.shop import register_shop_command
from src.commands.staff import register_staff_commands
from src.commands.start import register_start_command
from src.commands.train import register_train_command
from src.commands.travel import register_travel_command
from src.commands.use import register_use_command


def register_commands(bot) -> None:
    register_start_command(bot)
    register_profile_command(bot)
    register_quest_command(bot)
    register_inventory_command(bot)
    register_craft_command(bot)
    register_use_command(bot)
    register_shop_command(bot)
    register_fighttest_command(bot)
    register_dungeon_command(bot)
    register_explore_command(bot)
    register_train_command(bot)
    register_travel_command(bot)
    register_rest_command(bot)
    register_staff_commands(bot)
    register_fightlog_command(bot)
