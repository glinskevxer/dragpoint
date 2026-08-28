"""Running the package as a module, which is how a shop with no path runs it.

``python -m dragpoint`` is the same command line as the ``dragpoint`` script
and it works before anything has been installed properly. That matters more
here than it sounds: the machine terminal is a Windows box somebody set up
in a hurry, the script directory is not on the path half the time, and the
alternative to this file is a note on the wall telling people what to type.
"""

from __future__ import annotations

import sys

from dragpoint.cli.main import main

__all__ = ["main"]

if __name__ == "__main__":
    sys.exit(main())
