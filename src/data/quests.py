from __future__ import annotations

from src.data.quest_dialogue import KAITO_SOULS_FIRST_DAY_PROMPTS
from src.models.quest import (
    QuestDefinition,
    QuestRewardDefinition,
    QuestRewardItemDefinition,
    QuestStepDefinition,
    QuestStepRequirement,
)


SOULS_FIRST_DAY_QUEST = QuestDefinition(
    key="a_souls_first_day",
    category="main",
    title="A Soul's First Day",
    short_description="Kaito shows you the first hard rules of surviving Rukongai.",
    guide_name="Kaito",
    difficulty="Tutorial",
    lore_summary=(
        "Fresh souls do not arrive in Rukongai to comfort. They arrive hungry, confused, and easy to overlook. "
        "Kaito is one of the many strays trying to last another day in the district, and he has learned that pity "
        "only matters if it keeps someone moving."
    ),
    briefing_objective=(
        "Survive your first real stretch in Rukongai by following Kaito through four lessons: search the streets, "
        "turn scraps into supplies, move toward opportunity, and harden yourself in the Training Yard."
    ),
    min_level=1,
    auto_start=False,
    steps=(
        QuestStepDefinition(
            title="Find Something to Hold Onto",
            narrative_prompt=KAITO_SOULS_FIRST_DAY_PROMPTS["explore"],
            system_explanation=(
                "`/explore` is one of your main ways to progress through Rukongai.",
                "Exploring can uncover useful materials, dangerous encounters, strange events, and direct rewards.",
                "Successful runs also grant experience, so exploration is one of your core gameplay loops.",
            ),
            objective="Use `/explore` and commit to one exploration run.",
            requirement=QuestStepRequirement(action_type="explore_completed"),
        ),
        QuestStepDefinition(
            title="Make Do With What You Have",
            narrative_prompt=KAITO_SOULS_FIRST_DAY_PROMPTS["craft"],
            system_explanation=(
                "Crafting turns gathered materials into items you can actually rely on.",
                "Basic crafted supplies can restore health, recover stamina, or give you practical support.",
                "Exploration finds the scraps. Crafting turns those scraps into an advantage.",
            ),
            objective="Craft a basic item like `Bandages` or a `Ration Pack` with `/craft`.",
            requirement=QuestStepRequirement(
                action_type="craft_item",
                accepted_item_keys=("bandages", "ration_pack"),
            ),
        ),
        QuestStepDefinition(
            title="Move Before the Streets Swallow You",
            narrative_prompt=KAITO_SOULS_FIRST_DAY_PROMPTS["travel"],
            system_explanation=(
                "`/travel` moves you between locations across Rukongai.",
                "Different locations unlock different actions, opportunities, and rewards.",
                "The Training Yard is where you improve your stats, so where you stand matters.",
            ),
            objective="Use `/travel` to reach the `Rukongai Training Yard`.",
            requirement=QuestStepRequirement(
                action_type="travel_completed",
                required_location="rukongai_training_yard",
            ),
        ),
        QuestStepDefinition(
            title="Push Yourself",
            narrative_prompt=KAITO_SOULS_FIRST_DAY_PROMPTS["train"],
            system_explanation=(
                "`/train` improves your core stats and builds raw strength over time.",
                "Better stats make you stronger in combat and better prepared for harder districts.",
                "Training is steadier and more controlled than exploration. Exploration drives events and XP, while training builds your foundation.",
            ),
            objective="Use `/train` once and begin a training session.",
            requirement=QuestStepRequirement(action_type="training_started"),
        ),
    ),
    reward=QuestRewardDefinition(
        xp=15,
        kan=100,
        reputation=20,
        stat_points=5,
        items=(
            QuestRewardItemDefinition(item_key="ration_pack", quantity=2),
            QuestRewardItemDefinition(item_key="bandages", quantity=2),
        ),
    ),
    completion_text=KAITO_SOULS_FIRST_DAY_PROMPTS["complete"],
)


QUEST_DEFINITIONS: dict[str, QuestDefinition] = {
    SOULS_FIRST_DAY_QUEST.key: SOULS_FIRST_DAY_QUEST,
}


QUESTS_BY_CATEGORY = {
    "main": (SOULS_FIRST_DAY_QUEST,),
    "side": (),
    "daily": (),
    "repeatable": (),
}


def get_quest_definition(quest_key: str) -> QuestDefinition:
    try:
        return QUEST_DEFINITIONS[quest_key]
    except KeyError as error:
        raise ValueError(f"Unknown quest definition: {quest_key}") from error


def list_quests_for_category(category: str) -> tuple[QuestDefinition, ...]:
    return QUESTS_BY_CATEGORY.get(category, ())
