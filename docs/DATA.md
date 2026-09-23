# Demo data attribution

Our code is MIT; that does not relicense upstream data.

## Optical handwritten digits

Alpaydin, E. & Kaynak, C. (1998). **Optical Recognition of Handwritten Digits** [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C50P49.

The [UCI dataset page](https://archive.ics.uci.edu/dataset/80/optical+recognition+of+handwritten+digits) licenses the dataset under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). We access its 1,797-row subset through scikit-learn's `load_digits`. The full auditable temperature example filters digits 3 and 8, relabels them as 0 and 1, assigns local row IDs, splits the rows, casts features to CSV numeric text and removes test labels from the worker input. Generated predictions and other truth excerpts use the same public source. These transformations are ours; the original authors do not endorse this project.

## Diabetes

The demonstration loads the anonymized 442-row regression dataset packaged by scikit-learn's `load_diabetes`. Source and description: [scikit-learn dataset documentation](https://scikit-learn.org/stable/datasets/toy_dataset.html#diabetes-dataset), [Efron et al. Least Angle Regression data](https://hastie.su.domains/Papers/LARS/diabetes.data).

The repository includes held-out target excerpts and derived prediction intervals for inspecting recorded results, not private patient records. Features are generated locally by the example preparation script. See scikit-learn's dataset description for preprocessing and provenance. No medical inference or clinical claim is made.

## Record completeness

`docs/site/temperature-rules` includes the reviewed worker, all input CSVs, truth, generated predictions, logs and hash-chained events; `repro-flightdeck audit docs/site/temperature-rules` can verify it. The other hosted runs include compact evidence (not every source/input); regenerate them using the example commands for full auditing. Rerunning on another operating system can change floating-point last digits, timing and file hashes.
