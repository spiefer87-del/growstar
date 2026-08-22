"""Aggregated Growstar release history."""

from .legacy import RELEASES as LEGACY_RELEASES
from .loader import (
    CURRENT_RELEASES,
    PATCH_RELEASES,
    RELEASE_MODULES,
)

RELEASES = tuple(PATCH_RELEASES) + tuple(LEGACY_RELEASES)

__all__ = (
    "PATCH_RELEASES",
    "CURRENT_RELEASES",
    "RELEASE_MODULES",
    "LEGACY_RELEASES",
    "RELEASES",
)
