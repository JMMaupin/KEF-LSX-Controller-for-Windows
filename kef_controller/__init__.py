"""KEF LSX II Controller: version number.

The version number always has three parts, `major.minor.fix`: 0.3.0,
0.3.1, 0.3.2, then 0.4.0 ("0.3" and "0.3.0" are the same version).

The **major** changes when the existing configuration is no longer enough
as is -- a settings file whose format evolves, a setting whose meaning
changes. In other words: when an update requires checking something rather
than just restarting.

The **minor** changes when a feature is added: something one can do that
one could not before.

The **fix** number changes for every correction, behaviour included -- a
wrong command sent at boot, a wait too long, a wording. It is incremented
even for a detail, because its role is to answer a single question, asked
on a day something breaks: *which version is running in front of me?*

A third number, not a second decimal: versions compare number by number,
so "0.21" would read as newer than "0.3", and an update would be refused.

This module imports nothing but the standard library: build.py and
release.py read the version without the application's dependencies.
"""

__version__ = "0.3.0"


def version_tuple(text):
    """Comparable form of a version; "0.3" and "0.3.0" are the same."""
    parts = []
    for piece in str(text).split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    parts += [0] * (4 - len(parts))
    return tuple(parts[:4])
