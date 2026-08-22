"""Backward-compatible alias for automatically discovered patch releases.

Do not add release dictionaries to this file. Every new patch belongs in its
own ``core/releases/r_<version>_<phase>.py`` module.
"""

from .loader import PATCH_RELEASES

CURRENT_RELEASES = PATCH_RELEASES

__all__ = ("CURRENT_RELEASES",)
