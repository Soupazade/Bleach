from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Literal

from src.models.effects import PlayerEffectType


ExploreResultTone = Literal["positive", "negative"]


@dataclass(frozen=True, slots=True)
class ExploreEffectTemplate:
    key: str
    title: str
    description: str
    effect_type: PlayerEffectType
    magnitude: int
    duration_minutes: int | None = None
    remaining_explores: int | None = None


POSITIVE_EXPLORE_EFFECTS = (
    ExploreEffectTemplate(
        key="warm_broth",
        title="Warm Broth",
        description="A cookfire widow presses a hot bowl into your hands. The heat reaches deeper than the soup should.",
        effect_type="stamina_flat",
        magnitude=5,
    ),
    ExploreEffectTemplate(
        key="street_brew",
        title="Street Brew",
        description="A bitter little bottle changes hands in the dark. It tastes awful and wakes every nerve you have.",
        effect_type="stamina_regen_pct",
        magnitude=25,
        duration_minutes=60,
    ),
    ExploreEffectTemplate(
        key="full_belly",
        title="Full Belly",
        description="You manage a real meal instead of scraps. It is not much by Seireitei standards, but it is enough to sharpen the next few runs.",
        effect_type="xp_boost_pct",
        magnitude=25,
        remaining_explores=2,
    ),
    ExploreEffectTemplate(
        key="borrowed_grit",
        title="Borrowed Grit",
        description="A rough hand clasps your shoulder before you part ways. The words are short. The fire they leave behind is not.",
        effect_type="power_pct",
        magnitude=15,
        duration_minutes=60,
    ),
    ExploreEffectTemplate(
        key="scrap_wrappings",
        title="Scrap Wrappings",
        description="Someone who has seen too many alley fights shows you how to bind the weak points under your clothes.",
        effect_type="defense_pct",
        magnitude=15,
        duration_minutes=60,
    ),
    ExploreEffectTemplate(
        key="shortcut_feet",
        title="Shortcut Feet",
        description="A local points out a cleaner line through the district. Suddenly your steps know where not to die.",
        effect_type="speed_pct",
        magnitude=15,
        duration_minutes=60,
    ),
    ExploreEffectTemplate(
        key="quiet_focus",
        title="Quiet Focus",
        description="A brief moment of stillness lets your breathing settle and your reiatsu stop spilling in all directions.",
        effect_type="reiatsu_pct",
        magnitude=15,
        duration_minutes=60,
    ),
    ExploreEffectTemplate(
        key="bandaged_up",
        title="Bandaged Up",
        description="A careful stranger patches you with cleaner cloth than these streets usually offer. You feel steadier for it.",
        effect_type="hp_pct",
        magnitude=15,
        duration_minutes=60,
    ),
    ExploreEffectTemplate(
        key="soul_drops",
        title="Soul Drops",
        description="A cheap little tonic steadies the spiritual ache behind your eyes and leaves your reserves brighter.",
        effect_type="mana_pct",
        magnitude=15,
        duration_minutes=60,
    ),
    ExploreEffectTemplate(
        key="back_alley_voucher",
        title="Back-Alley Voucher",
        description="A trader with nervous hands slips you a marked chit and mutters that somebody farther up the lane owes you a better deal.",
        effect_type="shop_discount_pct",
        magnitude=25,
        duration_minutes=60,
    ),
    ExploreEffectTemplate(
        key="safe_route",
        title="Safe Route",
        description="A runner scratches a cleaner path through the district onto torn paper. It will not stay safe forever, but it should hold for a while.",
        effect_type="travel_time_flat",
        magnitude=-1,
        duration_minutes=60,
    ),
    ExploreEffectTemplate(
        key="crowd_intel",
        title="Crowd Intel",
        description="By the time the murmurs die, you know where trouble usually steps from and how long it takes fear to turn into violence.",
        effect_type="combat_focus_flat",
        magnitude=4,
        duration_minutes=60,
    ),
    ExploreEffectTemplate(
        key="street_favor",
        title="Street Favor",
        description="Someone in the block quietly puts your name in the right ear. It does not make the streets kind. It just makes them a little less closed.",
        effect_type="special_trigger_pct",
        magnitude=10,
        duration_minutes=60,
    ),
)

NEGATIVE_EXPLORE_EFFECTS = (
    ExploreEffectTemplate(
        key="bad_skewers",
        title="Bad Skewers",
        description="You eat because hungry souls do not get to be picky. A few minutes later, your stomach makes you regret it.",
        effect_type="stamina_flat",
        magnitude=-5,
    ),
    ExploreEffectTemplate(
        key="ash_lungs",
        title="Ash in the Lungs",
        description="Smoke, dust, and alley stink cling to your chest. Breathing turns heavier than it should.",
        effect_type="stamina_regen_pct",
        magnitude=-25,
        duration_minutes=60,
    ),
    ExploreEffectTemplate(
        key="shaking_hands",
        title="Shaking Hands",
        description="Your knuckles still hum from the last hard exchange. There is strength there, but not the clean kind.",
        effect_type="power_pct",
        magnitude=-15,
        duration_minutes=60,
    ),
    ExploreEffectTemplate(
        key="bruised_guard",
        title="Bruised Guard",
        description="You caught one hit too flush. Every raised arm reminds you of it.",
        effect_type="defense_pct",
        magnitude=-15,
        duration_minutes=60,
    ),
    ExploreEffectTemplate(
        key="twisted_ankle",
        title="Twisted Ankle",
        description="One bad landing in broken stone leaves your footing off by just enough to matter.",
        effect_type="speed_pct",
        magnitude=-15,
        duration_minutes=60,
    ),
    ExploreEffectTemplate(
        key="rattled_focus",
        title="Rattled Focus",
        description="Too much noise, too little calm. Your reiatsu keeps slipping every time you try to gather it cleanly.",
        effect_type="reiatsu_pct",
        magnitude=-15,
        duration_minutes=60,
    ),
    ExploreEffectTemplate(
        key="split_lip",
        title="Split Lip",
        description="You are still upright, but the street tagged you before it let you leave.",
        effect_type="hp_pct",
        magnitude=-15,
        duration_minutes=60,
    ),
    ExploreEffectTemplate(
        key="drained_nerves",
        title="Drained Nerves",
        description="Whatever steadiness you had burns off fast. The next draw on your spirit feels thinner.",
        effect_type="mana_pct",
        magnitude=-15,
        duration_minutes=60,
    ),
)


def _roll_from_pool(
    pool: tuple[ExploreEffectTemplate, ...],
) -> ExploreEffectTemplate:
    return random.choice(pool)


def get_exploration_effect_template(
    *,
    event_type: Literal["reward", "combat", "choice", "flavor"],
    combat_outcome: str | None,
    reputation_change: int,
) -> ExploreEffectTemplate | None:
    if event_type == "reward":
        return _roll_from_pool(POSITIVE_EXPLORE_EFFECTS) if random.random() < 0.35 else None

    if event_type == "flavor":
        if random.random() >= 0.22:
            return None
        return _roll_from_pool(POSITIVE_EXPLORE_EFFECTS if random.random() < 0.65 else NEGATIVE_EXPLORE_EFFECTS)

    if event_type == "combat":
        if combat_outcome == "Victory":
            return _roll_from_pool(POSITIVE_EXPLORE_EFFECTS) if random.random() < 0.24 else None
        if combat_outcome == "Setback":
            return _roll_from_pool(NEGATIVE_EXPLORE_EFFECTS) if random.random() < 0.42 else None
        return None

    if event_type == "choice":
        if reputation_change > 0:
            return _roll_from_pool(POSITIVE_EXPLORE_EFFECTS) if random.random() < 0.34 else None
        if reputation_change < 0:
            return _roll_from_pool(NEGATIVE_EXPLORE_EFFECTS) if random.random() < 0.34 else None
        return _roll_from_pool(POSITIVE_EXPLORE_EFFECTS if random.random() < 0.55 else NEGATIVE_EXPLORE_EFFECTS) if random.random() < 0.26 else None

    return None
