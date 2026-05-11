"""Compares DEFAULT_WEIGHTS in signals/composite.py to the weights table in
docs/strategy_v1_preregistration.md. Fails CI on mismatch (FND-05, D-09, D-10).

Plain stdlib at module top; the heavier `from screener.signals.composite
import DEFAULT_WEIGHTS` lives inside main() so this script can be invoked
in any environment where pandas is not yet installed (the CI step runs
AFTER `uv sync --frozen --extra dev`, so the import succeeds in CI).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DOC = Path("docs/strategy_v1_preregistration.md")

# Friendly-name -> internal-key mapping. The "Component" column in the doc
# uses these long-form names; the composite scorer uses short keys.
NAME_TO_KEY = {
    "RS percentile": "rs",
    "Trend Template": "trend",
    "Pattern": "pattern",
    "Volume confirmation": "volume",
    "Earnings momentum": "earnings",
    "Catalyst presence": "catalyst",
}


class PreregistrationDocError(RuntimeError):
    """Raised by parse_doc_weights for missing/unreadable preregistration docs.

    REVIEW IN-02: parse_doc_weights used to call sys.exit() directly,
    which made the two error paths (parse vs. mismatch) inconsistent
    (SystemExit vs. int return). Now the parse path raises a typed
    exception and main() converts it to a uniform non-zero int return.
    The __main__ entry point calls sys.exit(main()) per convention.
    """


def parse_doc_weights() -> dict[str, float]:
    """Parse the Frozen Weight column from docs/strategy_v1_preregistration.md.

    Per-row regex captures the rightmost percentage on a row whose first
    cell starts with one of the friendly names. Tolerance: 1e-3.

    Raises PreregistrationDocError on missing weight or unreadable file.
    """
    if not DOC.exists():
        raise PreregistrationDocError(f"Preregistration doc not found: {DOC}")
    text = DOC.read_text(encoding="utf-8")
    out: dict[str, float] = {}
    for friendly, key in NAME_TO_KEY.items():
        # Match: | <friendly>... | <target>% | <frozen>% |
        # The frozen weight is the LAST percentage on the line.
        pattern = (
            rf"\|\s*{re.escape(friendly)}.*?\|\s*\d+%\s*\|"
            rf"\s*(\d+(?:\.\d+)?)%\s*\|"
        )
        m = re.search(pattern, text)
        if m is None:
            raise PreregistrationDocError(
                f"Preregistration doc missing frozen weight for: {friendly}"
            )
        out[key] = float(m.group(1)) / 100.0
    return out


def main() -> int:
    """Compare module weights vs doc weights; return 0 on match, 1 on mismatch.

    FND-05 + D-09 verbatim mismatch line format:
        "Weight mismatch:\\n  composite.py rs=0.30 vs doc rs=0.25\\n  ..."

    REVIEW IN-02: returns a non-zero int on EITHER parse failure OR
    weight mismatch so callers see one uniform error model. The
    __main__ block at the bottom of this file converts the int to a
    process exit code.
    """
    # Lazy heavy import — module top is stdlib only (Pitfall 9).
    from screener.signals.composite import DEFAULT_WEIGHTS

    try:
        doc_weights = parse_doc_weights()
    except PreregistrationDocError as err:
        print(str(err), file=sys.stderr)
        return 1

    # Sum check on parsed weights — must sum to 1.0 +/- 0.005 (Pitfall 11)
    doc_sum = sum(doc_weights.values())
    if abs(doc_sum - 1.0) > 0.005:
        print(
            f"Doc weights do not sum to 100% (got {doc_sum * 100:.1f}%)",
            file=sys.stderr,
        )
        return 1

    diffs: list[str] = []
    for k, w in DEFAULT_WEIGHTS.items():
        dw = doc_weights.get(k)
        if dw is None or abs(w - dw) > 1e-3:
            diffs.append(
                f"composite.py {k}={w:.2f} vs doc {k}={dw}"
            )
    # Bidirectional check (REVIEW CR-02): also detect keys present in the
    # doc table that are NOT in DEFAULT_WEIGHTS. The forward loop above only
    # catches code → doc; this catches doc → code so a renamed/added doc row
    # without a corresponding DEFAULT_WEIGHTS update is surfaced.
    extra_in_doc = set(doc_weights) - set(DEFAULT_WEIGHTS)
    if extra_in_doc:
        diffs.append(
            f"doc has extra keys not in composite.py: {sorted(extra_in_doc)}"
        )
    if diffs:
        print(
            "Weight mismatch:\n  " + "\n  ".join(diffs),
            file=sys.stderr,
        )
        return 1
    print("Preregistration check passed.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
