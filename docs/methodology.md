# Methodology and limits

## Trust boundaries

1. A human supplies a reviewed Python entrypoint and input files. Each run copies these into a fresh workspace, hashes them, and saves the protocol and truth outside that workspace.
2. The policy chooses from execute, discover, bind, verify, stop. It cannot change acceptance bounds, seed, training inputs, source code, or metric through this interface. Each run executes at most once. Bindings are limited to observed files/columns, and a scored result ends the action space.
3. The verifier requires an exact one-to-one match between observed and expected sample IDs. Worker-reported labels and headline metrics are ignored. Accuracy uses exact string labels; NLL uses binary labels and strict interior probabilities; RMSE uses finite numbers; interval coverage includes both endpoints.
4. Events form a SHA256 chain. `audit` rechecks original sources, inputs, truth, logs, protocol, chain and scored predictions. This detects accidental edits relative to the saved record, not malicious rewriting of the entire bundle. There is no external signature or trusted timestamp.

**Local execution is trusted execution.** Manifest path containment and environment filtering are useful guardrails, not OS isolation. A malicious script can read files, use the network, spawn descendants or tamper with the controller's files. Subprocess timeout kills the direct worker, not necessarily its descendants; use a container/VM for unfamiliar code. Model credentials are omitted from the child environment, but this cannot stop a malicious program from seeking other local credentials. No raw logs/labels are included in model requests, but task metadata and verifier feedback are. The static report is inert: strings are escaped and displayed as text.

## Public demonstrations

All use data packaged by scikit-learn. Preparation fixes split seeds 1729/1730 and separates train/calibration/test. The worker receives held-out features without held-out labels; labels are used only by the controller's verifier. This is a workflow convention, not filesystem access control.

- **Temperature scaling:** Guo et al. (2017) method transferred to binary optical digits 3/8, logistic regression instead of the paper's neural networks. Fit temperature on calibration logits by bounded scalar optimization of log-temperature in [-3,3]. Clip probabilities to [1e-12,1-1e-12] for finite export. Evaluate held-out binary NLL. This does not establish that calibration improved on held-out data. The artifact path and names are deliberately mismatched.
- **Split conformal:** Absolute-residual split conformal with standardized ridge regression on diabetes; alpha=.1, finite-sample rank ceil((n+1)(1-alpha)). Fixed split of a small dataset, one coverage observation. Its actual coverage is 93/111=83.78%, below nominal. The broad [.8,1] engineering bound is not a statistical coverage guarantee. Interval names are deliberately mismatched.
- **SVM:** Standardized RBF SVC on the optical digits dataset, C=10, gamma='scale'. Measure held-out accuracy. Uses a third-party implementation, no original-paper table claim.

Each method has strict/no-recovery, rule-recovery, and corrupted-result arms. The last arm flips binary probabilities, collapses intervals, or rotates class predictions. These are obvious engineered negative controls, not realistic failure distributions. Rules recognize known aliases, so their success here says nothing about held-out generalization. The suite has three cases and one split, too small for inferential rankings. Acceptance bounds were chosen during development, not preregistered. Runtime values describe this machine/run only.

## What is not evaluated

Live Jev/LLM intelligence, online latency/cost, arbitrary paper interpretation, source patching, environment installation, GPU experiments, general recovery, parameter-search fairness, model confidence calibration and scientific novelty. Adapter tests use fixtures explicitly; no mock result appears in the real CPU demonstration. No cost/accuracy improvement over existing systems is claimed.

## Planned comparison protocol

Before any model comparison, freeze a held-out set of artifact failures with human-reviewed bindings, disjoint from rule development. Compare strict, rules, LLM, Jev, hybrid with the same cases/action limits. Report recovery success, false acceptance, abstention, steps, token usage, wall time and API spend; repeat runs and retain failed attempts. Distinguish verifier reliability from policy intelligence. Statistical summaries should operate on paired cases, not treat actions from one case as independent samples.
