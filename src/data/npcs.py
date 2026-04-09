from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NpcChoiceOutcomeDefinition:
    title: str
    description: str
    event_type: str
    xp_reward: int
    next_state: str
    next_stage: int
    combat_outcome: str | None = None


@dataclass(frozen=True, slots=True)
class NpcChoiceOptionDefinition:
    key: str
    label: str
    style: str
    outcome: NpcChoiceOutcomeDefinition


@dataclass(frozen=True, slots=True)
class NpcEncounterDefinition:
    key: str
    npc_id: str
    stage_number: int
    title: str
    description: str
    options: tuple[NpcChoiceOptionDefinition, ...]


@dataclass(frozen=True, slots=True)
class RecurringNpcDefinition:
    id: str
    name: str
    personality: str
    location_keys: tuple[str, ...]
    cooldown_minutes: int
    stage_one_chance: float
    stage_two_chance: float
    stage_three_chance: float
    encounters: dict[tuple[int, str], NpcEncounterDefinition]

    def get_stage_chance(self, stage: int) -> float:
        if stage <= 0:
            return self.stage_one_chance
        if stage == 1:
            return self.stage_two_chance
        if stage == 2:
            return self.stage_three_chance
        return 0.0


def _outcome(
    *,
    title: str,
    description: str,
    event_type: str,
    xp_reward: int,
    next_state: str,
    next_stage: int,
    combat_outcome: str | None = None,
) -> NpcChoiceOutcomeDefinition:
    return NpcChoiceOutcomeDefinition(
        title=title,
        description=description,
        event_type=event_type,
        xp_reward=xp_reward,
        next_state=next_state,
        next_stage=next_stage,
        combat_outcome=combat_outcome,
    )


def _option(
    *,
    key: str,
    label: str,
    style: str,
    outcome: NpcChoiceOutcomeDefinition,
) -> NpcChoiceOptionDefinition:
    return NpcChoiceOptionDefinition(
        key=key,
        label=label,
        style=style,
        outcome=outcome,
    )


KAITO_STAGE_ONE = NpcEncounterDefinition(
    key="kaito_stage_1",
    npc_id="kaito",
    stage_number=1,
    title="A Boy on the Verge",
    description=(
        "A nervous soul is crouched beside a broken wall, trying to hide how badly he is shaking. "
        "His name is **Kaito**, and hunger has stripped the fear right through him."
    ),
    options=(
        _option(
            key="help",
            label="Help",
            style="success",
            outcome=_outcome(
                title="Kaito Eats in Silence",
                description=(
                    "You share what little you can. Kaito barely speaks, but the way he clutches the food tells you he will remember this."
                ),
                event_type="reward",
                xp_reward=12,
                next_state="helped",
                next_stage=1,
            ),
        ),
        _option(
            key="ignore",
            label="Ignore",
            style="secondary",
            outcome=_outcome(
                title="You Walk Past",
                description=(
                    "You leave Kaito to the cold and the hunger. He lowers his eyes like he expected nothing else from the street."
                ),
                event_type="flavor",
                xp_reward=4,
                next_state="ignored",
                next_stage=1,
            ),
        ),
        _option(
            key="rob",
            label="Rob",
            style="danger",
            outcome=_outcome(
                title="You Take What He Has",
                description=(
                    "You strip the last scraps from Kaito and leave him with nothing. He does not fight back, but the look he gives you lingers."
                ),
                event_type="choice",
                xp_reward=2,
                next_state="robbed",
                next_stage=1,
            ),
        ),
    ),
)

KAITO_STAGE_TWO_HELPED = NpcEncounterDefinition(
    key="kaito_stage_2_helped",
    npc_id="kaito",
    stage_number=2,
    title="Kaito Finds You First",
    description=(
        "Kaito spots you near a dim cookfire, thinner than before but steadier. He nervously offers a rumor about a hidden ration lane, hoping to repay what you did."
    ),
    options=(
        _option(
            key="trust_him",
            label="Trust him",
            style="success",
            outcome=_outcome(
                title="The Rumor Pays Off",
                description=(
                    "You follow Kaito's lead and it turns into a real score. For the first time, he manages a small smile."
                ),
                event_type="reward",
                xp_reward=20,
                next_state="trusted_kaito",
                next_stage=2,
            ),
        ),
        _option(
            key="send_him_away",
            label="Send him away",
            style="secondary",
            outcome=_outcome(
                title="He Steps Back",
                description=(
                    "You refuse the lead. Kaito nods like he understands, but the chance between you closes a little."
                ),
                event_type="choice",
                xp_reward=8,
                next_state="distant",
                next_stage=2,
            ),
        ),
        _option(
            key="press_him",
            label="Press him for more",
            style="danger",
            outcome=_outcome(
                title="You Push Too Hard",
                description=(
                    "You lean on Kaito for every detail until panic takes over. He bolts before the story is complete, and whatever trust existed goes with him."
                ),
                event_type="flavor",
                xp_reward=5,
                next_state="shaken",
                next_stage=2,
            ),
        ),
    ),
)

KAITO_STAGE_TWO_IGNORED = NpcEncounterDefinition(
    key="kaito_stage_2_ignored",
    npc_id="kaito",
    stage_number=2,
    title="Kaito Keeps His Distance",
    description=(
        "You catch Kaito again near the alley drains. He looks worse, and this time he only glances up long enough to decide whether you are worth the risk."
    ),
    options=(
        _option(
            key="help_now",
            label="Help now",
            style="success",
            outcome=_outcome(
                title="Late Kindness Still Matters",
                description=(
                    "You help him this time. Kaito is wary, but hunger leaves little room for pride, and he accepts it with a quiet nod."
                ),
                event_type="reward",
                xp_reward=16,
                next_state="helped_late",
                next_stage=2,
            ),
        ),
        _option(
            key="ignore_again",
            label="Ignore again",
            style="secondary",
            outcome=_outcome(
                title="The Street Teaches Its Lesson",
                description=(
                    "You pass by again. Kaito does not call out, and the silence says more than words would."
                ),
                event_type="flavor",
                xp_reward=4,
                next_state="abandoned",
                next_stage=2,
            ),
        ),
        _option(
            key="use_him",
            label="Use him for info",
            style="danger",
            outcome=_outcome(
                title="He Gives You a Name",
                description=(
                    "You wring a rumor out of him and move on. It helps you, but Kaito learns exactly what kind of soul you are."
                ),
                event_type="choice",
                xp_reward=10,
                next_state="used",
                next_stage=2,
            ),
        ),
    ),
)

KAITO_STAGE_TWO_ROBBED = NpcEncounterDefinition(
    key="kaito_stage_2_robbed",
    npc_id="kaito",
    stage_number=2,
    title="Kaito Does Not Forget",
    description=(
        "Kaito sees you before you see him. He is scared, angry, and trying not to show either while clutching a rag-wrapped bundle to his chest."
    ),
    options=(
        _option(
            key="return_something",
            label="Return something",
            style="success",
            outcome=_outcome(
                title="A Thin Attempt at Mercy",
                description=(
                    "You give back enough to matter. Kaito does not thank you, but the hatred in his eyes dulls into confusion."
                ),
                event_type="choice",
                xp_reward=10,
                next_state="partially_redeemed",
                next_stage=2,
            ),
        ),
        _option(
            key="threaten_him",
            label="Threaten him off",
            style="danger",
            outcome=_outcome(
                title="Fear Wins Again",
                description=(
                    "You drive him off one more time. He runs, but not before memorizing your face like a curse."
                ),
                event_type="combat",
                xp_reward=3,
                next_state="terrorized",
                next_stage=2,
                combat_outcome="Setback",
            ),
        ),
        _option(
            key="leave_him",
            label="Leave him",
            style="secondary",
            outcome=_outcome(
                title="Nothing Repaired",
                description=(
                    "You do not take more, but you do nothing to fix it either. Kaito watches until you are gone."
                ),
                event_type="flavor",
                xp_reward=5,
                next_state="resentful",
                next_stage=2,
            ),
        ),
    ),
)

KAITO_STAGE_THREE_TRUST = NpcEncounterDefinition(
    key="kaito_stage_3_trust",
    npc_id="kaito",
    stage_number=3,
    title="Kaito Brings the Last Thing He Has",
    description=(
        "Kaito finds you with a stolen map scrap and a trembling voice. He says it leads to an abandoned food cache if you believe him one last time."
    ),
    options=(
        _option(
            key="take_him_with_you",
            label="Take him with you",
            style="success",
            outcome=_outcome(
                title="A Better Ending Than Most",
                description=(
                    "You trust Kaito and bring him along. The cache is real, and for one rare night both of you walk away with more than survival."
                ),
                event_type="reward",
                xp_reward=32,
                next_state="saved",
                next_stage=3,
            ),
        ),
        _option(
            key="take_map_only",
            label="Take the map only",
            style="primary",
            outcome=_outcome(
                title="You Leave Him Behind",
                description=(
                    "The cache exists, but Kaito does not share in it. The score is good, though the guilt stains it."
                ),
                event_type="choice",
                xp_reward=22,
                next_state="used_again",
                next_stage=3,
            ),
        ),
    ),
)

KAITO_STAGE_THREE_FALL = NpcEncounterDefinition(
    key="kaito_stage_3_fall",
    npc_id="kaito",
    stage_number=3,
    title="Kaito Is Cornered",
    description=(
        "You find Kaito in a dead-end alley, trapped between hunger and the sort of souls who smell weakness. He looks at you like he already knows what kind of choice you will make."
    ),
    options=(
        _option(
            key="pull_him_out",
            label="Pull him out",
            style="success",
            outcome=_outcome(
                title="You Break the Pattern",
                description=(
                    "You drag Kaito out of the alley and away from the worst ending waiting for him. It does not fix Rukongai, but it matters to one soul."
                ),
                event_type="reward",
                xp_reward=24,
                next_state="rescued",
                next_stage=3,
            ),
        ),
        _option(
            key="leave_him_to_it",
            label="Leave him to it",
            style="secondary",
            outcome=_outcome(
                title="The Street Keeps What It Wants",
                description=(
                    "You leave him to the alley and whatever follows. Rukongai swallows people like Kaito every day, and tonight you let it."
                ),
                event_type="flavor",
                xp_reward=6,
                next_state="lost",
                next_stage=3,
            ),
        ),
        _option(
            key="turn_on_him",
            label="Turn on him",
            style="danger",
            outcome=_outcome(
                title="You Become the Worst Thing There",
                description=(
                    "You make Kaito's last bad day even worse. The reward is shallow, and the consequence lingers long after the alley is quiet."
                ),
                event_type="combat",
                xp_reward=2,
                next_state="broken",
                next_stage=3,
                combat_outcome="Setback",
            ),
        ),
    ),
)

KAITO = RecurringNpcDefinition(
    id="kaito",
    name="Kaito",
    personality="Nervous, starving, and struggling to survive.",
    location_keys=("rukongai_streets",),
    cooldown_minutes=45,
    stage_one_chance=0.05,
    stage_two_chance=0.08,
    stage_three_chance=0.10,
    encounters={
        (0, "default"): KAITO_STAGE_ONE,
        (1, "helped"): KAITO_STAGE_TWO_HELPED,
        (1, "ignored"): KAITO_STAGE_TWO_IGNORED,
        (1, "robbed"): KAITO_STAGE_TWO_ROBBED,
        (2, "trusted_kaito"): KAITO_STAGE_THREE_TRUST,
        (2, "helped_late"): KAITO_STAGE_THREE_TRUST,
        (2, "partially_redeemed"): KAITO_STAGE_THREE_TRUST,
        (2, "distant"): KAITO_STAGE_THREE_FALL,
        (2, "shaken"): KAITO_STAGE_THREE_FALL,
        (2, "abandoned"): KAITO_STAGE_THREE_FALL,
        (2, "used"): KAITO_STAGE_THREE_FALL,
        (2, "terrorized"): KAITO_STAGE_THREE_FALL,
        (2, "resentful"): KAITO_STAGE_THREE_FALL,
    },
)

RECURRING_NPCS = {
    KAITO.id: KAITO,
}


def get_npc_definition(npc_id: str) -> RecurringNpcDefinition:
    try:
        return RECURRING_NPCS[npc_id]
    except KeyError as error:
        raise ValueError(f"Unknown recurring NPC: {npc_id}") from error


def get_npc_encounter(
    npc_id: str,
    *,
    stage: int,
    state: str,
) -> NpcEncounterDefinition | None:
    npc = get_npc_definition(npc_id)
    return npc.encounters.get((stage, state)) or npc.encounters.get((stage, "default"))


def get_location_npcs(location_key: str) -> tuple[RecurringNpcDefinition, ...]:
    return tuple(
        npc
        for npc in RECURRING_NPCS.values()
        if location_key in npc.location_keys
    )
