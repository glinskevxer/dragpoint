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


def test_every_check_module_is_found_by_name() -> None:
    names = release_check.check_names()
    assert "check_layers" in names
    assert "check_face" in names
    assert "check_examples" in names
    assert len(names) >= 7


def test_the_checks_are_found_and_not_listed() -> None:
    on_disk = sorted(
        path.stem for path in (ROOT / "src" / "dragpoint" / "tools").glob("check_*.py")
    )
    assert list(release_check.check_names()) == on_disk


def test_every_check_that_is_found_can_be_run() -> None:
    for name, entry in release_check.checks():
        assert callable(entry), name


def test_a_check_with_nothing_to_run_is_a_programming_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(release_check, "check_names", lambda: ("support",))
    with pytest.raises(AttributeError, match="no main"):
        release_check.checks()


def test_every_generator_is_checked_rather_than_written() -> None:
    modules = {generator.__module__ for generator in release_check.GENERATORS}
    assert len(modules) == len(release_check.WANTED_DOCS)


def test_the_changelog_is_where_the_gate_looks_for_it() -> None:
    assert (ROOT / "CHANGELOG.md").is_file()
