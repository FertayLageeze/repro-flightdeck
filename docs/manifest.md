# Experiment-card contract

Use a directory containing your reviewed script, input data, frozen labels, and this JSON. `examples/prepare.py` writes three working cards.

```json
{
  "id": "my-experiment",
  "title": "My reviewed classifier",
  "scope": "State exactly which claim and dataset are being checked",
  "source": "https://example.org/paper-or-protocol",
  "command": ["{python}", "experiment.py"],
  "inputs": ["experiment.py", "train.csv", "test.csv"],
  "truth": "truth.csv",
  "metric": "accuracy",
  "acceptance": {"min": 0.9, "max": 1.0},
  "artifact": {
    "path": "predictions.csv",
    "columns": {"id": "sample_id", "prediction": "label"}
  },
  "timeout_seconds": 60
}
```

`truth.csv` contains unique nonempty `id,target` columns. IDs are matched exactly, with no trimming or coercion; prediction order does not matter. Accuracy labels compare strings (`1` differs from `1.0`). Every expected sample must be present exactly once, with no extras.

Metric column roles:

| Metric | Required roles | Value |
|---|---|---|
| accuracy | id, prediction | fraction matching frozen labels |
| nll | id, probability | mean natural-log binary negative log likelihood |
| rmse | id, prediction | square root of mean squared error |
| coverage | id, lower, upper | fraction inside inclusive intervals |

Acceptance is an inclusive finite interval. Probability exports must be strictly inside (0,1); clip explicitly in reviewed experiment code if needed. Input/ground-truth files are copied and hashed; output directories cannot be reused. Relative paths must remain inside the card/workspace. The current command contract is `{python}` plus a script filename and arguments; shell strings, `-c`, `-m`, automatic installations, arbitrary commands and source patches are unsupported.

The policy sees discovered schemas and may propose a new binding. It cannot mutate the command or acceptance through the action API. Once a valid metric is scored, the action space becomes stop-only, preventing repeated output selection until something passes. The simple baseline stops if multiple alias-compatible candidates exist. Policies may still select semantically wrong files/columns before scoring; a passing threshold is not proof of correspondence to the intended experiment. Human review of bindings remains necessary.

CLI exit codes: 0 verified, 1 unresolved/budget exhausted/integrity failure, 2 configuration or invocation error. `audit` returning 0 means the saved bundle is consistent, even if the scientific result is unresolved; inspect its `status` field.
