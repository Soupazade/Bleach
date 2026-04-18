from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.data.locations import RUKONGAI_MARKET, RUKONGAI_STREETS


WorkAlignment = Literal["legit", "neutral", "shady"]


@dataclass(frozen=True, slots=True)
class WorkDefinition:
    key: str
    location_key: str
    label: str
    duration_minutes: int
    stamina_cost: int
    kan_min: int
    kan_max: int
    reputation_change: int
    alignment: WorkAlignment
    menu_description: str
    intro_text: str
    completion_title: str
    completion_description: str


RUKONGAI_STREETS_WORK_OPTIONS = (
    WorkDefinition(
        key="streets_beg_cookfires",
        location_key=RUKONGAI_STREETS.key,
        label="Beg at cookfires",
        duration_minutes=2,
        stamina_cost=4,
        kan_min=3,
        kan_max=7,
        reputation_change=0,
        alignment="neutral",
        menu_description="Low pay. Low risk. Pride goes missing before the kan does.",
        intro_text="You drift from cookfire to cookfire with your hands open and your eyes low, trying to look hungry without looking dangerous.",
        completion_title="You Come Away With A Little",
        completion_description="It is not much, but a few souls spare what they can and you make it through the hour with something in your hand.",
    ),
    WorkDefinition(
        key="streets_haul_salvage",
        location_key=RUKONGAI_STREETS.key,
        label="Haul salvage",
        duration_minutes=3,
        stamina_cost=6,
        kan_min=7,
        kan_max=11,
        reputation_change=1,
        alignment="legit",
        menu_description="Safer work. Better for decent names. The pay stays small.",
        intro_text="You throw your back into broken timber, scrap cloth, and bent metal for souls too tired to move it themselves.",
        completion_title="You Earn The Slow Way",
        completion_description="It is hard, miserable work, but it is honest by Rukongai standards and that still counts for something.",
    ),
    WorkDefinition(
        key="streets_run_errands",
        location_key=RUKONGAI_STREETS.key,
        label="Run street errands",
        duration_minutes=3,
        stamina_cost=5,
        kan_min=6,
        kan_max=10,
        reputation_change=1,
        alignment="legit",
        menu_description="Safe enough. Better for faces people trust not to vanish.",
        intro_text="You carry messages, bundles, and whispered promises across the block for souls who would rather not be seen moving them.",
        completion_title="You Keep Your Word",
        completion_description="The jobs stay small and the pay stays light, but enough people trust your feet to keep you moving.",
    ),
    WorkDefinition(
        key="streets_dirty_delivery",
        location_key=RUKONGAI_STREETS.key,
        label="Run a dirty delivery",
        duration_minutes=5,
        stamina_cost=8,
        kan_min=12,
        kan_max=18,
        reputation_change=-2,
        alignment="shady",
        menu_description="Riskier and dirtier. Bad names get the better cuts.",
        intro_text="You take a wrapped bundle, ask no questions, and walk the kind of route decent souls pretend not to notice.",
        completion_title="The Bundle Changes Hands",
        completion_description="The delivery lands where it was meant to land, no one says the worst part out loud, and the pay is better for exactly that reason.",
    ),
)


RUKONGAI_MARKET_WORK_OPTIONS = (
    WorkDefinition(
        key="market_sweep_stalls",
        location_key=RUKONGAI_MARKET.key,
        label="Sweep the stalls",
        duration_minutes=2,
        stamina_cost=4,
        kan_min=4,
        kan_max=8,
        reputation_change=1,
        alignment="legit",
        menu_description="Safer market work. Small pay for names people do not mind nearby.",
        intro_text="You sweep around half-collapsed stalls, stack scraps, and keep the walkways clear enough for trade to keep limping forward.",
        completion_title="The Stalls Stay Open",
        completion_description="The work is plain and the pay is thin, but market hands remember who helps without stealing on the way past.",
    ),
    WorkDefinition(
        key="market_carry_crates",
        location_key=RUKONGAI_MARKET.key,
        label="Carry crates",
        duration_minutes=3,
        stamina_cost=6,
        kan_min=7,
        kan_max=12,
        reputation_change=1,
        alignment="legit",
        menu_description="Steady lifting. Better if the market does not hate your face.",
        intro_text="You throw your shoulder under cracked crates and warped baskets while stall owners shout directions like you work for them already.",
        completion_title="Your Back Buys Supper",
        completion_description="The crates get where they are going and your shoulders pay the price, but the market coughs up a few coins for the trouble.",
    ),
    WorkDefinition(
        key="market_watch_goods",
        location_key=RUKONGAI_MARKET.key,
        label="Watch a table",
        duration_minutes=3,
        stamina_cost=5,
        kan_min=6,
        kan_max=10,
        reputation_change=0,
        alignment="neutral",
        menu_description="Low-risk standing work. Better than begging, not by much.",
        intro_text="A stall runner needs an extra pair of eyes more than a trusted partner, and that is close enough to work for tonight.",
        completion_title="Nothing Walks Off",
        completion_description="You keep hands where they belong, glare down one would-be thief, and come away with pay too small to brag about.",
    ),
    WorkDefinition(
        key="market_move_hot_goods",
        location_key=RUKONGAI_MARKET.key,
        label="Move hot goods",
        duration_minutes=5,
        stamina_cost=8,
        kan_min=13,
        kan_max=19,
        reputation_change=-2,
        alignment="shady",
        menu_description="Better pay. Dirtier work. Bad reputations open better doors here.",
        intro_text="You keep your mouth shut, your pace even, and your hands on a parcel everyone involved is pretending was always theirs.",
        completion_title="The Market Looks Away",
        completion_description="The parcel moves, the right palms get greased, and the pay comes quicker because no honest soul would touch the job.",
    ),
)


WORK_OPTIONS_BY_LOCATION = {
    RUKONGAI_STREETS.key: RUKONGAI_STREETS_WORK_OPTIONS,
    RUKONGAI_MARKET.key: RUKONGAI_MARKET_WORK_OPTIONS,
}


WORK_DEFINITIONS = {
    option.key: option
    for options in WORK_OPTIONS_BY_LOCATION.values()
    for option in options
}


def get_work_definition(work_key: str) -> WorkDefinition:
    try:
        return WORK_DEFINITIONS[work_key]
    except KeyError as error:
        raise ValueError(f"Unknown work definition: {work_key}") from error


def get_work_options_for_location(location_key: str) -> tuple[WorkDefinition, ...]:
    return WORK_OPTIONS_BY_LOCATION.get(location_key, ())


def is_work_location_supported(location_key: str) -> bool:
    return location_key in WORK_OPTIONS_BY_LOCATION
