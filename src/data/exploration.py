from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Literal


ExploreEventType = Literal["reward", "combat", "choice", "flavor"]
ExploreFlowType = Literal["instant", "single_choice", "multi_step"]
ExploreXpProfile = Literal[
    "none",
    "approach_low",
    "approach_base",
    "approach_high",
    "combat_win",
    "combat_lose",
    "special_base",
    "special_high",
    "special_combat_win",
    "special_combat_lose",
]
ButtonStyleName = Literal["primary", "secondary", "success", "danger"]


@dataclass(frozen=True, slots=True)
class ExploreApproachDefinition:
    key: str
    label: str
    duration_minutes: int
    stamina_cost: int
    xp_min: int
    xp_max: int
    risk_tier: str
    reward_tier: str
    event_biases: dict[ExploreEventType, int]
    menu_description: str
    intro_text: str

    @property
    def id(self) -> str:
        return self.key

    @property
    def name(self) -> str:
        return self.label

    @property
    def duration_label(self) -> str:
        return f"{self.duration_minutes}m"

    @property
    def dropdown_label(self) -> str:
        return f"{self.label} [{self.duration_label}]"


@dataclass(frozen=True, slots=True)
class ExplorationEventTemplate:
    title: str
    description: str


@dataclass(frozen=True, slots=True)
class ExplorationOutcomeDefinition:
    title: str
    description: str
    event_type: ExploreEventType
    xp_profile: ExploreXpProfile
    reputation_change: int = 0
    combat_outcome: str | None = None


@dataclass(frozen=True, slots=True)
class ExplorationDecisionOptionDefinition:
    key: str
    label: str
    style: ButtonStyleName
    next_step_id: str | None = None
    outcome: ExplorationOutcomeDefinition | None = None


@dataclass(frozen=True, slots=True)
class ExplorationDecisionStepDefinition:
    key: str
    title: str
    description: str
    options: tuple[ExplorationDecisionOptionDefinition, ...]


@dataclass(frozen=True, slots=True)
class ExplorationDecisionEventDefinition:
    key: str
    title: str
    flow_type: Literal["single_choice", "multi_step"]
    initial_step_id: str
    steps: tuple[ExplorationDecisionStepDefinition, ...]

    @property
    def step_count(self) -> int:
        return 2 if self.flow_type == "multi_step" else 1


@dataclass(frozen=True, slots=True)
class LocationEventPool:
    reward_events: tuple[ExplorationEventTemplate, ...]
    combat_events: tuple[ExplorationEventTemplate, ...]
    choice_events: tuple[ExplorationEventTemplate, ...]
    flavor_events: tuple[ExplorationEventTemplate, ...]


@dataclass(frozen=True, slots=True)
class LocationExploreDefinition:
    location_key: str
    menu_title: str
    menu_description: str
    menu_footer: str
    approach_pool: tuple[ExploreApproachDefinition, ...]
    event_pool: LocationEventPool
    single_choice_events: tuple[ExplorationDecisionEventDefinition, ...]
    multi_step_events: tuple[ExplorationDecisionEventDefinition, ...]
    special_offer_templates: tuple[ExplorationEventTemplate, ...]
    special_events: tuple[ExplorationDecisionEventDefinition, ...]


def _biases(
    *,
    reward: int,
    combat: int,
    choice: int,
    flavor: int,
) -> dict[ExploreEventType, int]:
    return {
        "reward": reward,
        "combat": combat,
        "choice": choice,
        "flavor": flavor,
    }


def _outcome(
    *,
    title: str,
    description: str,
    event_type: ExploreEventType,
    xp_profile: ExploreXpProfile,
    reputation_change: int = 0,
    combat_outcome: str | None = None,
) -> ExplorationOutcomeDefinition:
    return ExplorationOutcomeDefinition(
        title=title,
        description=description,
        event_type=event_type,
        xp_profile=xp_profile,
        reputation_change=reputation_change,
        combat_outcome=combat_outcome,
    )


def _option(
    *,
    key: str,
    label: str,
    style: ButtonStyleName,
    next_step_id: str | None = None,
    outcome: ExplorationOutcomeDefinition | None = None,
) -> ExplorationDecisionOptionDefinition:
    return ExplorationDecisionOptionDefinition(
        key=key,
        label=label,
        style=style,
        next_step_id=next_step_id,
        outcome=outcome,
    )


RUKONGAI_STREETS_APPROACHES = (
    ExploreApproachDefinition(
        key="rukongai_search_scraps",
        label="Search for scraps",
        duration_minutes=2,
        stamina_cost=10,
        xp_min=6,
        xp_max=10,
        risk_tier="low",
        reward_tier="low",
        event_biases=_biases(reward=46, combat=16, choice=18, flavor=20),
        menu_description="Low risk. Quick scavenging through the leftovers.",
        intro_text="You drift through busted stalls and broken crates, hoping the streets left something behind.",
    ),
    ExploreApproachDefinition(
        key="rukongai_follow_crowd",
        label="Follow the crowd",
        duration_minutes=2,
        stamina_cost=10,
        xp_min=6,
        xp_max=10,
        risk_tier="low",
        reward_tier="low",
        event_biases=_biases(reward=30, combat=12, choice=38, flavor=20),
        menu_description="Low risk. Blend in and chase movement in the district.",
        intro_text="You let the flow of hungry souls carry you, listening for where fear and opportunity gather.",
    ),
    ExploreApproachDefinition(
        key="rukongai_keep_head_down",
        label="Keep your head down",
        duration_minutes=2,
        stamina_cost=10,
        xp_min=6,
        xp_max=10,
        risk_tier="low",
        reward_tier="low",
        event_biases=_biases(reward=22, combat=10, choice=18, flavor=50),
        menu_description="Lowest risk. Stay unseen and survive the block.",
        intro_text="You avoid hard stares and lowered blades, moving like another tired soul trying to make it through the hour.",
    ),
    ExploreApproachDefinition(
        key="rukongai_listen_rumors",
        label="Listen for rumors",
        duration_minutes=2,
        stamina_cost=10,
        xp_min=6,
        xp_max=10,
        risk_tier="low",
        reward_tier="medium",
        event_biases=_biases(reward=28, combat=10, choice=42, flavor=20),
        menu_description="Low risk. Chase whispers, debts, and dirty secrets.",
        intro_text="You haunt cookfires and alley corners, picking truth out of desperate whispers and cheap lies.",
    ),
    ExploreApproachDefinition(
        key="rukongai_walk_back_alleys",
        label="Walk the back alleys",
        duration_minutes=3,
        stamina_cost=10,
        xp_min=10,
        xp_max=15,
        risk_tier="medium",
        reward_tier="medium",
        event_biases=_biases(reward=30, combat=28, choice=18, flavor=24),
        menu_description="Medium risk. The alleys hide danger and useful scraps.",
        intro_text="You slip away from the main flow and into the narrow veins of the district, where trouble rarely announces itself.",
    ),
    ExploreApproachDefinition(
        key="rukongai_offer_help",
        label="Offer a helping hand",
        duration_minutes=3,
        stamina_cost=10,
        xp_min=10,
        xp_max=15,
        risk_tier="medium",
        reward_tier="medium",
        event_biases=_biases(reward=36, combat=12, choice=34, flavor=18),
        menu_description="Medium risk. Small kindness can open unexpected doors.",
        intro_text="You spend your time helping where you can, knowing Rukongai remembers even the smallest mercy.",
    ),
    ExploreApproachDefinition(
        key="rukongai_check_market_edges",
        label="Check the market edges",
        duration_minutes=3,
        stamina_cost=10,
        xp_min=10,
        xp_max=15,
        risk_tier="medium",
        reward_tier="medium",
        event_biases=_biases(reward=40, combat=18, choice=22, flavor=20),
        menu_description="Medium risk. Scavenge the fringe where trade breaks down.",
        intro_text="You circle the edges of the market where spoiled goods, thrown scrap, and bad tempers pile together.",
    ),
    ExploreApproachDefinition(
        key="rukongai_trail_figure",
        label="Trail a suspicious figure",
        duration_minutes=3,
        stamina_cost=10,
        xp_min=10,
        xp_max=15,
        risk_tier="medium",
        reward_tier="high",
        event_biases=_biases(reward=18, combat=32, choice=34, flavor=16),
        menu_description="Medium risk. Follow trouble and hope it leads somewhere useful.",
        intro_text="You shadow a nervous soul through the district, careful not to lose them in the crowd or the smoke.",
    ),
    ExploreApproachDefinition(
        key="rukongai_push_rough_blocks",
        label="Push into the rough blocks",
        duration_minutes=5,
        stamina_cost=10,
        xp_min=15,
        xp_max=25,
        risk_tier="high",
        reward_tier="high",
        event_biases=_biases(reward=24, combat=48, choice=16, flavor=12),
        menu_description="High risk. Press deeper where gangs and fear hold ground.",
        intro_text="You leave the safer lanes behind and step into blocks where every doorway watches and every mistake costs.",
    ),
    ExploreApproachDefinition(
        key="rukongai_chase_disturbance",
        label="Chase a spiritual disturbance",
        duration_minutes=5,
        stamina_cost=10,
        xp_min=15,
        xp_max=25,
        risk_tier="high",
        reward_tier="high",
        event_biases=_biases(reward=20, combat=52, choice=16, flavor=12),
        menu_description="High risk. Hunt the pressure spike before it finds someone else.",
        intro_text="You lock onto a shiver in the spiritual air and follow it through shattered streets before it can fade.",
    ),
    ExploreApproachDefinition(
        key="rukongai_defend_corner",
        label="Defend your corner",
        duration_minutes=5,
        stamina_cost=10,
        xp_min=15,
        xp_max=25,
        risk_tier="high",
        reward_tier="medium",
        event_biases=_biases(reward=24, combat=44, choice=20, flavor=12),
        menu_description="High risk. Hold ground when the district turns ugly.",
        intro_text="You stay where the pressure is rising and make it clear that your corner will not fold without a fight.",
    ),
    ExploreApproachDefinition(
        key="rukongai_hunt_better_life",
        label="Hunt for a better life",
        duration_minutes=5,
        stamina_cost=10,
        xp_min=15,
        xp_max=25,
        risk_tier="high",
        reward_tier="high",
        event_biases=_biases(reward=34, combat=24, choice=30, flavor=12),
        menu_description="High risk. Chase a rare break beyond mere survival.",
        intro_text="You push beyond daily survival, looking for a thread that might actually pull you toward something better.",
    ),
)

RUKONGAI_STREETS_EVENTS = LocationEventPool(
    reward_events=(
        ExplorationEventTemplate(
            title="Scrap Luck",
            description=(
                "Halfway through **{approach}**, your foot kicks something under a sheet of warped wood. "
                "It is only a little salvage, but tonight that little feels like the district looked away for one second and let you keep it."
            ),
        ),
        ExplorationEventTemplate(
            title="A Kind Hand in a Hard Place",
            description=(
                "Near the end of **{approach}**, someone you helped earlier presses a wrapped ration into your hand without meeting your eyes. "
                "No speech. No thanks. Just proof that kindness is not dead here yet, only ashamed to be seen."
            ),
        ),
        ExplorationEventTemplate(
            title="Market Edge Score",
            description=(
                "The market fringe breaks into shouting, then silence. By the time your **{approach}** carries you through the aftermath, the best scraps are gone but not all of them. "
                "You come away with enough to call it a good night by Rukongai standards."
            ),
        ),
        ExplorationEventTemplate(
            title="Rumor Turned Reward",
            description=(
                "A whisper picked up during **{approach}** leads you behind split stone and mold-stiff cloth. "
                "Most rumors out here rot on the tongue. This one leaves something real in your hands."
            ),
        ),
    ),
    combat_events=(
        ExplorationEventTemplate(
            title="Alley Ambush",
            description=(
                "A narrow alley opens under **{approach}**, and the silence inside it is wrong. "
                "By the time you feel the eyes on you, the first step toward violence is already taken."
            ),
        ),
        ExplorationEventTemplate(
            title="Weak Hollow Stirring",
            description=(
                "A thin shriek tears across **{approach}** and something hungry lunges out from the wreckage between homes. "
                "Weak or not, a hollow in a poor block is still bad news for everyone nearby."
            ),
        ),
        ExplorationEventTemplate(
            title="Gang Pressure",
            description=(
                "Your **{approach}** takes you through a stretch claimed by local toughs who have not eaten enough and want you to know it. "
                "One hard look becomes two, and then the whole block shifts."
            ),
        ),
        ExplorationEventTemplate(
            title="Corner Turned Violent",
            description=(
                "It starts with a stare, then a shove, then somebody deciding your worn-out little pile of survival ought to be theirs. "
                "**{approach}** turns ugly in a blink."
            ),
        ),
    ),
    choice_events=(
        ExplorationEventTemplate(
            title="A Whisper Worth Chasing",
            description=(
                "A rumor catches on the edge of **{approach}** and refuses to leave your head. "
                "Safe route. Hidden stash. Debt collectors on the move. Three possibilities, and all of them smell like trouble."
            ),
        ),
        ExplorationEventTemplate(
            title="Need Versus Opportunity",
            description=(
                "A stranger with hollow cheeks needs help now. Ten steps away, a risky opening cracks wide in the district. "
                "**{approach}** gives you just enough time to hate whichever choice you make."
            ),
        ),
        ExplorationEventTemplate(
            title="The Street Tests Your Instincts",
            description=(
                "The crowd breaks wrong during **{approach}**. Fear runs one way, hunger runs the other, and for one heartbeat you can see the shape of what comes next."
            ),
        ),
        ExplorationEventTemplate(
            title="A Lead in the Dust",
            description=(
                "Dust, boot marks, a dropped cloth charm, and noise from farther down the lane. "
                "**{approach}** leaves you staring at one of those small moments that only stay small if you walk away."
            ),
        ),
    ),
    flavor_events=(
        ExplorationEventTemplate(
            title="Another Night in Rukongai",
            description=(
                "**{approach}** gives you no score worth bragging about. Just smoke in your clothes, thin lantern light, and the soft scrape of neighbors making one more night out of almost nothing."
            ),
        ),
        ExplorationEventTemplate(
            title="Hunger in the Air",
            description=(
                "You end **{approach}** near a cookfire full of water pretending to be soup. "
                "Nobody laughs. Nobody complains. They just keep waiting for it to be enough."
            ),
        ),
        ExplorationEventTemplate(
            title="Small Mercy, Small Hope",
            description=(
                "At the end of **{approach}**, you catch two neighbors splitting a meal that would not fill one stomach. "
                "They do it anyway. Somehow that stays with you longer than a bigger prize might have."
            ),
        ),
        ExplorationEventTemplate(
            title="The District Watches Back",
            description=(
                "The alleys give you no reward, only the feeling of being weighed. "
                "By the time **{approach}** ends, you know the block a little better, and it knows you too."
            ),
        ),
    ),
)

RUKONGAI_STREETS_SINGLE_CHOICE_EVENTS = (
    ExplorationDecisionEventDefinition(
        key="rukongai_hidden_ration",
        title="Hidden Ration",
        flow_type="single_choice",
        initial_step_id="step_one",
        steps=(
            ExplorationDecisionStepDefinition(
                key="step_one",
                title="A sack beneath the boards",
                description=(
                    "A ration sack shows under warped planks just as your hand reaches for it. "
                    "Two other hungry souls see it in the same breath. Nobody speaks. Nobody needs to."
                ),
                options=(
                    _option(
                        key="split_it",
                        label="Split it",
                        style="success",
                        outcome=_outcome(
                            title="Small Victory Shared",
                            description=(
                                "You split the find instead of clutching it all for yourself. Nobody eats well, but in a district like this, people remember a soul who still knows how to share."
                            ),
                            event_type="reward",
                            xp_profile="approach_high",
                            reputation_change=2,
                        ),
                    ),
                    _option(
                        key="take_it",
                        label="Take it and move",
                        style="danger",
                        outcome=_outcome(
                            title="Hard Choice, Hard Street",
                            description=(
                                "You grab the ration and disappear before hunger turns into knives. You stay fed a little longer, but the look left behind follows you."
                            ),
                            event_type="choice",
                            xp_profile="approach_base",
                            reputation_change=-2,
                        ),
                    ),
                    _option(
                        key="leave_it",
                        label="Leave it",
                        style="secondary",
                        outcome=_outcome(
                            title="Empty Hands",
                            description=(
                                "You step back and let the others have it. The street stays quiet, and you carry on with one more lesson about what Rukongai does to people."
                            ),
                            event_type="flavor",
                            xp_profile="approach_low",
                        ),
                    ),
                ),
            ),
        ),
    ),
    ExplorationDecisionEventDefinition(
        key="rukongai_washline_rumor",
        title="Rumor at the Washline",
        flow_type="single_choice",
        initial_step_id="step_one",
        steps=(
            ExplorationDecisionStepDefinition(
                key="step_one",
                title="A whisper worth acting on",
                description=(
                    "A washline whisper turns sharp halfway through **{approach}**. "
                    "A weak hollow is drifting near a nearby block, and a gang means to make coin off the fear before dawn."
                ),
                options=(
                    _option(
                        key="chase_whisper",
                        label="Chase the whisper",
                        style="primary",
                        outcome=_outcome(
                            title="You Follow the Lead",
                            description=(
                                "You move on the rumor before it cools and catch the trail while it still matters. In Rukongai, acting fast is often the only edge you get."
                            ),
                            event_type="choice",
                            xp_profile="approach_high",
                        ),
                    ),
                    _option(
                        key="warn_locals",
                        label="Warn the block",
                        style="success",
                        outcome=_outcome(
                            title="The Warning Holds",
                            description=(
                                "You pass the warning from doorway to doorway until the whole stretch is awake. Panic still stirs, but it never gets to own the block."
                            ),
                            event_type="reward",
                            xp_profile="approach_base",
                            reputation_change=2,
                        ),
                    ),
                    _option(
                        key="ignore_it",
                        label="Let it pass",
                        style="secondary",
                        outcome=_outcome(
                            title="Noise in the District",
                            description=(
                                "You let the rumor drift on without you. Around here, every alley wants something, and nobody has enough strength for all of it."
                            ),
                            event_type="flavor",
                            xp_profile="approach_low",
                        ),
                    ),
                ),
            ),
        ),
    ),
    ExplorationDecisionEventDefinition(
        key="rukongai_corner_hollow",
        title="Weak Hollow by the Wall",
        flow_type="single_choice",
        initial_step_id="step_one",
        steps=(
            ExplorationDecisionStepDefinition(
                key="step_one",
                title="A shriek in the plaster",
                description=(
                    "Near the end of **{approach}**, a cracked wall shudders with a thin, ugly shriek. "
                    "A weak hollow is probing the edge of the block, and everybody hiding nearby knows what happens if nobody answers it."
                ),
                options=(
                    _option(
                        key="drive_it_off",
                        label="Drive it off",
                        style="danger",
                        outcome=_outcome(
                            title="The Hollow Breaks First",
                            description=(
                                "You hit the weak hollow before fear can spread. It is quick, filthy work, but the lane breathes easier when it's over."
                            ),
                            event_type="combat",
                            xp_profile="combat_win",
                            reputation_change=2,
                            combat_outcome="Victory",
                        ),
                    ),
                    _option(
                        key="draw_it_away",
                        label="Draw it away",
                        style="primary",
                        outcome=_outcome(
                            title="Danger Redirected",
                            description=(
                                "You pull the creature away from the homes and buy the block a few precious minutes of quiet. In these streets, that counts."
                            ),
                            event_type="choice",
                            xp_profile="approach_base",
                            reputation_change=2,
                        ),
                    ),
                    _option(
                        key="raise_alarm",
                        label="Raise the alarm",
                        style="success",
                        outcome=_outcome(
                            title="The Block Stands Ready",
                            description=(
                                "You shout the warning before the danger lands. Doors slam, lamps go dark, and the block rides out the worst of it standing."
                            ),
                            event_type="reward",
                            xp_profile="approach_base",
                            reputation_change=2,
                        ),
                    ),
                ),
            ),
        ),
    ),
)

RUKONGAI_STREETS_MULTI_STEP_EVENTS = (
    ExplorationDecisionEventDefinition(
        key="rukongai_market_debt",
        title="Debt in the Market Fringe",
        flow_type="multi_step",
        initial_step_id="step_one",
        steps=(
            ExplorationDecisionStepDefinition(
                key="step_one",
                title="The collector arrives",
                description=(
                    "Your **{approach}** reaches the market edge at the worst moment. "
                    "A gang collector has a vendor trapped by the stall, and the whole stretch is pretending not to look while listening to every word."
                ),
                options=(
                    _option(key="shadow", label="Shadow the collector", style="primary", next_step_id="shadow_step"),
                    _option(key="back_vendor", label="Back the vendor", style="success", next_step_id="vendor_step"),
                    _option(
                        key="leave",
                        label="Leave it",
                        style="secondary",
                        outcome=_outcome(
                            title="You Keep Moving",
                            description=(
                                "You keep your head down and move on. In Rukongai, not every fight is yours, even when leaving it behind tastes bitter."
                            ),
                            event_type="flavor",
                            xp_profile="approach_low",
                        ),
                    ),
                ),
            ),
            ExplorationDecisionStepDefinition(
                key="shadow_step",
                title="You have their trail",
                description=(
                    "You fall in behind the collector through broken alleys and stacks of split crates. "
                    "One careless sound ends the tail. One clean read might show you where the stolen scraps keep disappearing."
                ),
                options=(
                    _option(
                        key="keep_tailing",
                        label="Keep tailing",
                        style="primary",
                        outcome=_outcome(
                            title="You Find the Hideout",
                            description=(
                                "You stay patient and catch the stash point without tipping your hand. That kind of patience can feed more than one empty night."
                            ),
                            event_type="reward",
                            xp_profile="approach_high",
                            reputation_change=2,
                        ),
                    ),
                    _option(
                        key="spring_trap",
                        label="Spring the trap",
                        style="danger",
                        outcome=_outcome(
                            title="Collector Put Down",
                            description=(
                                "You strike before the collector can bark for help. The alley turns mean in a heartbeat, but you're the one left standing."
                            ),
                            event_type="combat",
                            xp_profile="combat_win",
                            reputation_change=2,
                            combat_outcome="Victory",
                        ),
                    ),
                ),
            ),
            ExplorationDecisionStepDefinition(
                key="vendor_step",
                title="Now the street is looking at you",
                description=(
                    "The second you step in, the air changes. "
                    "The crowd is still scared, but now it is watching you to decide whether this becomes courage or blood."
                ),
                options=(
                    _option(
                        key="rally_crowd",
                        label="Rally the crowd",
                        style="success",
                        outcome=_outcome(
                            title="The Crowd Holds the Line",
                            description=(
                                "You turn fear into backbone. Once the collector sees the whole stretch stop bowing, he decides this debt is not worth bleeding for."
                            ),
                            event_type="reward",
                            xp_profile="approach_high",
                            reputation_change=5,
                        ),
                    ),
                    _option(
                        key="take_hit",
                        label="Take the hit",
                        style="danger",
                        outcome=_outcome(
                            title="You Hold the Corner",
                            description=(
                                "You take the first hit so the vendor does not have to. It hurts like hell, but nobody on that corner forgets who held the line."
                            ),
                            event_type="combat",
                            xp_profile="combat_lose",
                            reputation_change=2,
                            combat_outcome="Setback",
                        ),
                    ),
                ),
            ),
        ),
    ),
    ExplorationDecisionEventDefinition(
        key="rukongai_alley_cry",
        title="A Cry from the Alley",
        flow_type="multi_step",
        initial_step_id="step_one",
        steps=(
            ExplorationDecisionStepDefinition(
                key="step_one",
                title="Someone is calling for help",
                description=(
                    "A cry for help cuts through the alley maze at the tail end of **{approach}**. "
                    "It sounds thin, frightened, and maybe a little too well placed. In Rukongai, that usually means trouble either way."
                ),
                options=(
                    _option(key="investigate", label="Investigate", style="primary", next_step_id="investigate_step"),
                    _option(key="watch", label="Watch from cover", style="secondary", next_step_id="watch_step"),
                    _option(
                        key="move_on",
                        label="Move on",
                        style="secondary",
                        outcome=_outcome(
                            title="You Leave the Cry Behind",
                            description=(
                                "You let the alley keep its secrets and move on. Surviving this place sometimes means accepting that you cannot answer every cry."
                            ),
                            event_type="flavor",
                            xp_profile="approach_low",
                        ),
                    ),
                ),
            ),
            ExplorationDecisionStepDefinition(
                key="investigate_step",
                title="It was a trap, but not only a trap",
                description=(
                    "You step in and find a wounded soul slumped against the wall just as shadows start to close. "
                    "The trap is real. So is the person caught in it."
                ),
                options=(
                    _option(
                        key="help_wounded",
                        label="Help the wounded",
                        style="success",
                        outcome=_outcome(
                            title="Mercy Before Escape",
                            description=(
                                "You get the wounded soul moving before the alley seals shut. It is clumsy, desperate work, but you drag both of you through it."
                            ),
                            event_type="reward",
                            xp_profile="approach_base",
                            reputation_change=2,
                        ),
                    ),
                    _option(
                        key="set_trap",
                        label="Turn it back on them",
                        style="danger",
                        outcome=_outcome(
                            title="Ambushers Broken",
                            description=(
                                "You use the alley against the ambushers and break their rush before it becomes a beating in the dark."
                            ),
                            event_type="combat",
                            xp_profile="combat_win",
                            reputation_change=2,
                            combat_outcome="Victory",
                        ),
                    ),
                ),
            ),
            ExplorationDecisionStepDefinition(
                key="watch_step",
                title="The pattern becomes clear",
                description=(
                    "From cover, the whole setup finally shows itself: the bait, the watchers, the lane they want their victim to stumble into. "
                    "Now that you see the shape of it, you either break it or carry the knowledge away."
                ),
                options=(
                    _option(
                        key="intervene",
                        label="Step in",
                        style="danger",
                        outcome=_outcome(
                            title="You Break the Setup",
                            description=(
                                "You move at the exact right moment and smash the setup before it snaps shut. The alley erupts, but the people marked for it get out."
                            ),
                            event_type="combat",
                            xp_profile="combat_win",
                            reputation_change=2,
                            combat_outcome="Victory",
                        ),
                    ),
                    _option(
                        key="slip_away",
                        label="Slip away with intel",
                        style="primary",
                        outcome=_outcome(
                            title="Knowledge Carried Forward",
                            description=(
                                "You leave unseen with a better read on the alley crews and their patterns. Sometimes the best win is knowing where not to be next time."
                            ),
                            event_type="choice",
                            xp_profile="approach_high",
                        ),
                    ),
                ),
            ),
        ),
    ),
)

RUKONGAI_STREETS_SPECIAL_OFFERS = (
    ExplorationEventTemplate(
        title="A Hidden Pull in the District",
        description=(
            "Just when the run feels finished, **{approach}** catches on something odd. "
            "A buried spiritual pull. A hidden pocket. The kind of chance that usually costs more than it gives."
        ),
    ),
    ExplorationEventTemplate(
        title="A Rare Opening",
        description=(
            "The streets shift around **{approach}** and, for one narrow second, something opens that should have stayed hidden. "
            "It smells like hunger, luck, and bad judgment all at once."
        ),
    ),
    ExplorationEventTemplate(
        title="Something Valuable Stirs",
        description=(
            "Your **{approach}** turns up a lead with real weight behind it. "
            "Not rumor. Not wishful thinking. Something worth chasing, if you are willing to pay for it up front."
        ),
    ),
)

RUKONGAI_STREETS_SPECIAL_EVENTS = (
    ExplorationDecisionEventDefinition(
        key="rukongai_special_buried_cache",
        title="Buried Cache Below the Stone",
        flow_type="single_choice",
        initial_step_id="step_one",
        steps=(
            ExplorationDecisionStepDefinition(
                key="step_one",
                title="The opening is real, but unstable",
                description=(
                    "You force your way into the hidden pocket and find a cramped cache under cracked stone. "
                    "It is real. So is the noise you're making, and out here noise is just another way of inviting company."
                ),
                options=(
                    _option(
                        key="grab_fast",
                        label="Grab what you can",
                        style="primary",
                        outcome=_outcome(
                            title="Quick Hands, Hard-Won Prize",
                            description=(
                                "You snatch the best of the stash before the alley folds in on itself. It is not pretty, but it beats going hungry."
                            ),
                            event_type="reward",
                            xp_profile="special_base",
                            reputation_change=-2,
                        ),
                    ),
                    _option(
                        key="hold_ground",
                        label="Hold the site",
                        style="danger",
                        outcome=_outcome(
                            title="You Hold the Cache",
                            description=(
                                "You plant your feet and fight for the hidden stash when the rush comes. It is brutal, loud, and exactly the kind of thing the district talks about after."
                            ),
                            event_type="combat",
                            xp_profile="special_combat_win",
                            reputation_change=-2,
                            combat_outcome="Victory",
                        ),
                    ),
                    _option(
                        key="pull_back",
                        label="Pull back with scraps",
                        style="secondary",
                        outcome=_outcome(
                            title="You Settle for Less",
                            description=(
                                "You abandon the deepest part of the stash before the danger peaks. The haul is smaller than it could have been, but you still leave with more than you started with."
                            ),
                            event_type="choice",
                            xp_profile="approach_high",
                        ),
                    ),
                ),
            ),
        ),
    ),
    ExplorationDecisionEventDefinition(
        key="rukongai_special_hollow_nest",
        title="Weak Hollow Nest",
        flow_type="single_choice",
        initial_step_id="step_one",
        steps=(
            ExplorationDecisionStepDefinition(
                key="step_one",
                title="The reiatsu trail leads to a nest",
                description=(
                    "The strange pull resolves behind a line of wrecked walls, where weak hollows have been nesting in the dark. "
                    "There is value here, but the whole place feels one bad move away from erupting."
                ),
                options=(
                    _option(
                        key="purge_nest",
                        label="Purge the nest",
                        style="danger",
                        outcome=_outcome(
                            title="Nest Broken Open",
                            description=(
                                "You hit the nest head-on and tear it apart under a rain of bad reiatsu. The block will sleep easier for it, even if you do not."
                            ),
                            event_type="combat",
                            xp_profile="special_combat_win",
                            reputation_change=2,
                            combat_outcome="Victory",
                        ),
                    ),
                    _option(
                        key="lure_one_out",
                        label="Lure one out",
                        style="primary",
                        outcome=_outcome(
                            title="Controlled Risk, Real Gain",
                            description=(
                                "You bait only part of the nest into the open and take what you can from the opening. It is slower, safer, and still far richer than a routine street run."
                            ),
                            event_type="reward",
                            xp_profile="special_base",
                        ),
                    ),
                    _option(
                        key="retreat_scuffed",
                        label="Retreat when it spikes",
                        style="secondary",
                        outcome=_outcome(
                            title="The Chance Slips Away",
                            description=(
                                "You back off when the pressure grows ugly. The opportunity vanishes, and all you carry away is a partial read on what was hiding there."
                            ),
                            event_type="flavor",
                            xp_profile="special_combat_lose",
                            combat_outcome="Setback",
                        ),
                    ),
                ),
            ),
        ),
    ),
    ExplorationDecisionEventDefinition(
        key="rukongai_special_gang_route",
        title="Gang Courier Route",
        flow_type="single_choice",
        initial_step_id="step_one",
        steps=(
            ExplorationDecisionStepDefinition(
                key="step_one",
                title="You found the handoff lane",
                description=(
                    "The lead opens onto a handoff lane where local gangs move food, scrap, and every other stolen comfort worth guarding. "
                    "One bold move here could feed you for days, or get your name dragged through every block nearby."
                ),
                options=(
                    _option(
                        key="hit_courier",
                        label="Hit the courier",
                        style="danger",
                        outcome=_outcome(
                            title="Courier Broken, Street Watching",
                            description=(
                                "You smash the courier lane before it can slip through your fingers. The score is real, and so is the trouble your name will stir after."
                            ),
                            event_type="combat",
                            xp_profile="special_combat_win",
                            reputation_change=-2,
                            combat_outcome="Victory",
                        ),
                    ),
                    _option(
                        key="shadow_and_steal",
                        label="Shadow and steal",
                        style="primary",
                        outcome=_outcome(
                            title="You Peel Off the Best Cut",
                            description=(
                                "You tail the lane until it opens up, then peel off the best cut at the perfect moment. Clean for Rukongai, dirty everywhere else."
                            ),
                            event_type="reward",
                            xp_profile="special_high",
                            reputation_change=-2,
                        ),
                    ),
                    _option(
                        key="take_small_piece",
                        label="Take a small piece",
                        style="success",
                        outcome=_outcome(
                            title="A Smaller Score, Still Worth It",
                            description=(
                                "You avoid the bloodiest version of the chance and settle for a safer cut. It is less than glory, but still better than an ordinary night."
                            ),
                            event_type="choice",
                            xp_profile="special_base",
                        ),
                    ),
                ),
            ),
        ),
    ),
)

LEGACY_GENERIC_APPROACHES = (
    ExploreApproachDefinition(
        key="cautious_search",
        label="Cautious Search",
        duration_minutes=2,
        stamina_cost=10,
        xp_min=6,
        xp_max=10,
        risk_tier="low",
        reward_tier="low",
        event_biases=_biases(reward=40, combat=30, choice=20, flavor=10),
        menu_description="Legacy exploration option.",
        intro_text="You move carefully, listening for every shift in the spiritual air.",
    ),
    ExploreApproachDefinition(
        key="standard_patrol",
        label="Standard Patrol",
        duration_minutes=3,
        stamina_cost=10,
        xp_min=10,
        xp_max=15,
        risk_tier="medium",
        reward_tier="medium",
        event_biases=_biases(reward=40, combat=30, choice=20, flavor=10),
        menu_description="Legacy exploration option.",
        intro_text="You patrol with steady purpose, ready for whatever Rukongai throws at you.",
    ),
    ExploreApproachDefinition(
        key="risky_push",
        label="Risky Push",
        duration_minutes=4,
        stamina_cost=10,
        xp_min=15,
        xp_max=25,
        risk_tier="high",
        reward_tier="high",
        event_biases=_biases(reward=40, combat=30, choice=20, flavor=10),
        menu_description="Legacy exploration option.",
        intro_text="You push deeper into danger, chasing growth through pressure and risk.",
    ),
)

LOCATION_EXPLORATION_DEFINITIONS = {
    "rukongai_streets": LocationExploreDefinition(
        location_key="rukongai_streets",
        menu_title="Rukongai Streets",
        menu_description=(
            "The streets never hand you anything. Keep your head up, pick your move, and try to carve one good break out of the night."
        ),
        menu_footer='"If miracles only happen once, what are they called the second time?"',
        approach_pool=RUKONGAI_STREETS_APPROACHES,
        event_pool=RUKONGAI_STREETS_EVENTS,
        single_choice_events=RUKONGAI_STREETS_SINGLE_CHOICE_EVENTS,
        multi_step_events=RUKONGAI_STREETS_MULTI_STEP_EVENTS,
        special_offer_templates=RUKONGAI_STREETS_SPECIAL_OFFERS,
        special_events=RUKONGAI_STREETS_SPECIAL_EVENTS,
    ),
}

EXPLORE_APPROACHES = {
    approach.key: approach
    for approach in (
        *LEGACY_GENERIC_APPROACHES,
        *(
            approach
            for location_definition in LOCATION_EXPLORATION_DEFINITIONS.values()
            for approach in location_definition.approach_pool
        ),
    )
}


def get_explore_approach(approach_key: str) -> ExploreApproachDefinition:
    try:
        return EXPLORE_APPROACHES[approach_key]
    except KeyError as error:
        raise ValueError(f"Unknown explore approach: {approach_key}") from error


def get_location_exploration_definition(location_key: str) -> LocationExploreDefinition:
    try:
        return LOCATION_EXPLORATION_DEFINITIONS[location_key]
    except KeyError as error:
        raise ValueError(f"Unknown exploration location: {location_key}") from error


def get_location_event_pool(location_key: str) -> LocationEventPool:
    return get_location_exploration_definition(location_key).event_pool


def get_location_approach_pool(location_key: str) -> tuple[ExploreApproachDefinition, ...]:
    return get_location_exploration_definition(location_key).approach_pool


def get_random_explore_options_for_location(
    location_key: str,
    *,
    count: int = 3,
) -> tuple[ExploreApproachDefinition, ...]:
    approach_pool = get_location_approach_pool(location_key)
    if count == 3:
        duration_buckets: dict[int, list[ExploreApproachDefinition]] = {}
        for approach in approach_pool:
            duration_buckets.setdefault(approach.duration_minutes, []).append(approach)

        required_durations = (2, 3, 5)
        if all(duration_buckets.get(duration) for duration in required_durations):
            selected = [
                random.choice(duration_buckets[duration])
                for duration in required_durations
            ]
            return tuple(selected)

    sample_size = min(count, len(approach_pool))
    return tuple(random.sample(approach_pool, k=sample_size))


def get_random_decision_event(
    location_key: str,
    flow_type: Literal["single_choice", "multi_step"],
) -> ExplorationDecisionEventDefinition:
    location_definition = get_location_exploration_definition(location_key)
    pool = (
        location_definition.single_choice_events
        if flow_type == "single_choice"
        else location_definition.multi_step_events
    )
    return random.choice(pool)


def get_random_special_offer_template(location_key: str) -> ExplorationEventTemplate:
    location_definition = get_location_exploration_definition(location_key)
    return random.choice(location_definition.special_offer_templates)


def get_random_special_event(location_key: str) -> ExplorationDecisionEventDefinition:
    location_definition = get_location_exploration_definition(location_key)
    return random.choice(location_definition.special_events)


def get_decision_event_definition(
    location_key: str,
    event_key: str,
) -> ExplorationDecisionEventDefinition:
    location_definition = get_location_exploration_definition(location_key)
    for event in (
        *location_definition.single_choice_events,
        *location_definition.multi_step_events,
        *location_definition.special_events,
    ):
        if event.key == event_key:
            return event

    raise ValueError(f"Unknown exploration decision event: {location_key}:{event_key}")


def get_decision_step_definition(
    event: ExplorationDecisionEventDefinition,
    step_key: str,
) -> ExplorationDecisionStepDefinition:
    for step in event.steps:
        if step.key == step_key:
            return step

    raise ValueError(f"Unknown exploration decision step: {event.key}:{step_key}")
