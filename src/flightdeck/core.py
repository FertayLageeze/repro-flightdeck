"""Small, auditable controller. Policies propose; independent code verifies."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone


class ContractError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def contained(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ContractError("Expected a relative path")
    path = (Path(root) / relative).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ContractError("Path escapes experiment workspace")
    return path


def finite(value):
    if isinstance(value, bool):
        raise ContractError("Booleans are not numeric measurements")
    try:
        number = float(value)
    except (ValueError, TypeError) as exc:
        raise ContractError("Measurement is not numeric") from exc
    if not math.isfinite(number):
        raise ContractError("Measurement is not finite")
    return number


def read_csv(path):
    if path.stat().st_size > 10_000_000:
        raise ContractError("CSV exceeds the 10 MB artifact limit")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        if not fields or len(set(fields)) != len(fields):
            raise ContractError("CSV header is empty or duplicated")
        rows = list(reader)
    if not rows or any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ContractError("CSV is empty or ragged")
    return fields, rows


def load_manifest(path):
    path = Path(path).resolve()
    value = json.loads(path.read_text(encoding="utf-8"))
    required = {"id", "title", "scope", "source", "command", "inputs", "truth", "metric", "acceptance", "artifact"}
    if not isinstance(value, dict) or required - value.keys():
        raise ContractError("Manifest lacks required fields")
    if not isinstance(value["command"], list) or not value["command"] or any(not isinstance(s, str) for s in value["command"]):
        raise ContractError("command must be an argv string array")
    if value["command"][0] != "{python}":
        raise ContractError("This release executes reviewed Python entrypoints only")
    if len(value["command"]) < 2 or value["command"][1].startswith("-"):
        raise ContractError("Use a Python script, not -c or -m")
    if not isinstance(value["inputs"], list) or not value["inputs"]:
        raise ContractError("List the complete reviewed input files")
    for name in value["inputs"]:
        if not contained(path.parent, name).is_file():
            raise ContractError(f"Input missing: {name}")
    if value["command"][1] not in value["inputs"]:
        raise ContractError("Entrypoint must be included in inputs")
    truth = contained(path.parent, value["truth"])
    if not truth.is_file():
        raise ContractError("Frozen truth file is missing")
    if value["metric"] not in {"accuracy", "nll", "coverage", "rmse"}:
        raise ContractError("Unknown metric")
    low, high = (finite(value["acceptance"][key]) for key in ("min", "max"))
    if low > high:
        raise ContractError("Acceptance interval is reversed")
    if not isinstance(value["artifact"], dict) or not isinstance(value["artifact"].get("columns"), dict):
        raise ContractError("artifact requires a columns map")
    contained(path.parent, value["artifact"]["path"])
    timeout = finite(value.get("timeout_seconds", 60))
    if not 0 < timeout <= 600:
        raise ContractError("timeout_seconds must be in (0, 600]")
    return path, value


def verify_predictions(truth_file, artifact_file, columns, metric, acceptance):
    """Recompute from frozen labels. Never trust a worker's reported metric/labels."""
    _, truth = read_csv(truth_file)
    fields, observed = read_csv(artifact_file)
    roles = {"id", "prediction"} if metric in {"accuracy", "rmse"} else ({"id", "probability"} if metric == "nll" else {"id", "lower", "upper"})
    if set(columns) != roles or any(c not in fields for c in columns.values()) or len(set(columns.values())) != len(columns):
        raise ContractError("Artifact columns do not match the metric contract")
    if any("id" not in row or "target" not in row for row in truth):
        raise ContractError("Truth must have id,target")
    expected = {row["id"]: row["target"] for row in truth}
    predictions = {row[columns["id"]]: row for row in observed}
    if "" in expected or "" in predictions or len(expected) != len(truth) or len(predictions) != len(observed):
        raise ContractError("Sample identifiers are empty or duplicated")
    if set(expected) != set(predictions):
        raise ContractError("Missing or extra sample IDs; partial results cannot pass")
    values = []
    for sample, target in expected.items():
        row = predictions[sample]
        if metric == "accuracy":
            values.append(float(row[columns["prediction"]] == target))
        elif metric == "rmse":
            values.append((finite(row[columns["prediction"]]) - finite(target)) ** 2)
        elif metric == "nll":
            p, y = finite(row[columns["probability"]]), finite(target)
            if not 0 < p < 1 or y not in (0, 1):
                raise ContractError("NLL needs binary targets and probabilities strictly inside (0,1)")
            values.append(-math.log(p if y == 1 else 1 - p))
        else:
            lo, hi, y = finite(row[columns["lower"]]), finite(row[columns["upper"]]), finite(target)
            if lo > hi:
                raise ContractError("Prediction interval is reversed")
            values.append(float(lo <= y <= hi))
    value = math.fsum(values) / len(values)
    if metric == "rmse":
        value = math.sqrt(value)
    finite(value)
    return {"metric": metric, "value": value, "n": len(values), "acceptance": acceptance,
            "passed": finite(acceptance["min"]) <= value <= finite(acceptance["max"]),
            "truth_sha256": digest(truth_file), "artifact_sha256": digest(artifact_file)}


class Controller:
    """Local trusted-code runner, not a security sandbox."""
    def __init__(self, manifest, out, policy, max_steps=10):
        self.path, self.spec = load_manifest(manifest)
        self.out = Path(out).resolve()
        if self.out.exists():
            raise ContractError("Run output already exists; use a fresh directory")
        if not 1 <= max_steps <= 100:
            raise ContractError("max_steps must be between 1 and 100")
        self.out.mkdir(parents=True)
        self.work = self.out / "workspace"
        self.work.mkdir()
        self.hashes = {}
        for name in self.spec["inputs"]:
            source = contained(self.path.parent, name)
            target = contained(self.work, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            self.hashes[name] = digest(target)
        shutil.copyfile(contained(self.path.parent, self.spec["truth"]), self.out / "truth.csv")
        self.truth_hash = digest(self.out / "truth.csv")
        (self.out / "manifest.json").write_text(json.dumps(self.spec, indent=2), encoding="utf-8")
        self.spec_hash = hashlib.sha256(canonical(self.spec).encode()).hexdigest()
        self.policy, self.max_steps = policy, max_steps
        self.events, self.candidates = [], []
        self.executed, self.exit_code, self.result = False, None, None
        self.artifact = json.loads(json.dumps(self.spec["artifact"]))
        self.failure = None
        self.last_hash = "0" * 64
        self.status = "running"
        self.start = time.monotonic()
        self.event("intake", {"protocol_sha256": self.spec_hash, "inputs": self.hashes, "truth_sha256": self.truth_hash})

    def event(self, kind, data):
        entry = {"seq": len(self.events), "kind": kind, "elapsed_s": round(time.monotonic() - self.start, 4), "data": data, "previous": self.last_hash}
        entry["sha256"] = hashlib.sha256(canonical(entry).encode()).hexdigest()
        self.last_hash = entry["sha256"]
        self.events.append(entry)
        with (self.out / "trace.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(canonical(entry) + "\n")

    def intact(self):
        if digest(self.out / "truth.csv") != self.truth_hash:
            raise ContractError("Frozen truth changed")
        saved = json.loads((self.out / "manifest.json").read_text(encoding="utf-8"))
        if hashlib.sha256(canonical(saved).encode()).hexdigest() != self.spec_hash:
            raise ContractError("Frozen protocol changed")
        for name, original in self.hashes.items():
            if digest(contained(self.work, name)) != original:
                raise ContractError(f"Reviewed source/input changed: {name}")

    def observation(self):
        return {"task": self.spec["title"], "metric": self.spec["metric"], "executed": self.executed,
                "exit_code": self.exit_code, "artifact": self.artifact, "failure": self.failure,
                "candidates": self.candidates, "verification": self.result,
                "allowed_actions": ["execute", "discover", "bind", "verify", "stop"],
                "constraint": "Only repair artifact path/column bindings. Never change data, program, metric, acceptance, or claim success without verification."}

    def execute(self):
        if self.executed:
            raise ContractError("Experiment execution already consumed; no silent reruns")
        self.executed = True
        argv = [sys.executable, *self.spec["command"][1:]]
        allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE", "LANG"}
        env = {k: v for k, v in os.environ.items() if k.upper() in allowed}
        env.update({"PYTHONUTF8": "1", "PYTHONNOUSERSITE": "1", "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
        try:
            with (self.out / "stdout.txt").open("w", encoding="utf-8") as stdout, (self.out / "stderr.txt").open("w", encoding="utf-8") as stderr:
                done = subprocess.run(argv, cwd=self.work, env=env, stdout=stdout, stderr=stderr,
                                      timeout=self.spec.get("timeout_seconds", 60), check=False, shell=False)
            self.exit_code = done.returncode
        except subprocess.TimeoutExpired:
            self.exit_code = -1
            self.failure = "Execution timeout; no retry permitted in this run"
        self.intact()
        if self.exit_code != 0:
            self.failure = "Execution failed; inspect stderr.txt locally"
        self.event("execution", {"argv": self.spec["command"], "exit_code": self.exit_code,
                                 "stdout_sha256": digest(self.out / "stdout.txt"), "stderr_sha256": digest(self.out / "stderr.txt")})

    def discover(self):
        if not self.executed or self.exit_code != 0:
            raise ContractError("Artifact discovery requires a successful execution")
        candidates = []
        for path in sorted(self.work.rglob("*.csv")):
            relative = path.relative_to(self.work).as_posix()
            if relative in self.hashes or path.is_symlink():
                continue
            path = contained(self.work, relative)
            try:
                fields, rows = read_csv(path)
            except (ContractError, UnicodeError):
                continue
            candidates.append({"path": relative, "columns": fields, "rows": len(rows)})
            if len(candidates) >= 25:
                break
        self.candidates = candidates
        self.event("discovery", {"candidates": candidates})

    def bind(self, action):
        if self.result is not None:
            raise ContractError("A scored result cannot be rebound; stop and report it")
        candidate = next((x for x in self.candidates if x["path"] == action.get("path")), None)
        columns = action.get("columns")
        if candidate is None or not isinstance(columns, dict) or any(v not in candidate["columns"] for v in columns.values()):
            raise ContractError("Bindings must refer to an observed CSV and observed columns")
        old = self.artifact
        self.artifact = {"path": candidate["path"], "columns": columns}
        self.failure = None
        self.event("binding_repair", {"before": old, "after": self.artifact})

    def verify(self):
        if not self.executed or self.exit_code != 0:
            raise ContractError("A failed/unexecuted experiment cannot pass")
        self.intact()
        artifact = contained(self.work, self.artifact["path"])
        self.result = verify_predictions(self.out / "truth.csv", artifact, self.artifact["columns"], self.spec["metric"], self.spec["acceptance"])
        self.failure = None
        self.event("verification", self.result)

    def run(self):
        for step in range(self.max_steps):
            try:
                self.intact()
                action, meta = self.policy.decide(self.observation())
                self.event("decision", {"step": step, "action": action, "policy": meta})
                if not isinstance(action, dict):
                    raise ContractError("Decision is not an object")
                name = action.get("action")
                if name == "stop":
                    self.status = "verified" if self.result and self.result["passed"] else "unresolved"
                    break
                if name == "execute":
                    self.execute()
                elif name == "discover":
                    self.discover()
                elif name == "bind":
                    self.bind(action)
                elif name == "verify":
                    self.verify()
                else:
                    raise ContractError("Unsupported action; no shell or protocol-edit action exists")
            except Exception as exc:
                message = str(exc)
                for local, label in ((self.out, "$RUN"), (self.path.parent, "$CARD")):
                    # OSError renders Windows filenames with repr-style doubled slashes.
                    for spelling in (str(local).replace("\\", "\\\\"), str(local), local.as_posix()):
                        message = message.replace(spelling, label)
                self.failure = f"{type(exc).__name__}: {message[:400]}"
                self.event("failure", {"message": self.failure})
                if "Frozen" in self.failure or "Reviewed source" in self.failure:
                    self.status = "integrity_failed"
                    break
        else:
            self.status = "budget_exhausted"
        summary = {"schema_version": 1, "id": self.spec["id"], "title": self.spec["title"],
                   "scope": self.spec["scope"], "source": self.spec["source"], "status": self.status,
                   "policy": self.policy.name, "created_utc": datetime.now(timezone.utc).isoformat(),
                   "result": self.result, "failure": self.failure, "binding": self.artifact,
                   "protocol_sha256": self.spec_hash, "trace_head": self.last_hash,
                   "elapsed_s": round(time.monotonic() - self.start, 4), "events": self.events}
        (self.out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        from .report import render
        render(summary, self.out / "report.html")
        return summary


def audit_run(directory):
    directory = Path(directory)
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    events = [json.loads(line) for line in (directory / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
    previous = "0" * 64
    for seq, original in enumerate(events):
        entry = dict(original)
        claimed = entry.pop("sha256")
        if entry["seq"] != seq or entry["previous"] != previous or hashlib.sha256(canonical(entry).encode()).hexdigest() != claimed:
            raise ContractError("Trace chain mismatch")
        previous = claimed
    if not events or summary["trace_head"] != previous or summary["events"] != events:
        raise ContractError("Summary/trace mismatch")
    intake = events[0]["data"]
    spec = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if hashlib.sha256(canonical(spec).encode()).hexdigest() != intake["protocol_sha256"] or digest(directory / "truth.csv") != intake["truth_sha256"]:
        raise ContractError("Protocol/truth integrity mismatch")
    for relative, sha in intake["inputs"].items():
        if digest(contained(directory / "workspace", relative)) != sha:
            raise ContractError("Source/input integrity mismatch")
    for event in events:
        if event["kind"] == "execution":
            for stream in ("stdout", "stderr"):
                if digest(directory / f"{stream}.txt") != event["data"][f"{stream}_sha256"]:
                    raise ContractError("Execution log integrity mismatch")
    if summary["result"] is not None:
        verifications = [e["data"] for e in events if e["kind"] == "verification"]
        if not verifications or verifications[-1] != summary["result"]:
            raise ContractError("Summary lacks matching verification event")
        actual = verify_predictions(directory / "truth.csv", contained(directory / "workspace", summary["binding"]["path"]), summary["binding"]["columns"], spec["metric"], spec["acceptance"])
        if actual != summary["result"]:
            raise ContractError("Independent verification differs from saved result")
    if summary["status"] == "verified" and not (summary["result"] and summary["result"]["passed"]):
        raise ContractError("Unsupported success claim")
    return {"integrity": "valid", "status": summary["status"], "events": len(events), "trace_head": previous}
