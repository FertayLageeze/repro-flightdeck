"""Reviewed CPU experiments on sklearn's packaged datasets.

These are method-transfer demonstrations, not original-paper table replications.
The export path/column drift is deliberately injected to test contract recovery.
"""
import csv
import json
from pathlib import Path
import sys
import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import expit
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC


def read(name, target=True):
    with open(name, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    features = sorted((key for key in rows[0] if key.startswith("x")), key=lambda k:int(k[1:]))
    x = np.array([[float(row[key]) for key in features] for row in rows])
    y = np.array([float(row["target"]) for row in rows]) if target else None
    return x, y, [row["id"] for row in rows]


def main(case, broken=False):
    x, y, _ = read("train.csv")
    xt, _, ids = read("test.csv", target=False)
    if case == "temperature":
        xc, yc, _ = read("calibration.csv")
        model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, C=1))
        model.fit(x, y)
        zc, zt = model.decision_function(xc), model.decision_function(xt)
        def loss(log_t):
            z = zc / np.exp(log_t)
            return float(np.mean(np.logaddexp(0, z) - yc*z))
        optimum = minimize_scalar(loss, bounds=(-3, 3), method="bounded", options={"xatol":1e-8})
        p = np.clip(expit(zt / np.exp(optimum.x)), 1e-12, 1-1e-12)
        if broken:
            p = 1-p
        path, fields = Path("exports/calibrated.csv"), ["sample_id", "positive_probability"]
        rows = zip(ids, map(float, p))
        extra = {"temperature":float(np.exp(optimum.x)), "fit_split":"calibration only", "calibration_nll":loss(optimum.x), "uncalibrated_calibration_nll":loss(0)}
    elif case == "conformal":
        xc, yc, _ = read("calibration.csv")
        model = make_pipeline(StandardScaler(), Ridge(alpha=10))
        model.fit(x,y)
        residuals=np.abs(yc-model.predict(xc))
        alpha=.1
        rank=int(np.ceil((len(residuals)+1)*(1-alpha)))
        q=float(np.sort(residuals)[rank-1]) if rank<=len(residuals) else float('inf')
        prediction=model.predict(xt)
        if broken:
            q=0
        path,fields=Path("intervals.csv"),["id","interval_low","interval_high"]
        rows=zip(ids,map(float,prediction-q),map(float,prediction+q))
        extra={"alpha":alpha,"finite_sample_rank":rank,"calibration_n":len(residuals),"radius":q}
    elif case == "svm":
        model=make_pipeline(StandardScaler(), SVC(C=10,gamma="scale"))
        model.fit(x,y)
        predictions=model.predict(xt).astype(int)
        if broken:
            predictions=(predictions+1)%10
        path,fields=Path("predictions.csv"),["id","prediction"]
        rows=zip(ids,map(int,predictions))
        extra={"kernel":"rbf","C":10,"gamma":"scale"}
    else:
        raise ValueError("Unknown reviewed experiment")
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.writer(handle);writer.writerow(fields);writer.writerows(rows)
    Path("fit.json").write_text(json.dumps(extra,indent=2),encoding="utf-8")
    print(json.dumps({"artifact":path.as_posix(),"rows":len(ids),"injected_semantic_failure":broken}))


if __name__=="__main__":
    main(sys.argv[1], "--broken" in sys.argv[2:])
