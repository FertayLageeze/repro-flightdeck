"""Build public-data experiment cards. No network calls and no model calls."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np
import sklearn
from sklearn.datasets import load_digits,load_diabetes
from sklearn.model_selection import train_test_split


def write(path,x,y,ids,labels=True):
    with path.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.writer(handle)
        writer.writerow(["id"]+[f"x{i}" for i in range(x.shape[1])]+(["target"] if labels else []))
        for sample,features,target in zip(ids,x,y):
            writer.writerow([str(sample)]+list(map(float,features))+([str(target)] if labels else []))


def prepare(out):
    out=Path(out).resolve()
    if out.exists():
        raise ValueError("Use a new card directory to preserve previous protocols")
    out.mkdir(parents=True)
    definitions={
        "temperature":("Temperature scaling · binary digits", "https://proceedings.mlr.press/v70/guo17a.html", "nll", {"min":0,"max":0.35}, {"path":"probabilities.csv","columns":{"id":"id","probability":"probability"}}),
        "conformal":("Split conformal · diabetes regression", "https://arxiv.org/abs/2107.07511", "coverage", {"min":0.80,"max":1.0}, {"path":"intervals.csv","columns":{"id":"id","lower":"lower","upper":"upper"}}),
        "svm":("RBF SVM · handwritten digits", "https://doi.org/10.1007/BF00994018", "accuracy", {"min":0.90,"max":1.0}, {"path":"predictions.csv","columns":{"id":"id","prediction":"prediction"}})}
    for case,(title,source,metric,acceptance,artifact) in definitions.items():
        data=load_diabetes() if case=="conformal" else load_digits()
        x,y=data.data,data.target
        if case=="temperature":
            mask=(y==3)|(y==8);x,y=x[mask],(y[mask]==8).astype(int)
        ids=np.arange(len(y));stratify=None if case=="conformal" else y
        train,test=train_test_split(ids,test_size=.25,random_state=1729,stratify=stratify)
        train,cal=train_test_split(train,test_size=1/3,random_state=1730,stratify=None if case=="conformal" else y[train])
        folder=out/case;folder.mkdir()
        for split,indices in [("train",train),("calibration",cal),("test",test)]:
            write(folder/f"{split}.csv",x[indices],y[indices],indices,split!="test")
        with (folder/"truth.csv").open("w",newline="",encoding="utf-8") as handle:
            writer=csv.writer(handle);writer.writerow(["id","target"]);writer.writerows(zip(map(str,test),map(str,y[test])))
        shutil.copyfile(Path(__file__).with_name("experiment.py"),folder/"experiment.py")
        manifest={"id":case,"title":title,"scope":"Method-transfer demo on a different small dataset; not a replication of the cited paper's reported tables. Artifact path/column drift is intentionally injected. Acceptance bounds are this demo's engineering checks, not paper claims.","source":source,
                  "command":["{python}","experiment.py",case],"inputs":["experiment.py","train.csv","calibration.csv","test.csv"],"truth":"truth.csv","metric":metric,"acceptance":acceptance,"artifact":artifact,"timeout_seconds":120,
                  "dataset": "sklearn packaged diabetes" if case=="conformal" else "sklearn packaged UCI optical digits", "versions":{"numpy":np.__version__,"sklearn":sklearn.__version__},"split_seeds":[1729,1730],"split_sizes":{"train":len(train),"calibration":len(cal),"test":len(test)}}
        (folder/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
        negative=dict(manifest);negative["id"]=case+"-negative";negative["title"]=title+" · injected wrong output";negative["command"]=manifest["command"]+["--broken"]
        (folder/"negative.json").write_text(json.dumps(negative,indent=2),encoding="utf-8")
    print(out)
    return out


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--out",default="runs/cards");args=parser.parse_args();prepare(args.out)
