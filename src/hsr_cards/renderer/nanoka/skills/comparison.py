"""Attach inline differences to resolved skills and eidolon descriptions."""
from __future__ import annotations

from hsr_cards.renderer.nanoka.diff import diff_runs
from hsr_cards.renderer.nanoka.skills.models import SkillData
from hsr_cards.renderer.nanoka.skills.styles import KIND_COLOR
from hsr_cards.renderer.nanoka.skills.text import description_tokens, eidolon_tokens


def mark_skill_diff(before: SkillData, after: SkillData) -> None:
    """Attach skill/eidolon word differences to the newer model in place.

    Match entries by stable keys, mark absent-old entries new and changed entries
    changed, and attach their previous objects plus added/removed runs. Unchanged
    normalized text has no change marker. No provider, cache or file IO occurs.
    """
    previous_skills = {group.key: group for group in before.skills}
    for group in after.skills:
        old = previous_skills.get(group.key)
        if old is None:
            group.change = "new"
            group.diff_runs = _runs_with_added(
                description_tokens(group), KIND_COLOR["added"]
            )
            continue
        old_runs = description_tokens(old)
        new_runs = description_tokens(group)
        if _plain_runs(old_runs) == _plain_runs(new_runs):
            group.change = None
            continue
        group.before = old
        group.change = "changed"
        group.diff_runs = diff_runs(old_runs, new_runs, locale=group_locale(after))

    previous_ranks = {rank.key: rank for rank in before.eidolons}
    for rank in after.eidolons:
        old = previous_ranks.get(rank.key)
        if old is None:
            rank.change = "new"
            rank.diff_runs = _runs_with_added(eidolon_tokens(rank), KIND_COLOR["added"])
            continue
        old_runs = eidolon_tokens(old)
        new_runs = eidolon_tokens(rank)
        if _plain_runs(old_runs) == _plain_runs(new_runs):
            rank.change = None
            continue
        rank.before = old
        rank.change = "changed"
        rank.diff_runs = diff_runs(old_runs, new_runs, locale=group_locale(after))


def group_locale(data: SkillData) -> str:
    """Return the SkillData locale used to tokenize comparison differences."""
    return data.locale


def _plain_runs(runs) -> str:
    return " ".join(text for text, kind, _ in runs if text != "\n" and text.strip())


def _runs_with_added(runs, color):
    return [
        (text, "added" if not kind.startswith("removed") else kind, color)
        if text != "\n"
        else (text, kind, color)
        for text, kind, color in runs
    ]
