#!/usr/bin/env python3
"""Compatibility entry point for the former CORE.R1/R2 split regression.

The migration-specific test was retired after CORE.R3. The permanent,
version-agnostic architecture test now lives in check_release_system.py.
"""

from check_release_system import main


if __name__ == "__main__":
    main()
