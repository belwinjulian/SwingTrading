"""signals — pure-function signal stack; consumes the indicator panel.

Includes minervini (Trend Template), qullamaggie (Setup A scan), canslim
(C+L+M overlay), and composite (the single M2 extension point — takes a
weights dict, emits playbook tag). Imports only `indicators/`, `regime`,
`persistence`, `config`. Never reads OHLCV directly.
"""
