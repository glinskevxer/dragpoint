"""A plate spec the compiler tests can lean on."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dragpoint.spec.plate import PlateSpec

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "mcc-panel-7.toml"


def plate_spec(**overrides: Any) -> PlateSpec:
    """The plate the shop cuts more of than any other."""
    values: dict[str, Any] = {
        "name": "P-101",
        "width": 60.0,
        "height": 20.0,
        "stock": "LAM16-BW",
        "lines": ("FEED PUMP 1", "RUN"),
    }
    values.update(overrides)
    return PlateSpec(**values)
