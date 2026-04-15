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
    key="rukongai_outskirts_scout",
    name="Outskirts Scout",
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
    key="rukongai_hideout_boss",
    name="Bandit Handler",
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
    title="The Briar Den",
    subtitle="A rough first run through an Outskirts bandit hideout.",
    location_key="rukongai_outskirts",
    stamina_cost=12,
    intro_title="The Briar Den Waits",
    intro_description=(
        "Past the last broken shacks of the Outskirts, a nest of scavengers and cutthroats has taken over a ruined camp hidden behind briars and leaning timber. "
        "People on the edge say supplies disappear there, and sometimes people do too."
    ),
    completion_title="The Briar Den Falls Quiet",
    completion_description=(
        "The hideout breaks apart, the watchfires burn low, and the edge of the Outskirts feels a little less owned by fear. "
        "That is as close to peace as this district usually gets."
    ),
    rooms=(
        DungeonRoomDefinition(
            key="entry_choice",
            map_label="Entry",
            title="The Thorn Gap",
            description=(
                "A narrow opening in the briars leads into a ring of half-rotten barricades and old camp ash. The wind carries wet earth, smoke, and the smell of people trying to survive by becoming worse."
            ),
            kind="choice",
            options=(
                DungeonChoiceOptionDefinition(
                    key="check_rags",
                    label="Search the outer stash",
                    style="primary",
                    summary_text="You work the edge of the hideout carefully and come away with usable salvage before anyone deeper in the camp catches on.",
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
                    label="Listen by the watchfire",
                    style="success",
                    summary_text="You catch the rhythm of the camp, lift a wrapped meal, and learn how the sentries are handing the night off to each other.",
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
            map_label="Scout",
            title="The Outer Watchpost",
            description=(
                "A crooked watchpost stands between you and the camp proper. One lean soul is posted there with a blade, a bad attitude, and just enough discipline to be dangerous."
            ),
            kind="combat",
            combat=DungeonCombatDefinition(
                encounter_title="The Outer Watchpost",
                encounter_description=(
                    "The scout drops from the timber rail and comes straight at you with a scavenged knife. There is no room here for hesitation, only a short ugly clash in the dirt."
                ),
                resolution_title="The Scout Goes Down",
                resolution_description=(
                    "You put the sentry down before the alarm can spread through the hideout. The watchfire still spits and cracks, but nobody comes running."
                ),
                enemy_template=RUKONGAI_LOOKOUT,
                xp_reward_win=10,
                xp_reward_lose=3,
                kan_reward_win=12,
                victory_summary_text="The outer scout drops, and the hideout opens a little wider in front of you.",
                failure_summary_text="The scout holds long enough to ruin your push, and the Outskirts spit you back before you can reach the heart of the camp.",
            ),
        ),
        DungeonRoomDefinition(
            key="cache_choice",
            map_label="Cache",
            title="A Raiders' Supply Lean-To",
            description=(
                "Just inside the camp proper, somebody threw together a supply lean-to from warped boards and old cloth. It is crude, but crude still feeds people and keeps knives in their hands."
            ),
            kind="choice",
            options=(
                DungeonChoiceOptionDefinition(
                    key="patch_up",
                    label="Wrap your wounds",
                    style="success",
                    summary_text="You pull the cleanest wraps from the lean-to and patch yourself up before the next hard push.",
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
                    label="Raid the supply shelf",
                    style="primary",
                    summary_text="You strip the useful supplies out of the lean-to and leave the shelf looking like hunger already got there first.",
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
            title="The Handler's Shack",
            description=(
                "At the back of the camp, the bandit handler keeps a crooked shack lit by low coals and bad confidence. This is where the stolen food ends up, and where the ugliest decisions get made."
            ),
            kind="boss",
            combat=DungeonCombatDefinition(
                encounter_title="The Handler's Shack",
                encounter_description=(
                    "The bandit handler rises from his crate-table with a scavenger's grin and a killer's patience. He has held this patch of the Outskirts through fear, and he does not plan to hand it over."
                ),
                resolution_title="The Handler Breaks",
                resolution_description=(
                    "You break the hideout's last hard point and leave the shack quieter than you found it. Out here, that counts as a kind of justice."
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
                victory_summary_text="The hideout caves with its handler, and the edge of the Outskirts belongs to the desperate instead of the cruel for one more night.",
                failure_summary_text="The handler holds the camp. You get out with what breath and pride you can still drag back through the briars.",
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
