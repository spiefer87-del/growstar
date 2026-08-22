# Aggregated Growstar release history.
from .current import CURRENT_RELEASES
from .legacy import RELEASES as LEGACY_RELEASES

RELEASES = tuple(CURRENT_RELEASES) + tuple(LEGACY_RELEASES)

__all__ = (
    "CURRENT_RELEASES",
    "LEGACY_RELEASES",
    "RELEASES",
)
