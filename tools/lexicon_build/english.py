from __future__ import annotations

from typing import Any

from tools.lexicon_build.common import fail, validate_required_keys


def derive_en_present_3sg(lemma: str) -> str:
    if lemma.endswith(("s", "sh", "ch", "x", "z", "o")):
        return f"{lemma}es"
    if len(lemma) > 1 and lemma.endswith("y") and lemma[-2] not in "aeiou":
        return f"{lemma[:-1]}ies"
    return f"{lemma}s"


def derive_en_gerund(lemma: str) -> str:
    if lemma.endswith("ie"):
        return f"{lemma[:-2]}ying"
    if lemma.endswith("e") and lemma not in {"be", "see"}:
        return f"{lemma[:-1]}ing"
    if (
        len(lemma) >= 3
        and lemma[-1] not in "aeiouwxy"
        and lemma[-2] in "aeiou"
        and lemma[-3] not in "aeiou"
        and len(lemma) <= 4
    ):
        return f"{lemma}{lemma[-1]}ing"
    return f"{lemma}ing"


def derive_en_regular_past(lemma: str) -> str:
    if len(lemma) > 1 and lemma.endswith("y") and lemma[-2] not in "aeiou":
        return f"{lemma[:-1]}ied"
    if lemma.endswith("e"):
        return f"{lemma}d"
    if (
        len(lemma) >= 3
        and lemma[-1] not in "aeiouwxy"
        and lemma[-2] in "aeiou"
        and lemma[-3] not in "aeiou"
        and len(lemma) <= 4
    ):
        return f"{lemma}{lemma[-1]}ed"
    return f"{lemma}ed"


def normalize_string_or_list(value: Any, context: str) -> str | list[str]:
    if isinstance(value, str):
        stripped_value = value.strip()
        if not stripped_value:
            fail(f"{context}: value must not be empty")
        return stripped_value

    if isinstance(value, list):
        normalized_values: list[str] = []
        for index, item in enumerate(value, start=1):
            if not isinstance(item, str) or not item.strip():
                fail(f"{context}: list item #{index} must be a non-empty string")
            normalized_values.append(item.strip())
        if not normalized_values:
            fail(f"{context}: list must not be empty")
        return normalized_values

    fail(f"{context}: expected string or list of strings")


def example_form_value(value: str | list[str]) -> str:
    if isinstance(value, list):
        return value[0]
    return value


def make_examples(*sentences: str) -> list[dict[str, str]]:
    return [{"dst": sentence} for sentence in sentences]


TRANSITIVE_OBJECTS: dict[str, tuple[str, str, str, str, str]] = {
    "have": (
        "a small office",
        "a long meeting",
        "the result",
        "support",
        "Have a seat.",
    ),
    "get": ("new ideas", "a reply", "the tickets", "ready", "Get some rest."),
    "make": ("coffee", "good soup", "a plan", "lunch", "Make a note."),
    "take": ("the bus", "her laptop", "the wrong train", "notes", "Take this seat."),
    "see": (
        "the mountains",
        "her friends",
        "a good film",
        "a doctor",
        "See for yourself.",
    ),
    "use": (
        "this notebook",
        "her phone",
        "the back door",
        "the new system",
        "Use this carefully.",
    ),
    "find": (
        "this book useful",
        "small errors",
        "the receipt",
        "new clients",
        "Find out the truth.",
    ),
    "need": (
        "more time",
        "a short break",
        "help",
        "more support",
        "Need is not enough.",
    ),
    "keep": ("a journal", "her promises", "the door closed", "a record", "Keep going."),
    "bring": (
        "lunch to work",
        "fresh flowers",
        "the documents",
        "coffee for everyone",
        "Bring your ID.",
    ),
    "write": (
        "in a notebook",
        "emails every day",
        "the report",
        "a new chapter",
        "Write it down.",
    ),
    "lose": (
        "my keys often",
        "her temper sometimes",
        "the receipt",
        "patience",
        "Lose the fear.",
    ),
    "include": (
        "fresh fruit",
        "a map",
        "the appendix",
        "everyone",
        "Include the details.",
    ),
    "change": (
        "my schedule often",
        "her mind quickly",
        "the plan",
        "the settings",
        "Change the plan.",
    ),
    "watch": (
        "the news every night",
        "a short video",
        "the game",
        "the screen",
        "Watch this.",
    ),
}


MOTION_PLACES: dict[str, tuple[str, str, str, str, str]] = {
    "go": (
        "to work by bus",
        "to school early",
        "home after lunch",
        "to the station",
        "Go inside.",
    ),
    "come": ("home at six", "to class on time", "by train", "to the party", "Come in."),
    "leave": (
        "home at eight",
        "the office late",
        "for London",
        "the building now",
        "Leave now.",
    ),
    "run": (
        "in the park every morning",
        "to catch the bus",
        "five miles yesterday",
        "toward the station",
        "Run faster.",
    ),
    "sit": (
        "by the window",
        "near the door",
        "there yesterday",
        "at the front now",
        "Sit down.",
    ),
    "stand": (
        "near the wall",
        "by the window",
        "outside for an hour",
        "in the hall now",
        "Stand here.",
    ),
}


TOPIC_PREPOSITIONS: dict[str, tuple[str, str, str, str, str]] = {
    "think": (
        "about my future often",
        "the idea is good",
        "about the trip",
        "about dinner now",
        "Think again.",
    ),
    "look": (
        "at the screen all day",
        "tired this morning",
        "for the key",
        "at the map now",
        "Look here.",
    ),
    "talk": (
        "about work a lot",
        "to her sister every day",
        "about the problem",
        "with the team now",
        "Talk to me.",
    ),
}


MENTAL_CONTENT: dict[str, tuple[str, str, str, str, str]] = {
    "know": (
        "the answer",
        "my sister well",
        "the address",
        "the problem well",
        "Know the rules.",
    ),
    "hear": (
        "music every evening",
        "a strange noise",
        "the news",
        "someone outside now",
        "Hear me out.",
    ),
    "believe": (
        "your story",
        "that the plan will work",
        "the rumor",
        "in this idea",
        "Believe me.",
    ),
    "learn": (
        "new words every day",
        "fast in class",
        "a lot yesterday",
        "more about the topic now",
        "Learn from this.",
    ),
    "understand": (
        "this question",
        "the instructions",
        "the reason",
        "what you mean now",
        "Understand this.",
    ),
}


ACTIVITY_GENERAL: dict[str, tuple[str, str, str, str, str]] = {
    "do": (
        "my homework every evening",
        "the dishes after dinner",
        "the laundry",
        "our best now",
        "Do it carefully.",
    ),
    "work": (
        "in an office downtown",
        "at a small hospital",
        "late",
        "on a new project now",
        "Work steadily.",
    ),
    "begin": (
        "work at eight",
        "with a short note",
        "the lesson",
        "the meeting now",
        "Begin here.",
    ),
    "start": (
        "early every day",
        "with coffee",
        "the engine",
        "the lesson now",
        "Start now.",
    ),
    "continue": (
        "after lunch",
        "with the next page",
        "the course",
        "the discussion now",
        "Continue.",
    ),
}


PERSON_OBJECT: dict[str, tuple[str, str, str, str, str]] = {
    "give": (
        "my plants water every morning",
        "good advice",
        "us a ride",
        "the children snacks now",
        "Give me a minute.",
    ),
    "call": (
        "my mother every Sunday",
        "a taxi after work",
        "the doctor",
        "the hotel now",
        "Call me later.",
    ),
    "show": (
        "my notes to the class",
        "the photo to her friend",
        "us the way",
        "the visitors around now",
        "Show me.",
    ),
    "help": (
        "my brother with homework",
        "her neighbor often",
        "us yesterday",
        "the children now",
        "Help me.",
    ),
    "provide": (
        "my team with updates",
        "clear instructions",
        "us support",
        "the group with water now",
        "Provide details.",
    ),
    "meet": (
        "my tutor every Friday",
        "the client today",
        "us at the station",
        "with the team now",
        "Meet me there.",
    ),
    "lead": (
        "a small team at work",
        "the group confidently",
        "the meeting",
        "the discussion now",
        "Lead the way.",
    ),
}


PERSON_CONTENT: dict[str, tuple[str, str, str, str, str]] = {
    "say": (
        "hello every morning",
        "the right words",
        "goodbye",
        "the same thing now",
        "Say that again.",
    ),
    "tell": (
        "my son a story every night",
        "the truth",
        "us the news",
        "the driver our address now",
        "Tell me.",
    ),
    "ask": (
        "a lot of questions in class",
        "the teacher for help",
        "about the price",
        "about the schedule now",
        "Ask again.",
    ),
    "mean": ("what I say", "well", "something else", "this as a joke", "Mean it."),
}


OBJECT_PLACE: dict[str, tuple[str, str, str, str, str]] = {
    "put": (
        "my keys on the table",
        "the book on the shelf",
        "everything away",
        "the cups in the sink now",
        "Put it here.",
    ),
    "set": (
        "my phone on silent",
        "the table for dinner",
        "the alarm",
        "the chairs in place now",
        "Set it aside.",
    ),
}


INFINITIVE_COMPLEMENT: dict[str, tuple[str, str, str, str, str]] = {
    "want": (
        "to leave early",
        "to study abroad",
        "more time",
        "a quiet evening",
        "Want less.",
    ),
    "try": (
        "to stay calm",
        "to help everyone",
        "to call him",
        "to solve the problem now",
        "Try again.",
    ),
    "let": (
        "my son choose his clothes",
        "her team decide",
        "us leave early",
        "me explain now",
        "Let me speak.",
    ),
}


COPULA_STATE: dict[str, tuple[str, str, str, str, str]] = {
    "be": ("at home", "at work", "late yesterday", "careful now", "Be careful."),
    "feel": (
        "tired after work",
        "much better today",
        "sick yesterday",
        "more relaxed now",
        "Feel free.",
    ),
    "become": (
        "tired in the evening",
        "more confident each year",
        "friends quickly",
        "stronger now",
        "Become stronger.",
    ),
    "seem": (
        "calm today",
        "happy this morning",
        "different yesterday",
        "more confident now",
        "Seem calm.",
    ),
}


SELF_OR_OBJECT_MOTION: dict[str, tuple[str, str, str, str, str]] = {
    "turn": (
        "left at the corner",
        "the page slowly",
        "back too late",
        "toward the door now",
        "Turn right.",
    ),
    "move": (
        "to a new apartment",
        "the chair closer",
        "to Boston",
        "the boxes now",
        "Move carefully.",
    ),
}


RESIDENCE_PLACE: dict[str, tuple[str, str, str, str, str]] = {
    "live": (
        "in Boston now",
        "near the river",
        "there for years",
        "with her parents now",
        "Live well.",
    ),
}


GAME_OR_MUSIC: dict[str, tuple[str, str, str, str, str]] = {
    "play": (
        "tennis on weekends",
        "the piano beautifully",
        "a long match",
        "music now",
        "Play on.",
    ),
}


INTRANSITIVE_EVENT: dict[str, tuple[str, str, str, str, str]] = {
    "happen": (
        "all the time here",
        "rarely by accident",
        "yesterday afternoon",
        "very fast now",
        "Let it happen.",
    ),
}


PAYMENT: dict[str, tuple[str, str, str, str, str]] = {
    "pay": (
        "my bills online",
        "for coffee by card",
        "the rent",
        "for lunch now",
        "Pay attention.",
    ),
}


def build_en_examples(
    lemma: str,
    present_3sg: str,
    past: str,
    gerund: str,
    strategy: str,
    built_in_examples: dict[str, list[str]],
) -> list[dict[str, str]]:
    custom_examples = built_in_examples.get(lemma)
    if custom_examples:
        return [{"dst": sentence} for sentence in custom_examples]

    if strategy == "copula_state":
        present_phrase, third_phrase, past_phrase, progressive_phrase, imperative = (
            COPULA_STATE.get(
                lemma,
                ("ready", "calm", "fine yesterday", "careful now", "Be ready."),
            )
        )
        if lemma == "be":
            return make_examples(
                f"I am {present_phrase}.",
                f"She is {third_phrase}.",
                f"They were {past_phrase}.",
                f"We are being {progressive_phrase}.",
                imperative,
            )
        return make_examples(
            f"I {lemma} {present_phrase}.",
            f"She {present_3sg} {third_phrase}.",
            f"They {past} {past_phrase}.",
            f"We are {gerund} {progressive_phrase}.",
            imperative,
        )

    if strategy == "transitive_object":
        first_phrase, third_phrase, past_phrase, progressive_phrase, imperative = (
            TRANSITIVE_OBJECTS.get(
                lemma,
                (
                    "the file every day",
                    "the document carefully",
                    "the report",
                    "the task now",
                    f"{lemma.capitalize()} it.",
                ),
            )
        )
        return make_examples(
            f"I {lemma} {first_phrase}.",
            f"She {present_3sg} {third_phrase}.",
            f"They {past} {past_phrase} yesterday.",
            f"We are {gerund} {progressive_phrase}.",
            imperative,
        )

    if strategy == "motion_place":
        first_phrase, third_phrase, past_phrase, progressive_phrase, imperative = (
            MOTION_PLACES.get(
                lemma,
                (
                    "home early",
                    "to school on time",
                    "there yesterday",
                    "toward the station now",
                    f"{lemma.capitalize()} there.",
                ),
            )
        )
        return make_examples(
            f"I {lemma} {first_phrase}.",
            f"She {present_3sg} {third_phrase}.",
            f"They {past} {past_phrase}.",
            f"We are {gerund} {progressive_phrase}.",
            imperative,
        )

    if strategy == "topic_preposition":
        first_phrase, third_phrase, past_phrase, progressive_phrase, imperative = (
            TOPIC_PREPOSITIONS.get(
                lemma,
                (
                    "about this often",
                    "about the issue",
                    "about it",
                    "about the problem now",
                    f"{lemma.capitalize()} again.",
                ),
            )
        )
        return make_examples(
            f"I {lemma} {first_phrase}.",
            f"She {present_3sg} {third_phrase}.",
            f"They {past} {past_phrase} yesterday.",
            f"We are {gerund} {progressive_phrase}.",
            imperative,
        )

    if strategy == "person_object":
        first_phrase, third_phrase, past_phrase, progressive_phrase, imperative = (
            PERSON_OBJECT.get(
                lemma,
                (
                    "my friend every week",
                    "the class clearly",
                    "us yesterday",
                    "the group now",
                    f"{lemma.capitalize()} me.",
                ),
            )
        )
        return make_examples(
            f"I {lemma} {first_phrase}.",
            f"She {present_3sg} {third_phrase}.",
            f"They {past} {past_phrase}.",
            f"We are {gerund} {progressive_phrase}.",
            imperative,
        )

    if strategy == "person_content":
        first_phrase, third_phrase, past_phrase, progressive_phrase, imperative = (
            PERSON_CONTENT.get(
                lemma,
                (
                    "the truth",
                    "something useful",
                    "that yesterday",
                    "the same thing now",
                    f"{lemma.capitalize()} it.",
                ),
            )
        )
        return make_examples(
            f"I {lemma} {first_phrase}.",
            f"She {present_3sg} {third_phrase}.",
            f"They {past} {past_phrase}.",
            f"We are {gerund} {progressive_phrase}.",
            imperative,
        )

    if strategy == "object_place":
        first_phrase, third_phrase, past_phrase, progressive_phrase, imperative = (
            OBJECT_PLACE.get(
                lemma,
                (
                    "the book on the desk",
                    "the keys by the door",
                    "everything away",
                    "the chairs in place now",
                    f"{lemma.capitalize()} it there.",
                ),
            )
        )
        return make_examples(
            f"I {lemma} {first_phrase}.",
            f"She {present_3sg} {third_phrase}.",
            f"They {past} {past_phrase}.",
            f"We are {gerund} {progressive_phrase}.",
            imperative,
        )

    if strategy == "infinitive_complement":
        first_phrase, third_phrase, past_phrase, progressive_phrase, imperative = (
            INFINITIVE_COMPLEMENT.get(
                lemma,
                (
                    "to leave early",
                    "to help",
                    "to go",
                    "to solve it now",
                    f"{lemma.capitalize()} again.",
                ),
            )
        )
        if lemma == "want":
            return make_examples(
                f"I {lemma} {first_phrase}.",
                f"She {present_3sg} {third_phrase}.",
                f"They {past} more time yesterday.",
                f"We {lemma} a quiet evening.",
                imperative,
            )
        return make_examples(
            f"I {lemma} {first_phrase}.",
            f"She {present_3sg} {third_phrase}.",
            f"They {past} {past_phrase} yesterday.",
            f"We are {gerund} {progressive_phrase}.",
            imperative,
        )

    if strategy == "mental_content":
        first_phrase, third_phrase, past_phrase, progressive_phrase, imperative = (
            MENTAL_CONTENT.get(
                lemma,
                (
                    "the answer",
                    "the problem",
                    "that yesterday",
                    "more now",
                    f"{lemma.capitalize()} this.",
                ),
            )
        )
        return make_examples(
            f"I {lemma} {first_phrase}.",
            f"She {present_3sg} {third_phrase}.",
            f"They {past} {past_phrase}.",
            f"We are {gerund} {progressive_phrase}.",
            imperative,
        )

    if strategy == "activity_general":
        first_phrase, third_phrase, past_phrase, progressive_phrase, imperative = (
            ACTIVITY_GENERAL.get(
                lemma,
                (
                    "every day",
                    "carefully",
                    "yesterday",
                    "right now",
                    f"{lemma.capitalize()} now.",
                ),
            )
        )
        return make_examples(
            f"I {lemma} {first_phrase}.",
            f"She {present_3sg} {third_phrase}.",
            f"They {past} {past_phrase}.",
            f"We are {gerund} {progressive_phrase}.",
            imperative,
        )

    if strategy == "intransitive_event":
        first_phrase, third_phrase, past_phrase, progressive_phrase, imperative = (
            INTRANSITIVE_EVENT.get(
                lemma,
                ("sometimes", "rarely", "yesterday", "again now", "Let it happen."),
            )
        )
        return make_examples(
            f"It can {lemma} {first_phrase}.",
            f"It {present_3sg} {third_phrase}.",
            f"It {past} {past_phrase}.",
            f"It is {gerund} {progressive_phrase}.",
            imperative,
        )

    if strategy == "game_or_music":
        first_phrase, third_phrase, past_phrase, progressive_phrase, imperative = (
            GAME_OR_MUSIC.get(
                lemma,
                (
                    "soccer on weekends",
                    "the piano well",
                    "a match yesterday",
                    "music now",
                    f"{lemma.capitalize()} on.",
                ),
            )
        )
        return make_examples(
            f"I {lemma} {first_phrase}.",
            f"She {present_3sg} {third_phrase}.",
            f"They {past} {past_phrase}.",
            f"We are {gerund} {progressive_phrase}.",
            imperative,
        )

    if strategy == "self_or_object_motion":
        first_phrase, third_phrase, past_phrase, progressive_phrase, imperative = (
            SELF_OR_OBJECT_MOTION.get(
                lemma,
                (
                    "left at the corner",
                    "the page slowly",
                    "back too late",
                    "toward the door now",
                    f"{lemma.capitalize()} now.",
                ),
            )
        )
        return make_examples(
            f"I {lemma} {first_phrase}.",
            f"She {present_3sg} {third_phrase}.",
            f"They {past} {past_phrase}.",
            f"We are {gerund} {progressive_phrase}.",
            imperative,
        )

    if strategy == "residence_place":
        first_phrase, third_phrase, past_phrase, progressive_phrase, imperative = (
            RESIDENCE_PLACE.get(
                lemma,
                (
                    "in Boston now",
                    "near the river",
                    "there for years",
                    "with family now",
                    "Live well.",
                ),
            )
        )
        return make_examples(
            f"I {lemma} {first_phrase}.",
            f"She {present_3sg} {third_phrase}.",
            f"They {past} {past_phrase}.",
            f"We are {gerund} {progressive_phrase}.",
            imperative,
        )

    if strategy == "payment":
        first_phrase, third_phrase, past_phrase, progressive_phrase, imperative = (
            PAYMENT.get(
                lemma,
                (
                    "my bills online",
                    "for coffee by card",
                    "the rent yesterday",
                    "for lunch now",
                    "Pay attention.",
                ),
            )
        )
        return make_examples(
            f"I {lemma} {first_phrase}.",
            f"She {present_3sg} {third_phrase}.",
            f"They {past} {past_phrase}.",
            f"We are {gerund} {progressive_phrase}.",
            imperative,
        )

    fail(
        f"no English example generator implemented for strategy '{strategy}' (lemma: {lemma})"
    )


def expand_english_entry(
    seed_entry: dict[str, Any],
    rank: int,
    built_in_examples: dict[str, list[str]],
) -> dict[str, Any]:
    context = f"English seed #{rank}"
    strategy = seed_entry.get("example_strategy", "generic")

    validate_required_keys(seed_entry, ["id", "lemma"], context)

    seed_id = seed_entry["id"]
    lemma = seed_entry["lemma"]
    irregular_object = seed_entry.get("irregular", {})
    examples_object = seed_entry.get("examples")

    if not isinstance(seed_id, str) or not seed_id.strip():
        fail(f"{context}: id must be a non-empty string")
    if not isinstance(lemma, str) or not lemma.strip():
        fail(f"{context}: lemma must be a non-empty string")
    if irregular_object is not None and not isinstance(irregular_object, dict):
        fail(f"{context}: irregular must be an object if present")
    if examples_object is not None and not isinstance(examples_object, list):
        fail(f"{context}: examples must be a list if present")
    if not isinstance(strategy, str) or not strategy.strip():
        fail(f"{context}: example_strategy must be a non-empty string if present")

    irregular: dict[str, Any] = (
        irregular_object if isinstance(irregular_object, dict) else {}
    )

    base = lemma

    irregular_past = irregular.get("past")
    if irregular_past is None:
        past: str | list[str] = derive_en_regular_past(lemma)
    else:
        past = normalize_string_or_list(irregular_past, f"{context}: irregular.past")

    irregular_past_participle = irregular.get("past_participle")
    if irregular_past_participle is None:
        if isinstance(past, list):
            fail(
                f"{context}: irregular.past_participle is required when irregular.past is a list"
            )
        past_participle = past
    else:
        normalized_past_participle = normalize_string_or_list(
            irregular_past_participle,
            f"{context}: irregular.past_participle",
        )
        if isinstance(normalized_past_participle, list):
            fail(f"{context}: irregular.past_participle must be a string")
        past_participle = normalized_past_participle

    irregular_present_1sg = irregular.get("present_1sg")
    if irregular_present_1sg is not None:
        normalized_present_1sg = normalize_string_or_list(
            irregular_present_1sg,
            f"{context}: irregular.present_1sg",
        )
        if isinstance(normalized_present_1sg, list):
            fail(f"{context}: irregular.present_1sg must be a string")
        present_1sg = normalized_present_1sg
    else:
        present_1sg = None

    irregular_present_3sg = irregular.get("present_3sg")
    if irregular_present_3sg is None:
        present_3sg = derive_en_present_3sg(lemma)
    else:
        normalized_present_3sg = normalize_string_or_list(
            irregular_present_3sg,
            f"{context}: irregular.present_3sg",
        )
        if isinstance(normalized_present_3sg, list):
            fail(f"{context}: irregular.present_3sg must be a string")
        present_3sg = normalized_present_3sg

    irregular_present_other = irregular.get("present_other")
    if irregular_present_other is not None:
        normalized_present_other = normalize_string_or_list(
            irregular_present_other,
            f"{context}: irregular.present_other",
        )
        if isinstance(normalized_present_other, list):
            fail(f"{context}: irregular.present_other must be a string")
        present_other = normalized_present_other
    else:
        present_other = None

    irregular_gerund = irregular.get("gerund")
    if irregular_gerund is None:
        gerund = derive_en_gerund(lemma)
    else:
        normalized_gerund = normalize_string_or_list(
            irregular_gerund,
            f"{context}: irregular.gerund",
        )
        if isinstance(normalized_gerund, list):
            fail(f"{context}: irregular.gerund must be a string")
        gerund = normalized_gerund

    runtime_examples: list[dict[str, str]]
    if examples_object:
        runtime_examples = []
        for index, example in enumerate(examples_object, start=1):
            if not isinstance(example, dict):
                fail(f"{context}: example #{index} must be an object")
            sentence = example.get("dst")
            if not isinstance(sentence, str) or not sentence.strip():
                fail(f"{context}: example #{index} must contain non-empty 'dst'")
            runtime_examples.append({"dst": sentence})
    else:
        runtime_examples = build_en_examples(
            lemma=lemma,
            present_3sg=present_3sg,
            past=example_form_value(past),
            gerund=gerund,
            strategy=strategy,
            built_in_examples=built_in_examples,
        )

    forms: dict[str, Any] = {
        "base": base,
        "past": past,
        "past_participle": past_participle,
        "present_3sg": present_3sg,
        "gerund": gerund,
    }

    if present_1sg is not None:
        forms["present_1sg"] = present_1sg

    if present_other is not None:
        forms["present_other"] = present_other

    return {
        "id": seed_id,
        "rank": rank,
        "lemma": lemma,
        "forms": forms,
        "examples": runtime_examples,
    }
