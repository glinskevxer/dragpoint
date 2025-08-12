"""The command line.

Nothing in here decides anything. Every command reads, calls into the
package and prints, so that the behaviour of dragpoint can be tested without
starting a process.
"""

from dragpoint.cli.main import main

__all__ = ["main"]
