import numpy as np
import pytest
from conftest import csv_bytes, import_dataset
from test_temporal_audit import encode, module, temporal_inputs


def test_large_non_demo_csv_cannot_train_without_temporal_contract():
    from jit_defect.data import parse_csv
    from jit_defect.learning import fit_baseline

    with pytest.raises(ValueError, match="temporal contract"):
        fit_baseline(parse_csv(csv_bytes(1000)), is_demo=False)


def test_api_refusal_does_not_register_or_publish_model(client):
    dataset = import_dataset(client, csv_bytes(1000), is_demo=False)
    result = client.post("/api/models/train", json={"dataset_id": dataset["id"]})
    assert result.status_code == 422
    assert "temporal contract" in result.json()["detail"]
    assert client.get("/api/models").json() == []
    assert not list(client.app.state.store.models_dir.glob("*.joblib"))


def test_audited_scaler_sees_only_available_training_rows():
    from jit_defect import learning

    assert hasattr(learning, "fit_temporal_baseline")
    raw, contract = temporal_inputs(mutate=lambda rows: rows[5].update(la=999999))
    contract["rows"][5]["labelAvailableAt"] = "2025-03-05T00:00:00Z"
    audit = module().audit_temporal(raw, encode(contract))
    result = learning.fit_temporal_baseline(raw, encode(contract), is_demo=True)
    expected = np.mean(
        [[row.features[name] for name in learning.FEATURES] for row in audit.train],
        axis=0,
    )
    np.testing.assert_allclose(result.pipeline.named_steps["scale"].mean_, expected)
    assert "commit-0005" not in {row["commit_id"] for row in result.predictions}
    assert result.metadata["label_availability_checked"] is True
    assert result.metadata["split_at"] == contract["config"]["trainCutoff"]
    assert result.metadata["train_ratio_requested"] is None
    assert result.metadata["temporal_audit"] == audit.report
    assert result.metrics["test_count"] == len(audit.test)


def test_audited_entrypoint_enforces_hash_and_post_filter_sample_gates():
    from jit_defect import learning

    assert hasattr(learning, "fit_temporal_baseline")
    raw, contract = temporal_inputs()
    with pytest.raises(ValueError, match="hash"):
        learning.fit_temporal_baseline(raw + b"\n", encode(contract), is_demo=True)
    with pytest.raises(ValueError, match="1000"):
        learning.fit_temporal_baseline(raw, encode(contract), is_demo=False)
    for row in contract["rows"]:
        row["evidenceRef"] = None
    with pytest.raises(ValueError, match="20"):
        learning.fit_temporal_baseline(raw, encode(contract), is_demo=True)


def test_audited_empty_holdout_and_one_class_training_fail():
    from jit_defect import learning

    assert hasattr(learning, "fit_temporal_baseline")
    raw, contract = temporal_inputs()
    for row in contract["rows"][56:]:
        row["evidenceRef"] = None
    with pytest.raises(ValueError, match="test cohort"):
        learning.fit_temporal_baseline(raw, encode(contract), is_demo=True)
    raw, contract = temporal_inputs(
        mutate=lambda rows: [row.update(label=0) for row in rows]
    )
    with pytest.raises(ValueError, match="both classes"):
        learning.fit_temporal_baseline(raw, encode(contract), is_demo=True)


def test_synthetic_legacy_fit_reports_unchecked_label_times():
    from jit_defect.data import parse_csv
    from jit_defect.learning import fit_baseline

    result = fit_baseline(parse_csv(csv_bytes()), is_demo=True)
    assert result.metadata["label_availability_checked"] is False
    assert result.metadata["label_time_policy"] == "unchecked_synthetic_only"


@pytest.mark.parametrize("exclude_one", [False, True])
def test_large_synthetic_fixture_exercises_non_demo_count_gate_after_audit(exclude_one):
    from jit_defect.learning import fit_temporal_baseline

    raw, contract = temporal_inputs(1000)
    if exclude_one:
        contract["rows"][5]["evidenceRef"] = None
        with pytest.raises(ValueError, match="1000"):
            fit_temporal_baseline(raw, encode(contract))
    else:
        result = fit_temporal_baseline(raw, encode(contract))
        assert result.metadata["train_count"] == 700
        assert result.metadata["test_count"] == 300
        assert result.metadata["temporal_audit"]["trainingReady"] is False
