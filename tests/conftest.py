import csv
import io
from datetime import datetime, timedelta, timezone

import pytest

FEATURES = (
    "ns",
    "nd",
    "nf",
    "entropy",
    "la",
    "ld",
    "lt",
    "fix",
    "ndev",
    "age",
    "nuc",
    "exp",
    "rexp",
    "sexp",
)


def csv_bytes(count=80, mutate=None):
    rows = []
    for index in range(count):
        nf = index % 9 + 1
        row = dict.fromkeys(FEATURES, 1)
        row.update(
            commit_id=f"commit-{index:04}",
            committed_at=(
                datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=index)
            ).isoformat(),
            label=int(nf >= 6),
            nf=nf,
            la=nf * 7,
            ld=index % 5,
            fix=0,
            message=f"Change {index}",
        )
        rows.append(row)
    if mutate:
        mutate(rows)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=["commit_id", "committed_at", "label", *FEATURES, "message"]
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


@pytest.fixture
def feature_csv():
    return csv_bytes()


@pytest.fixture
def client(tmp_path):
    from fastapi.testclient import TestClient

    from jit_defect.api import create_app

    with TestClient(create_app(data_dir=tmp_path)) as test_client:
        yield test_client


def import_dataset(client, contents=None, name="Test dataset", is_demo=True):
    response = client.post(
        "/api/datasets/import",
        files={"file": ("features.csv", contents or csv_bytes(), "text/csv")},
        data={
            "name": name,
            "provenance": "Synthetic test fixture",
            "label_policy": "Synthetic labels, not SZZ",
            "is_demo": str(is_demo).lower(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def trained_dataset(client):
    dataset = import_dataset(client)
    response = client.post("/api/models/train", json={"dataset_id": dataset["id"]})
    assert response.status_code == 201, response.text
    return dataset, response.json()
