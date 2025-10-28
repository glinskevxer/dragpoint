"""The release gate."""

from __future__ import annotations

import pytest

from dragpoint import __version__
from dragpoint.tools import release_check
from dragpoint.tools.support import DOCS, ROOT


def test_the_checkout_is_ready_to_release(capsys: pytest.CaptureFixture[str]) -> None:
    assert release_check.main(["--verbose"]) == 0
    assert __version__ in capsys.readouterr().out


def test_it_says_nothing_unless_it_is_asked_to(capsys: pytest.CaptureFixture[str]) -> None:
    assert release_check.main([]) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1] != f"release: {__version__} is ready"


def test_the_packaged_version_is_the_package_version() -> None:
    assert release_check._pyproject_version() == __version__


def test_the_changelog_has_something_to_say_about_this_version() -> None:
    assert release_check._changelog_mentions(__version__)


def test_a_version_nobody_wrote_about_is_not_mentioned() -> None:
    assert not release_check._changelog_mentions("99.9.9")


def test_every_document_a_release_ships_is_there() -> None:
    for name in release_check.WANTED_DOCS:
        assert (DOCS / name).is_file()


def test_every_check_is_run_again_here() -> None:
    modules = {check.__module__ for check in release_check.CHECKS}
    assert "dragpoint.tools.check_layers" in modules
    assert "dragpoint.tools.check_face" in modules
    assert len(release_check.CHECKS) >= 6


def test_every_generator_is_checked_rather_than_written() -> None:
    modules = {generator.__module__ for generator in release_check.GENERATORS}
    assert len(modules) == len(release_check.WANTED_DOCS)


def test_the_changelog_is_where_the_gate_looks_for_it() -> None:
    assert (ROOT / "CHANGELOG.md").is_file()
