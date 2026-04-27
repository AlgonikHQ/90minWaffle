"""sportsdb — public image-lookup API for 90minWaffle content.

This is a thin facade over sportsdb_registry. card_generator.py imports
get_image_for_story() from here; the registry does the real work.

Keeping this module around (rather than letting callers import the registry
directly) means we can swap data sources later — e.g. add API-Football as
a secondary provider — without touching every call site.
"""

from typing import Optional

from sportsdb_registry import (
    get_image_for_story as _get_image_for_story,
    extract_player_names,
    find_team_in_text,
    find_player_image,
    best_team_image,
    best_player_image,
    resolve_team,
    get_roster,
    refresh_teams,
)

__all__ = [
    "get_image_for_story",
    "extract_player_names",
    "find_team_in_text",
    "find_player_image",
    "best_team_image",
    "best_player_image",
    "resolve_team",
    "get_roster",
    "refresh_teams",
]


def get_image_for_story(title: str, hook: str = "") -> Optional[str]:
    """Best-fit image URL for a story, or None if nothing reliable is found.

    Policy: never return a wrong image. If we can't verify a player belongs
    to the team mentioned in the story, we return the team badge instead.
    """
    return _get_image_for_story(title, hook)
