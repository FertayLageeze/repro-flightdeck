# Contributing

Please start with one narrowly scoped, redistributable failure case. Include the reviewed source, public data provenance, a frozen verification protocol, expected failure, and a reproducible command. Never add private logs, tokens, customer data or copyrighted full papers without permission.

For policy changes, preserve the same action space and verifier across baselines. Report failures and abstentions. Fixture tests are useful for API contracts but are not live model evaluation.

Run `python -m pytest -q`; for example changes also regenerate the nine-run suite with `examples/prepare.py` and `examples/benchmark.py` in fresh directories. Do not replace checked-in evidence with unexecuted numbers.
