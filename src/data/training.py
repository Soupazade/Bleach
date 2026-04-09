from __future__ import annotations

from dataclasses import dataclass
from math import ceil


TRAINING_YARD_LOCATION_KEY = "rukongai_training_yard"
TRAINING_MILESTONE_MINUTES = 15
ALL_STATS_KEY = "all_stats"
ALL_STATS_PROGRESS_ORDER = ("power", "defense", "speed", "reiatsu")


@dataclass(frozen=True, slots=True)
class TrainingFocusDefinition:
    key: str
    label: str
    stat_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TrainingDurationDefinition:
    minutes: int
    stamina_cost: int
    single_stat_reward: int


TRAINING_FOCUSES = {
    "power": TrainingFocusDefinition("power", "Power", ("power",)),
    "defense": TrainingFocusDefinition("defense", "Defense", ("defense",)),
    "speed": TrainingFocusDefinition("speed", "Speed", ("speed",)),
    "reiatsu": TrainingFocusDefinition("reiatsu", "Reiatsu", ("reiatsu",)),
    ALL_STATS_KEY: TrainingFocusDefinition(
        ALL_STATS_KEY,
        "All Stats",
        ALL_STATS_PROGRESS_ORDER,
    ),
}

TRAINING_DURATIONS = {
    15: TrainingDurationDefinition(15, 5, 1),
    30: TrainingDurationDefinition(30, 10, 2),
    45: TrainingDurationDefinition(45, 12, 3),
    60: TrainingDurationDefinition(60, 15, 5),
}


def get_training_focus(focus_key: str) -> TrainingFocusDefinition:
    try:
        return TRAINING_FOCUSES[focus_key]
    except KeyError as error:
        raise ValueError(f"Unknown training focus: {focus_key}") from error


def get_training_duration(duration_minutes: int) -> TrainingDurationDefinition:
    try:
        return TRAINING_DURATIONS[duration_minutes]
    except KeyError as error:
        raise ValueError(f"Unknown training duration: {duration_minutes}") from error


def get_training_duration_options(focus_key: str | None = None) -> tuple[TrainingDurationDefinition, ...]:
    if focus_key == ALL_STATS_KEY:
        return (TRAINING_DURATIONS[60],)

    return tuple(TRAINING_DURATIONS[minutes] for minutes in (15, 30, 45, 60))


def is_valid_training_selection(focus_key: str, duration_minutes: int) -> bool:
    if focus_key not in TRAINING_FOCUSES or duration_minutes not in TRAINING_DURATIONS:
        return False

    if focus_key == ALL_STATS_KEY:
        return duration_minutes == 60

    return True


def get_training_full_reward(focus_key: str, duration_minutes: int) -> dict[str, int]:
    if not is_valid_training_selection(focus_key, duration_minutes):
        raise ValueError("Invalid training selection.")

    if focus_key == ALL_STATS_KEY:
        return {stat_name: 1 for stat_name in ALL_STATS_PROGRESS_ORDER}

    focus = get_training_focus(focus_key)
    duration = get_training_duration(duration_minutes)
    return {focus.stat_fields[0]: duration.single_stat_reward}


def get_training_milestones_completed(duration_minutes: int, elapsed_minutes: int) -> int:
    available_milestones = duration_minutes // TRAINING_MILESTONE_MINUTES
    return max(0, min(available_milestones, elapsed_minutes // TRAINING_MILESTONE_MINUTES))


def get_training_earned_reward(
    focus_key: str,
    duration_minutes: int,
    elapsed_minutes: int,
) -> dict[str, int]:
    if not is_valid_training_selection(focus_key, duration_minutes):
        raise ValueError("Invalid training selection.")

    milestones_completed = get_training_milestones_completed(duration_minutes, elapsed_minutes)
    if milestones_completed <= 0:
        return {}

    if focus_key == ALL_STATS_KEY:
        return {
            stat_name: 1
            for stat_name in ALL_STATS_PROGRESS_ORDER[:milestones_completed]
        }

    focus = get_training_focus(focus_key)
    if duration_minutes == 60 and milestones_completed >= 4:
        return {focus.stat_fields[0]: 5}

    return {focus.stat_fields[0]: milestones_completed}


def get_training_early_stop_reward(
    focus_key: str,
    duration_minutes: int,
    elapsed_minutes: int,
) -> dict[str, int]:
    if elapsed_minutes < TRAINING_MILESTONE_MINUTES:
        return {}

    earned_reward = get_training_earned_reward(focus_key, duration_minutes, elapsed_minutes)
    if not earned_reward:
        return {}

    if focus_key == ALL_STATS_KEY:
        earned_total = sum(earned_reward.values())
        payout_total = ceil(earned_total / 2)
        return {
            stat_name: 1
            for stat_name in ALL_STATS_PROGRESS_ORDER[:payout_total]
        }

    stat_name, earned_amount = next(iter(earned_reward.items()))
    return {stat_name: ceil(earned_amount / 2)}
