"""Measured controller regression suite, explicitly not an LLM leaderboard."""
import argparse
import json
from pathlib import Path
import platform
from flightdeck.core import Controller,audit_run
from flightdeck.policies import RulePolicy


def benchmark(cards,out):
    cards,out=Path(cards),Path(out)
    rows=[]
    for case in ("temperature","conformal","svm"):
        for arm in ("strict","rules","negative"):
            spec=cards/case/("negative.json" if arm=="negative" else "manifest.json")
            run=out/f"{case}-{arm}"
            result=Controller(spec,run,RulePolicy(strict=arm=="strict")).run()
            audit_run(run)
            rows.append({"case":case,"arm":arm,"status":result["status"],"value":result["result"]["value"] if result["result"] else None,"metric":result["result"]["metric"] if result["result"] else None,"steps":sum(e["kind"]=="decision" for e in result["events"]),"repairs":sum(e["kind"]=="binding_repair" for e in result["events"]),"seconds":result["elapsed_s"],"report":f"{case}-{arm}/report.html"})
    data={"scope":"Nine deterministic controller runs on three public-data method-transfer demos. Output-contract drift and semantic failures are deliberately injected. No Jev/LLM call; not a scientific benchmark or paper-table reproduction.","python":platform.python_version(),"platform":platform.system(),"runs":rows}
    (out/"benchmark.json").write_text(json.dumps(data,indent=2),encoding="utf-8")
    print(json.dumps(data,indent=2))
    for row in rows:
        expected="verified" if row["arm"]=="rules" or (row["case"]=="svm" and row["arm"]=="strict") else "unresolved"
        if row["status"]!=expected:
            raise AssertionError(f"Unexpected result: {row}")
    return data


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--cards",default="runs/cards");parser.add_argument("--out",default="runs/benchmark");args=parser.parse_args();benchmark(args.cards,args.out)
