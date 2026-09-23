# Research notes · 2026-09-23

This is a source-grounded design note, not a novelty or performance claim.

## Jev: a bounded decision backend

TypeSafe AI announced Jev on September 15, 2026. Its official API takes a state plus typed questions and returns structured decisions. The Choice primitive returns a selected key, distribution and confidence. We use a single bounded action question, validate the entire distribution, and abstain or call a local LLM below a configurable threshold. That threshold has not been calibrated on our task. Structured answers can still be semantically wrong; the independent verifier remains responsible for acceptance.

Sources: [launch announcement](https://typesafe.ai/blog/introducing-system-one-models-and-jev), [official introduction](https://docs.typesafe.ai/introduction), [HTTP contract](https://docs.typesafe.ai/api). Endpoint/response fixture implementation was checked against these docs. No model weights, training recipe, vendor performance claims or brand affiliation are implied by this integration.

## FDE: a delivery perspective, with acronym ambiguity

The relevant primary sources we found use FDE as Forward Deployed Engineering / Engineer. [Palantir AI FDE](https://www.palantir.com/docs/foundry/ai-fde/overview) describes an agent operating its platform. A recent author-hosted [post-training delivery benchmark](https://junfei-z.github.io/fde/) separates successful execution from delivering useful behavior. Its page labels the work as under review; its numerical findings are not independently validated here.

There are other FDE expansions and methods. We have not identified a unique recent algorithm from the abbreviation alone. Flightdeck adopts the delivery-and-acceptance framing; it does not claim to implement that benchmark or reproduce its results.

## Existing work and our small starting point

- [PaperBench](https://github.com/openai/frontier-evals/blob/main/project/paperbench/README.md) evaluates research replication through agent rollout, execution and rubric-based grading. Flightdeck does not implement its tasks or use its name for our small demo suite.
- [AI Scientist-v2](https://github.com/SakanaAI/AI-Scientist-v2) is an end-to-end autonomous research system. Flightdeck v0.1 does not generate hypotheses or papers.
- [AgentRx](https://github.com/microsoft/AgentRx) diagnoses failure steps using trajectory constraints. Flightdeck's current recovery is much narrower: output artifact bindings.
- [LangGraph checkpointing](https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/checkpointers.mdx) already supports persistence and replay. An HTML timeline alone is not a new research method.

The hypothesis worth testing is whether a typed decision backend can recover experiment output contracts under fixed verification and cost constraints. We currently provide the controller, independently recomputed metrics, a rule baseline, and an inspectable replay. A held-out benchmark and actual model runs are still required.
