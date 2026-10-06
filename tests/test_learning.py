import math

import numpy as np
import pytest
from conftest import FEATURES, csv_bytes


def test_temporal_split_keeps_timestamp_ties_together():
    from jit_defect.data import parse_csv
    from jit_defect.learning import temporal_split

    records = parse_csv(
        csv_bytes(
            20,
            mutate=lambda rows: [
                row.update(committed_at=rows[13]["committed_at"]) for row in rows[12:16]
            ],
        )
    )
    train, test = temporal_split(records)
    assert max(row.committed_at for row in train) < min(
        row.committed_at for row in test
    )
    assert len(train) + len(test) == 20


def test_temporal_split_rejects_one_timestamp():
    from jit_defect.data import parse_csv
    from jit_defect.learning import temporal_split

    records = parse_csv(
        csv_bytes(
            20,
            mutate=lambda rows: [
                row.update(committed_at=rows[0]["committed_at"]) for row in rows
            ],
        )
    )
    with pytest.raises(ValueError, match="timestamp"):
        temporal_split(records)


def test_fit_excludes_unknown_and_scaler_sees_training_only():
    from jit_defect.data import parse_csv
    from jit_defect.learning import fit_baseline, temporal_split

    records = parse_csv(
        csv_bytes(80, mutate=lambda rows: rows[-1].update(label="unknown", la=999999))
    )
    result = fit_baseline(records, is_demo=True)
    train, _ = temporal_split([row for row in records if row.label is not None])
    expected = np.mean(
        [[row.features[name] for name in FEATURES] for row in train], axis=0
    )
    np.testing.assert_allclose(result.pipeline.named_steps["scale"].mean_, expected)
    assert result.metadata["excluded_unknown"] == 1
    assert result.metadata["train_count"] + result.metadata["test_count"] == 79
    assert all(item["scope"] == "holdout" for item in result.test_predictions)


def test_real_data_gate_cannot_use_smoke_sample():
    from jit_defect.data import parse_csv
    from jit_defect.learning import fit_baseline

    with pytest.raises(ValueError, match="1000"):
        fit_baseline(parse_csv(csv_bytes()), is_demo=False)


def test_single_class_training_fails():
    from jit_defect.data import parse_csv
    from jit_defect.learning import fit_baseline

    with pytest.raises(ValueError, match="both classes"):
        fit_baseline(
            parse_csv(
                csv_bytes(mutate=lambda rows: [row.update(label=0) for row in rows])
            ),
            is_demo=True,
        )


def test_exact_contributions_reconstruct_probability():
    from jit_defect.data import parse_csv
    from jit_defect.learning import explain, fit_baseline

    records = parse_csv(csv_bytes())
    result = fit_baseline(records, is_demo=True)
    detail = explain(result.pipeline, records[-1].features)
    logit = detail["baseline"] + sum(
        item["contribution"] for item in detail["contributions"]
    )
    assert 1 / (1 + math.exp(-logit)) == pytest.approx(detail["probability"])
    assert len(detail["contributions"]) == 14
    assert detail["method"] == "linear_log_odds"


def test_metrics_match_hand_calculated_effort_curve():
    from jit_defect.learning import evaluate

    report = evaluate(
        [1, 0, 1, 0, 0], [0.9, 0.8, 0.7, 0.6, 0.5], [1] * 5, list("abcde")
    )
    assert report["recall_at_20_effort"] == 0.5
    assert report["popt"] == pytest.approx(5 / 6)
    assert report["precision"] == pytest.approx(0.4)
    assert report["roc_auc"] == pytest.approx(5 / 6)


def test_metrics_single_class_and_zero_cost_are_explicit():
    from jit_defect.learning import evaluate

    report = evaluate([0, 0], [0.9, 0.1], [0, 0], ["a", "b"])
    assert report["roc_auc"] is None
    assert report["popt"] is None
    assert report["recall_at_20_effort"] is None
    assert "roc_auc" in report["notes"]
    assert report["effort_total"] == 2


def test_effort_budget_never_skips_expensive_leading_commit():
    from jit_defect.learning import evaluate

    report = evaluate([1, 1], [0.99, 0.01], [9, 1], ["a", "b"])
    assert report["recall_at_20_effort"] == 0
    assert report["inspected_commits"] == 0
