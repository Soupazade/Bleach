from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.data.combat import CombatEnemyTemplate
from src.data.items import BANDAGES, CLOTH_SCRAPS, FOOD_SCRAPS, RATION_PACK


DungeonRoomKind = Literal["choice", "combat", "boss"]
ButtonStyleName = Literal["primary", "secondary", "success", "danger"]


@dataclass(frozen=True, slots=True)
class DungeonItemRewardDefinition:
    key: str
    name: str
    description: str
    quantity: int
    item_type: str
    rarity: str
    stackable: bool = True


@dataclass(frozen=True, slots=True)
class DungeonChoiceOptionDefinition:
    key: str
    label: str
    style: ButtonStyleName
    summary_text: str
    xp_reward: int = 0
    kan_reward: int = 0
    reputation_change: int = 0
    heal_hp: int = 0
    heal_stamina: int = 0
    item_rewards: tuple[DungeonItemRewardDefinition, ...] = ()


@dataclass(frozen=True, slots=True)
class DungeonCombatDefinition:
    encounter_title: str
    encounter_description: str
    resolution_title: str
    resolution_description: str
    enemy_template: CombatEnemyTemplate
    xp_reward_win: int
    xp_reward_lose: int
    kan_reward_win: int = 0
    reputation_change_win: int = 0
    item_rewards_win: tuple[DungeonItemRewardDefinition, ...] = ()
    victory_summary_text: str = ""
    failure_summary_text: str = ""


@dataclass(frozen=True, slots=True)
class DungeonRoomDefinition:
    key: str
    map_label: str
    title: str
    description: str
    kind: DungeonRoomKind
    options: tuple[DungeonChoiceOptionDefinition, ...] = ()
    combat: DungeonCombatDefinition | None = None


@dataclass(frozen=True, slots=True)
class DungeonDefinition:
    key: str
    title: str
    subtitle: str
    location_key: str
    stamina_cost: int
    intro_title: str
    intro_description: str
    completion_title: str
    completion_description: str
    rooms: tuple[DungeonRoomDefinition, ...]


RUKONGAI_LOOKOUT = CombatEnemyTemplate(
    key="rukongai_tunnel_lookout",
    name="Lantern Lookout",
    level=1,
    race="Soul",
    rank="Lookout",
    hp=90,
    mana=30,
    power=1,
    defense=1,
    speed=1,
    reiatsu=0,
    reward_xp_win=0,
    reward_xp_lose=0,
)

RUKONGAI_KNIFEHAND = CombatEnemyTemplate(
    key="rukongai_knifehand",
    name="Tunnel Knifehand",
    level=2,
    race="Soul",
    rank="Cutpurse Lead",
    hp=105,
    mana=35,
    power=2,
    defense=1,
    speed=2,
    reiatsu=1,
    reward_xp_win=0,
    reward_xp_lose=0,
)

RUKONGAI_FIRST_DUNGEON = DungeonDefinition(
    key="rukongai_first_dungeon",
    title="The Ragpicker Tunnel",
    subtitle="A first test beneath the worst part of the block.",
    location_key="rukongai_streets",
    stamina_cost=12,
    intro_title="The Ragpicker Tunnel Opens",
    intro_description=(
        "A half-collapsed crawlspace under the lane has turned into a little kingdom for hungry souls with knives. "
        "People around the cookfires whisper that if someone clears it out, the block might breathe easier for a few nights."
    ),
    completion_title="The Tunnel Falls Quiet",
    completion_description=(
        "The lean-to stronghold breaks, the knives stop flashing in the dark, and the lane finally exhales. "
        "For one night in Rukongai, fear has to find another doorway."
    ),
    rooms=(
        DungeonRoomDefinition(
            key="entry_choice",
            map_label="Entry",
            title="A Quiet Mouth in the Rubble",
            description=(
                "The hidden entrance opens behind torn cloth and splintered wood. The air smells like wet ash, old soup, and the kind of hunger that learns to whisper."
            ),
            kind="choice",
            options=(
                DungeonChoiceOptionDefinition(
                    key="check_rags",
                    label="Check the rag bundles",
                    style="primary",
                    summary_text="You work the entrance carefully, lifting bundled cloth and finding a little salvage before the tunnel can take its bite.",
                    xp_reward=4,
                    item_rewards=(
                        DungeonItemRewardDefinition(
                            key=CLOTH_SCRAPS.key,
                            name=CLOTH_SCRAPS.name,
                            description=CLOTH_SCRAPS.description,
                            quantity=2,
                            item_type=CLOTH_SCRAPS.item_type,
                            rarity=CLOTH_SCRAPS.rarity,
                            stackable=CLOTH_SCRAPS.stackable,
                        ),
                    ),
                ),
                DungeonChoiceOptionDefinition(
                    key="listen_cookfire",
                    label="Listen by the cookfire vent",
                    style="success",
                    summary_text="You catch the soft places in the tunnel's rhythm and lift a wrapped meal before anyone below notices what went missing.",
                    xp_reward=4,
                    kan_reward=10,
                    reputation_change=1,
                    item_rewards=(
                        DungeonItemRewardDefinition(
                            key=FOOD_SCRAPS.key,
                            name=FOOD_SCRAPS.name,
                            description=FOOD_SCRAPS.description,
                            quantity=1,
                            item_type=FOOD_SCRAPS.item_type,
                            rarity=FOOD_SCRAPS.rarity,
                            stackable=FOOD_SCRAPS.stackable,
                        ),
                    ),
                ),
            ),
        ),
        DungeonRoomDefinition(
            key="lookout_fight",
            map_label="Lookout",
            title="The Lantern Dead-End",
            description=(
                "The tunnel narrows into a dead-end watched by one bad lantern and one worse soul. He hears you before he sees you, and that is enough."
            ),
            kind="combat",
            combat=DungeonCombatDefinition(
                encounter_title="Lantern Dead-End",
                encounter_description=(
                    "The lookout kicks off the wall and comes in low with a rusted blade. There is not enough room to dance here. Only enough room to finish it."
                ),
                resolution_title="The Lookout Drops",
                resolution_description=(
                    "You put the watcher down before he can bring the whole tunnel crashing in on you. The weak lantern keeps shaking after the fight, but the warning never goes out."
                ),
                enemy_template=RUKONGAI_LOOKOUT,
                xp_reward_win=10,
                xp_reward_lose=3,
                kan_reward_win=12,
                victory_summary_text="You put the tunnel lookout down and take the first real breath the run has allowed you.",
                failure_summary_text="The lookout keeps his feet and the tunnel spits you back toward the street before you can press deeper.",
            ),
        ),
        DungeonRoomDefinition(
            key="cache_choice",
            map_label="Cache",
            title="A Lean-To Cache",
            description=(
                "Past the dead-end, somebody carved out a pocket in the earth and called it a supply room. It is miserable work, but miserable work still keeps people alive down here."
            ),
            kind="choice",
            options=(
                DungeonChoiceOptionDefinition(
                    key="patch_up",
                    label="Patch yourself up",
                    style="success",
                    summary_text="You grab the cleanest wraps in the cache and make them count before the next push.",
                    xp_reward=3,
                    heal_hp=18,
                    item_rewards=(
                        DungeonItemRewardDefinition(
                            key=BANDAGES.key,
                            name=BANDAGES.name,
                            description=BANDAGES.description,
                            quantity=1,
                            item_type=BANDAGES.item_type,
                            rarity=BANDAGES.rarity,
                            stackable=BANDAGES.stackable,
                        ),
                    ),
                ),
                DungeonChoiceOptionDefinition(
                    key="take_rations",
                    label="Sweep the ration shelf",
                    style="primary",
                    summary_text="You clear what can still be carried and leave the empty boards behind.",
                    xp_reward=3,
                    kan_reward=15,
                    item_rewards=(
                        DungeonItemRewardDefinition(
                            key=RATION_PACK.key,
                            name=RATION_PACK.name,
                            description=RATION_PACK.description,
                            quantity=1,
                            item_type=RATION_PACK.item_type,
                            rarity=RATION_PACK.rarity,
                            stackable=RATION_PACK.stackable,
                        ),
                    ),
                ),
            ),
        ),
        DungeonRoomDefinition(
            key="boss_fight",
            map_label="Boss",
            title="The Knifehand's Corner",
            description=(
                "The far chamber is barely a room at all, just hanging cloth, a crate-table, and a soul mean enough to build a throne out of everyone else's fear."
            ),
            kind="boss",
            combat=DungeonCombatDefinition(
                encounter_title="The Knifehand's Corner",
                encounter_description=(
                    "The cutpurse lead rises from his crate-table with the kind of smile only desperate men mistake for confidence. He does not plan to let you leave with the lane."
                ),
                resolution_title="The Knifehand Breaks",
                resolution_description=(
                    "You break the stronghold's last hard point and leave the corner quieter than you found it. In a place like this, that counts as mercy."
                ),
                enemy_template=RUKONGAI_KNIFEHAND,
                xp_reward_win=18,
                xp_reward_lose=5,
                kan_reward_win=30,
                reputation_change_win=3,
                item_rewards_win=(
                    DungeonItemRewardDefinition(
                        key=RATION_PACK.key,
                        name=RATION_PACK.name,
                        description=RATION_PACK.description,
                        quantity=1,
                        item_type=RATION_PACK.item_type,
                        rarity=RATION_PACK.rarity,
                        stackable=RATION_PACK.stackable,
                    ),
                ),
                victory_summary_text="The stronghold caves with its leader, and the tunnel finally belongs to the block again.",
                failure_summary_text="The stronghold holds. You get out with what breath and pride you can still drag after you.",
            ),
        ),
    ),
)


DUNGEON_DEFINITIONS = {
    RUKONGAI_FIRST_DUNGEON.key: RUKONGAI_FIRST_DUNGEON,
}


def get_dungeon_definition(dungeon_key: str) -> DungeonDefinition:
    try:
        return DUNGEON_DEFINITIONS[dungeon_key]
    except KeyError as error:
        raise ValueError(f"Unknown dungeon definition: {dungeon_key}") from error


def get_first_dungeon_definition() -> DungeonDefinition:
    return RUKONGAI_FIRST_DUNGEON
