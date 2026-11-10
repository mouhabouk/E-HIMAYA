"""Pure rules of the inspections (docs/phase-i/design-i.md §4, §7): the model's weights, the score, the verdict, and
what a room reads of a report."""

from typing import Any, Literal

Room = Literal["central", "regional"]
Audience = Literal["none", "regional", "central", "both"]
ANSWERS = ("ok", "note", "ko")
PRIORITIES = ("high", "medium", "low")
DISCLOSED_FIELDS = ("inspection", "verdict", "score")


class InvalidModel(ValueError):
    """The calculation model does not add up; ``code`` names the rule."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def check_model(config: dict[str, Any]) -> None:
    """The items of each axis add up to the axis weight, the axes to the items weight, the elements to 100, and the
    thresholds and levels are ordered."""
    axes = config["axes"]
    items = config["items"]
    keys = [a["key"] for a in axes]
    if len(set(keys)) != len(keys) or not keys:
        raise InvalidModel("axes_invalid")
    if len({i["key"] for i in items}) != len(items) or not items:
        raise InvalidModel("items_invalid")
    for axis in axes:
        total = sum(i["weight"] for i in items if i["axis"] == axis["key"])
        if total != axis["weight"]:
            raise InvalidModel("weights_invalid")
    if any(i["axis"] not in keys for i in items):
        raise InvalidModel("items_invalid")
    weights = config["weights"]
    if sum(a["weight"] for a in axes) != weights["items"]:
        raise InvalidModel("weights_invalid")
    if weights["items"] + weights["presence"] + weights["exit"] != 100:
        raise InvalidModel("weights_invalid")
    exit_ = config["exit"]
    if not 0 < exit_["fast"] < exit_["ok"]:
        raise InvalidModel("exit_invalid")
    levels = config["levels"]
    mins = [lv["min"] for lv in levels]
    if not levels or mins != sorted(mins, reverse=True) or mins[-1] != 0 or len(set(mins)) != len(mins):
        raise InvalidModel("levels_invalid")


def items_value(config: dict[str, Any], answers: dict[str, str]) -> int | None:
    """Weighted mean of the answered items' values; None while nothing is answered."""
    weights = {i["key"]: i["weight"] for i in config["items"]}
    values = config["values"]
    total = weight = 0
    for key, answer in answers.items():
        w = weights.get(key, 0)
        if w and answer in values:
            total += values[answer] * w
            weight += w
    return round(total / weight) if weight else None


def exit_value(config: dict[str, Any], seconds: int | None) -> int | None:
    if seconds is None:
        return None
    t = config["exit"]
    if seconds <= t["fast"]:
        return int(t["fast_value"])
    if seconds <= t["ok"]:
        return int(t["ok_value"])
    return int(t["slow_value"])


def score(
    config: dict[str, Any], answers: dict[str, str], present: int | None, expected: int | None, exit_seconds: int | None
) -> int | None:
    """The readiness score (0-100). A missing element (presence or exit drill not recorded yet) gives its weight to the
    items, as the app shows while the inspection runs."""
    items = items_value(config, answers)
    if items is None:
        return None
    w = config["weights"]
    total = items * w["items"]
    rest = 0
    presence = None if present is None or not expected else min(100, round(present * 100 / expected))
    if presence is None:
        rest += w["presence"]
    else:
        total += presence * w["presence"]
    exit_ = exit_value(config, exit_seconds)
    if exit_ is None:
        rest += w["exit"]
    else:
        total += exit_ * w["exit"]
    total += items * rest
    return int(max(0, min(100, round(total / 100))))


def verdict(config: dict[str, Any], value: int) -> str:
    for level in config["levels"]:
        if value >= level["min"]:
            return str(level["name"])
    return str(config["levels"][-1]["name"])


def audience_flags(audience: Audience) -> tuple[bool, bool]:
    """(to_central, to_regional) of an audience."""
    return audience in ("central", "both"), audience in ("regional", "both")


def audience_of(to_central: bool, to_regional: bool) -> Audience:
    if to_central and to_regional:
        return "both"
    if to_central:
        return "central"
    return "regional" if to_regional else "none"


def disclosure_of(policy: dict[str, Any]) -> dict[str, dict[str, bool]]:
    """The disclosure a new report gets from the policy."""
    return {room: {f: bool(policy[room][f]) for f in DISCLOSED_FIELDS} for room in ("central", "regional")}


def recommendation_audience(policy: dict[str, Any], kind: str, priority: str | None) -> Audience:
    rules = policy["recommendations"]
    key = "general" if kind == "general" else (priority or "low")
    value = rules.get(key, "none")
    return value if value in ("none", "regional", "central", "both") else "none"


def room_view(disclosure: dict[str, Any], room: Room) -> dict[str, bool]:
    """What a room reads of a report: nothing unless the inspection itself is disclosed to it."""
    d = disclosure.get(room) or {}
    shown = bool(d.get("inspection"))
    return {"inspection": shown, "verdict": shown and bool(d.get("verdict")), "score": shown and bool(d.get("score"))}
