import math

import pytest
from conftest import csv_bytes, import_dataset, trained_dataset
from fastapi.testclient import TestClient


def test_empty_workspace(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/datasets").json() == []
    assert client.get("/api/models").json() == []


def test_invalid_import_is_atomic(client):
    response = client.post(
        "/api/datasets/import",
        files={
            "file": (
                "bad.csv",
                csv_bytes(mutate=lambda rows: rows[-1].update(nf="nan")),
                "text/csv",
            )
        },
        data={
            "name": "Bad",
            "provenance": "test",
            "label_policy": "test",
            "is_demo": "true",
        },
    )
    assert response.status_code == 422
    assert "nf" in response.json()["detail"]
    assert client.get("/api/datasets").json() == []


def test_real_sample_rejected_without_ready_model(client):
    dataset = import_dataset(client, is_demo=False)
    response = client.post("/api/models/train", json={"dataset_id": dataset["id"]})
    assert response.status_code == 422
    assert client.get("/api/models").json() == []


def test_train_rank_explain_and_restart(client, tmp_path):
    from jit_defect.api import create_app

    dataset, model = trained_dataset(client)
    assert len(dataset["source_sha256"]) == 64
    assert dataset["is_demo"] is True
    assert model["metrics"]["roc_auc"] is not None
    assert "popt" in model["metrics"]
    query = {"model_id": model["id"], "page_size": 5}
    first = client.get("/api/risks", params=query).json()
    second = client.get("/api/risks", params={**query, "page": 2}).json()
    combined = first["items"] + second["items"]
    assert first["total"] == model["metadata"]["test_count"]
    assert len({item["commit_id"] for item in combined}) == 10
    assert [item["probability"] for item in combined] == sorted(
        [item["probability"] for item in combined], reverse=True
    )
    assert all(item["scope"] == "holdout" for item in combined)
    commit_id = first["items"][0]["commit_id"]
    detail = client.get(f"/api/models/{model['id']}/commits/{commit_id}").json()
    logit = detail["explanation"]["baseline"] + sum(
        item["contribution"] for item in detail["explanation"]["contributions"]
    )
    assert detail["probability"] == pytest.approx(1 / (1 + math.exp(-logit)))
    assert detail["probability"] == pytest.approx(first["items"][0]["probability"])
    with TestClient(create_app(data_dir=tmp_path)) as restarted:
        assert restarted.get("/api/datasets").json()[0]["id"] == dataset["id"]
        restored = restarted.get(f"/api/models/{model['id']}/commits/{commit_id}")
        assert restored.status_code == 200
        assert restored.json()["probability"] == detail["probability"]


def test_risk_filters_and_training_scope(client):
    dataset, model = trained_dataset(client)
    response = client.get(
        "/api/risks",
        params={
            "model_id": model["id"],
            "min_probability": 0.7,
            "scope": "all",
            "search": "commit-",
        },
    )
    assert response.status_code == 200
    assert all(item["probability"] >= 0.7 for item in response.json()["items"])
    all_rows = client.get(
        "/api/risks", params={"model_id": model["id"], "scope": "all", "page_size": 100}
    ).json()
    assert all_rows["total"] == dataset["row_count"]
    assert {"training", "holdout"} == {item["scope"] for item in all_rows["items"]}


def test_model_dataset_mismatch_and_missing_ids(client):
    _, model = trained_dataset(client)
    other = import_dataset(client, name="Other")
    mismatch = client.get(
        "/api/risks", params={"model_id": model["id"], "dataset_id": other["id"]}
    )
    assert mismatch.status_code == 409
    assert client.get("/api/risks", params={"model_id": "missing"}).status_code == 404
    assert client.get(f"/api/models/{model['id']}/commits/missing").status_code == 404


def test_model_versions_are_immutable(client):
    dataset, first = trained_dataset(client)
    second = client.post("/api/models/train", json={"dataset_id": dataset["id"]}).json()
    assert first["id"] != second["id"]
    assert len(client.get("/api/models").json()) == 2


def test_demo_import_is_idempotent_and_marked(client):
    first = client.post("/api/demo").json()
    second = client.post("/api/demo").json()
    assert first["id"] == second["id"]
    assert first["is_demo"] is True
    assert "synthetic" in first["provenance"].lower()
    assert len(client.get("/api/datasets").json()) == 1


def test_missing_or_corrupt_artifact_does_not_fabricate_scores(client, tmp_path):
    _, model = trained_dataset(client)
    artifact = tmp_path / "models" / f"{model['id']}.joblib"
    artifact.write_bytes(b"corrupt artifact")
    response = client.get(f"/api/models/{model['id']}/commits/commit-0079")
    assert response.status_code == 409
    assert "artifact" in response.json()["detail"].lower()
    artifact.unlink()
    assert client.get("/api/risks", params={"model_id": model["id"]}).status_code == 409
