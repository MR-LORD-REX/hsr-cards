"""Shared renderer primitives used by player and HSR card renderers."""

from .stars import render_stars
from .team import render_team

__all__ = ["render_stars", "render_team"]