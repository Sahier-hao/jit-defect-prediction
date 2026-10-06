"""Fixed, auditable baseline. Feature and label construction remain upstream."""

import platform
from dataclasses import dataclass

import numpy as np
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .data import FEATURES, CommitRecord
from .preparation import _time
from .temporal_audit import audit_temporal

SEED = 42


def temporal_split(records: list[CommitRecord], train_ratio=0.7):
    if not 0 < train_ratio < 1:
        raise ValueError("train_ratio must be between 0 and 1")
    ordered = sorted(records, key=lambda row: (row.committed_at, row.commit_id))
    candidates = [
        index
        for index in range(1, len(ordered))
        if ordered[index - 1].committed_at < ordered[index].committed_at
    ]
    if not candidates:
        raise ValueError(
            "At least two distinct timestamps are required for temporal splitting"
        )
    boundary = min(
        candidates, key=lambda index: (abs(index - len(ordered) * train_ratio), index)
    )
    return ordered[:boundary], ordered[boundary:]


def evaluate(labels, probabilities, costs, ids):
    labels, scores = (
        np.asarray(labels, dtype=int),
        np.asarray(probabilities, dtype=float),
    )
    effort = np.maximum(1.0, np.asarray(costs, dtype=float))
    if not len(labels) or not (len(labels) == len(scores) == len(effort) == len(ids)):
        raise ValueError("Evaluation inputs must have equal, nonzero lengths")
    if (
        not np.isin(labels, [0, 1]).all()
        or not np.isfinite(scores).all()
        or ((scores < 0) | (scores > 1)).any()
    ):
        raise ValueError(
            "Evaluation requires binary labels and finite probabilities between 0 and 1"
        )
    if not np.isfinite(effort).all():
        raise ValueError("Evaluation costs must be finite")
    decisions = scores >= 0.5
    notes = {}
    report = {
        "precision": float(precision_score(labels, decisions, zero_division=0)),
        "recall": float(recall_score(labels, decisions, zero_division=0)),
        "f1": float(f1_score(labels, decisions, zero_division=0)),
        "roc_auc": None,
        "recall_at_20_effort": None,
        "popt": None,
        "test_count": len(labels),
        "positive_count": int(labels.sum()),
        "decision_threshold": 0.5,
        "effort_total": float(effort.sum()),
        "effort_budget": 0.2,
        "inspected_commits": 0,
        "notes": notes,
    }
    if len(np.unique(labels)) == 2:
        report["roc_auc"] = float(roc_auc_score(labels, scores))
    else:
        notes["roc_auc"] = "ROC-AUC is undefined for a one-class test set"
    model_order = sorted(
        range(len(labels)),
        key=lambda index: (-scores[index] / effort[index], ids[index]),
    )
    spent, found = 0.0, 0
    for index in model_order:
        if spent + effort[index] > 0.2 * effort.sum() + 1e-12:
            break
        spent += effort[index]
        found += int(labels[index])
        report["inspected_commits"] += 1
    report["effort_spent"] = spent
    positives = int(labels.sum())
    if not positives:
        notes["recall_at_20_effort"] = "No positive test labels"
        notes["popt"] = "No positive test labels"
        return report
    report["recall_at_20_effort"] = found / positives

    def area(order):
        x = np.r_[0, np.cumsum(effort[order]) / effort.sum()]
        y = np.r_[0, np.cumsum(labels[order]) / positives]
        return float(np.trapezoid(y, x))

    best = sorted(
        range(len(labels)),
        key=lambda index: (-labels[index] / effort[index], ids[index]),
    )
    worst = sorted(
        range(len(labels)),
        key=lambda index: (labels[index] / effort[index], ids[index]),
    )
    best_area, worst_area, model_area = area(best), area(worst), area(model_order)
    report["curve_areas"] = {
        "model": model_area,
        "oracle": best_area,
        "worst": worst_area,
    }
    if abs(best_area - worst_area) < 1e-12:
        notes["popt"] = "Oracle and worst curve areas are identical"
    else:
        report["popt"] = float(
            np.clip(1 - (best_area - model_area) / (best_area - worst_area), 0, 1)
        )
    return report


@dataclass
class TrainedBaseline:
    pipeline: Pipeline
    metadata: dict
    metrics: dict
    predictions: list[dict]
    test_predictions: list[dict]


def _check_sample_gate(eligible, is_demo):
    minimum = 20 if is_demo else 1000
    if len(eligible) < minimum or (
        not is_demo and sum(row.label == 1 for row in eligible) < 50
    ):
        raise ValueError(
            f"Requires at least {minimum} eligible commits"
            + ("" if is_demo else " and 50 positive labels")
            + "; unknown labels are excluded"
        )


def fit_baseline(records: list[CommitRecord], *, is_demo=False) -> TrainedBaseline:
    eligible = [row for row in records if row.label is not None]
    _check_sample_gate(eligible, is_demo)
    if not is_demo:
        raise ValueError(
            "Non-demo training requires a temporal contract; use fit_temporal_baseline"
        )
    train, test = temporal_split(eligible)
    result = _fit_partitions(records, train, test)
    result.metadata.update(
        label_availability_checked=False, label_time_policy="unchecked_synthetic_only"
    )
    return result


def fit_temporal_baseline(
    csv: bytes, contract: bytes, *, is_demo=False
) -> TrainedBaseline:
    """Fit only internally audited cohorts; supplied provenance still needs review."""
    audit = audit_temporal(csv, contract)
    admitted = list(audit.train + audit.test)
    _check_sample_gate(admitted, is_demo)
    if not audit.test:
        raise ValueError("Audited test cohort must not be empty")
    result = _fit_partitions(
        admitted,
        audit.train,
        audit.test,
        split_at=_time(audit.report["config"]["trainCutoff"]),
    )
    result.metadata.update(
        train_ratio_requested=None,
        excluded_unknown=sum(row.label is None for row in audit.records),
        excluded_temporal_total=audit.report["quality"]["excluded"],
        label_availability_checked=True,
        label_time_policy=audit.report["policyVersion"],
        temporal_audit=audit.report,
    )
    return result


def _fit_partitions(records, train, test, *, split_at=None) -> TrainedBaseline:
    eligible = [row for row in records if row.label is not None]
    if len({row.label for row in train}) != 2:
        raise ValueError("Training partition must contain both classes")
    x_train = np.asarray([[row.features[name] for name in FEATURES] for row in train])
    pipeline = Pipeline(
        [
            ("scale", StandardScaler()),
            ("classifier", LogisticRegression(C=1.0, max_iter=1000, random_state=SEED)),
        ]
    )
    pipeline.fit(x_train, [row.label for row in train])
    split_at = split_at or test[0].committed_at
    all_scores = pipeline.predict_proba(
        np.asarray([[row.features[name] for name in FEATURES] for row in records])
    )[:, 1]
    predictions = [
        {
            "commit_id": row.commit_id,
            "probability": float(score),
            "label": row.label,
            "effort": max(1, row.features["la"] + row.features["ld"]),
            "scope": "training" if row.committed_at < split_at else "holdout",
        }
        for row, score in zip(records, all_scores, strict=True)
    ]
    test_ids = {row.commit_id for row in test}
    test_predictions = [item for item in predictions if item["commit_id"] in test_ids]
    metrics = evaluate(
        [item["label"] for item in test_predictions],
        [item["probability"] for item in test_predictions],
        [item["effort"] for item in test_predictions],
        [item["commit_id"] for item in test_predictions],
    )
    metadata = {
        "algorithm": "standard_scaler_logistic_regression",
        "feature_order": list(FEATURES),
        "seed": SEED,
        "parameters": {"C": 1.0, "max_iter": 1000},
        "train_ratio_requested": 0.7,
        "train_count": len(train),
        "test_count": len(test),
        "excluded_unknown": len(records) - len(eligible),
        "train_window": {
            "start": train[0].committed_at.isoformat(),
            "end": train[-1].committed_at.isoformat(),
        },
        "test_window": {
            "start": test[0].committed_at.isoformat(),
            "end": test[-1].committed_at.isoformat(),
        },
        "split_at": split_at.isoformat(),
        "versions": {
            "python": platform.python_version(),
            "sklearn": sklearn.__version__,
            "numpy": np.__version__,
        },
        "risk_thresholds": {"high": 0.7, "low": 0.3},
        "metric_policy": "effort=max(1,LA+LD); score/effort order; commit-ID ties; whole-commit prefix at 20%; full-curve trapezoidal Popt",
    }
    return TrainedBaseline(pipeline, metadata, metrics, predictions, test_predictions)


def explain(pipeline, features):
    vector = np.asarray([[features[name] for name in FEATURES]])
    scaled = pipeline.named_steps["scale"].transform(vector)[0]
    coefficients = pipeline.named_steps["classifier"].coef_[0]
    contributions = [
        {
            "feature": name,
            "value": float(features[name]),
            "contribution": float(scaled[index] * coefficients[index]),
            "direction": "raises"
            if scaled[index] * coefficients[index] > 0
            else "lowers"
            if scaled[index] * coefficients[index] < 0
            else "neutral",
        }
        for index, name in enumerate(FEATURES)
    ]
    contributions.sort(key=lambda item: (-abs(item["contribution"]), item["feature"]))
    return {
        "method": "linear_log_odds",
        "unit": "log_odds",
        "baseline": float(pipeline.named_steps["classifier"].intercept_[0]),
        "probability": float(pipeline.predict_proba(vector)[0, 1]),
        "contributions": contributions,
    }
