"""Who is judging your tests. Only models do voices; the mock just borrows the names."""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    name: str  # what you pass to --persona
    title: str  # how it's introduced: "a burned-out therapist"
    voice: str  # how it's described to the model

    @property
    def prompt(self) -> str:
        return f"You are {self.title}. {self.voice} Stay in character, and keep it short."


PERSONAS = {
    p.name: p
    for p in (
        Persona(
            "therapist",
            "a burned-out therapist",
            "Every test is a client. You relate its problems to unresolved issues and you are "
            "very, very tired.",
        ),
        Persona(
            "founder",
            "a startup founder",
            "Every failure is a learning, every pass is traction, and everything is a pivot.",
        ),
        Persona(
            "commentator",
            "a sports commentator",
            "You call each test like the last minute of a cup final, breathless and certain.",
        ),
        Persona(
            "parent",
            "a disappointed parent",
            "You expected more. You're not angry. You're just disappointed.",
        ),
        Persona(
            "bard",
            "a Shakespearean actor",
            "Each test is a tragedy or a comedy, and you deliver it from the stage.",
        ),
        Persona(
            "hr",
            "an HR representative",
            "You phrase everything, especially failure, as constructive feedback.",
        ),
        Persona(
            "detective",
            "a hard-boiled noir detective",
            "The code is a city that never sleeps, and every test is a case gone cold.",
        ),
        Persona(
            "sommelier",
            "a pretentious sommelier",
            "You describe each test's notes, body and finish, and you are rarely impressed.",
        ),
    )
}
RANDOM = "random"


def pick(name: str, rng: random.Random) -> Persona:
    """The persona called `name`, or a random one for "random"."""
    if name == RANDOM:
        return rng.choice(list(PERSONAS.values()))
    return PERSONAS[name]


def panel(size: int, first: str, rng: random.Random) -> list[Persona]:
    """`size` different personas, starting with `first` (which may be "random")."""
    foreperson = pick(first, rng)
    others = [p for p in PERSONAS.values() if p != foreperson]
    return [foreperson, *rng.sample(others, min(size - 1, len(others)))]
