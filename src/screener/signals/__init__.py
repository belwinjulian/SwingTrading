"""signals — pure-function signal stack; consumes the indicator panel.

Includes minervini (Trend Template), qullamaggie (Setup A scan), canslim
(C+L+M overlay), and composite (the single M2 extension point — takes a
weights dict, emits playbook tag). Imports only `indicators/`, `regime`,
`persistence`, `config`. Never reads OHLCV directly.
"""

# Re-export build_panel so publishers/ (which cannot directly import
# indicators/ per D-16 ALLOWED) can access it via `from screener.signals
# import build_panel`. signals/ is allowed to import from indicators/.
from screener.indicators import build_panel

__all__ = ["build_panel"]
