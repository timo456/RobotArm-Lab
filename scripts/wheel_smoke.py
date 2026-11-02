"""Compatibility entry point for v0.1.1 clean-environment wheel verification.

Use python scripts/clean_environment.py; --environment selects a new checkout-local
path. Existing environments are never silently overwritten.
"""

from clean_environment import main

if __name__ == "__main__":
    main()
