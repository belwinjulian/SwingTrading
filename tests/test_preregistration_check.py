"""FND-05 -- Preregistration CI gate behavior tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

DOC_TEMPLATE_HEADER = "# Strategy v1 Pre-Registration\n\n## v1 Composite Weights\n\n"
DOC_TABLE_HEADER = (
    "| Component                              | Target Weight | Frozen Weight |\n"
    "|----------------------------------------|---------------|---------------|\n"
)

# Map of short friendly prefix -> (full row component name, target weight)
_ROW_DEFS = [
    ("RS percentile", "RS percentile (IBD-style)", "25%"),
    ("Trend Template", "Trend Template (0-8 normalized)", "20%"),
    ("Pattern", "Pattern (VCP/flag tightness)", "20%"),
    ("Volume confirmation", "Volume confirmation", "10%"),
    ("Earnings momentum", "Earnings momentum (CANSLIM C+A)", "15%"),
    ("Catalyst presence", "Catalyst presence", "10%"),
]


def _write_doc(tmp_path: Path, frozen: dict[str, str]) -> Path:
    """Write a fixture preregistration doc with the given frozen weights.

    `frozen` maps friendly name prefix -> percentage string (e.g., "25%").
    Keys must match the NAME_TO_KEY entries in check_preregistration.py.
    """
    rows = []
    for short_prefix, full_name, target in _ROW_DEFS:
        fw = frozen.get(short_prefix)
        if fw is not None:
            rows.append(f"| {full_name} | {target} | {fw} |")
    doc_path = tmp_path / "docs" / "strategy_v1_preregistration.md"
    doc_path.parent.mkdir(parents=True)
    doc_path.write_text(DOC_TEMPLATE_HEADER + DOC_TABLE_HEADER + "\n".join(rows) + "\n")
    return doc_path


def test_matching_weights_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FND-05: doc weights matching DEFAULT_WEIGHTS -> main() returns 0."""
    monkeypatch.chdir(tmp_path)
    _write_doc(
        tmp_path,
        {
            "RS percentile": "25%",
            "Trend Template": "20%",
            "Pattern": "20%",
            "Volume confirmation": "10%",
            "Earnings momentum": "15%",
            "Catalyst presence": "10%",
        },
    )
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.check_preregistration import main

    assert main() == 0


def test_mismatched_weights_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """FND-05 + D-09: doc weight differs from DEFAULT_WEIGHTS -> main() returns 1
    with formatted 'Weight mismatch:' line."""
    monkeypatch.chdir(tmp_path)
    _write_doc(
        tmp_path,
        {
            "RS percentile": "30%",  # Mismatch -- composite.py says 25%
            "Trend Template": "20%",
            "Pattern": "20%",
            "Volume confirmation": "10%",
            "Earnings momentum": "10%",  # Mismatch -- composite.py says 15%
            "Catalyst presence": "10%",
        },
    )
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.check_preregistration import main

    assert main() == 1
    captured = capsys.readouterr()
    assert "Weight mismatch:" in captured.err
    assert "rs=0.25" in captured.err  # composite.py value
    assert "rs=0.3" in captured.err  # doc value (printed as 0.3 not 0.30)
    assert "earnings=0.15" in captured.err
    assert "earnings=0.1" in captured.err


def test_missing_weight_in_doc_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """FND-05 + REVIEW IN-02: a doc missing one of the 6 weight rows ->
    main() returns 1 (uniform error model) with a stderr message
    naming the missing row.
    """
    monkeypatch.chdir(tmp_path)
    # Write a doc that omits the Catalyst row.
    doc_path = tmp_path / "docs" / "strategy_v1_preregistration.md"
    doc_path.parent.mkdir(parents=True)
    doc_path.write_text(
        DOC_TEMPLATE_HEADER
        + DOC_TABLE_HEADER
        + "| RS percentile (IBD-style)              | 25% | 25% |\n"
        + "| Trend Template (0-8 normalized)        | 20% | 20% |\n"
        + "| Pattern (VCP/flag tightness)           | 20% | 20% |\n"
        + "| Volume confirmation                    | 10% | 10% |\n"
        + "| Earnings momentum (CANSLIM C+A)        | 15% | 15% |\n"
        # No Catalyst row.
    )
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.check_preregistration import main

    assert main() == 1
    captured = capsys.readouterr()
    assert "Catalyst presence" in captured.err
