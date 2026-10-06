import pytest
from conftest import csv_bytes


def test_import_preserves_unknown_and_normalizes_timezone(feature_csv):
    from jit_defect.data import parse_csv

    records = parse_csv(
        csv_bytes(
            mutate=lambda rows: rows[0].update(
                label="unknown", committed_at="2025-01-01T08:00:00+08:00"
            )
        )
    )
    assert records[0].label is None
    assert records[0].committed_at.isoformat() == "2025-01-01T00:00:00+00:00"
    assert len(records[0].features) == 14


@pytest.mark.parametrize(
    "field,value",
    [
        ("la", "-1"),
        ("nf", "nan"),
        ("entropy", "inf"),
        ("fix", "2"),
        ("label", "false"),
        ("committed_at", "2025-01-01"),
        ("commit_id", ""),
    ],
)
def test_import_rejects_invalid_values(field, value):
    from jit_defect.data import parse_csv

    with pytest.raises(ValueError, match=field):
        parse_csv(csv_bytes(mutate=lambda rows: rows[3].update({field: value})))


def test_import_rejects_duplicate_ids():
    from jit_defect.data import parse_csv

    with pytest.raises(ValueError, match="duplicate"):
        parse_csv(
            csv_bytes(
                mutate=lambda rows: rows[1].update(commit_id=rows[0]["commit_id"])
            )
        )


def test_import_rejects_missing_column(feature_csv):
    from jit_defect.data import parse_csv

    with pytest.raises(ValueError, match="ns"):
        parse_csv(feature_csv.replace(b",ns,", b",not_ns,"))


def test_import_accepts_bom(feature_csv):
    from jit_defect.data import parse_csv

    assert len(parse_csv(b"\xef\xbb\xbf" + feature_csv)) == 80


def test_import_enforces_limits(feature_csv):
    from jit_defect.data import parse_csv

    with pytest.raises(ValueError, match="limit"):
        parse_csv(feature_csv, max_bytes=100)
    with pytest.raises(ValueError, match="limit"):
        parse_csv(feature_csv, max_rows=10)
