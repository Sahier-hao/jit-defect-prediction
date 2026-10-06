"""Deterministic synthetic examples, never repository/SZZ evidence."""

import argparse
import csv
import io
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .data import FEATURES


def demo_csv() -> bytes:
    randomizer = random.Random(42)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=["commit_id", "committed_at", "label", *FEATURES, "message"]
    )
    writer.writeheader()
    for index in range(240):
        nf = randomizer.randint(1, 12)
        la = randomizer.randint(1, 100) * nf
        ld = randomizer.randint(0, 15) * nf
        exp = randomizer.randint(1, 120)
        noise = randomizer.random()
        label = int(nf >= 7 or (la > 300 and exp < 35) or noise < 0.08)
        writer.writerow(
            {
                "commit_id": f"demo-{index:04}",
                "committed_at": (
                    datetime(2025, 1, 1, tzinfo=timezone.utc)
                    + timedelta(hours=index * 6)
                ).isoformat(),
                "label": "unknown" if index % 29 == 0 else label,
                "ns": min(nf, 3),
                "nd": min(nf, 5),
                "nf": nf,
                "entropy": round(randomizer.uniform(0, 3), 4),
                "la": la,
                "ld": ld,
                "lt": randomizer.randint(200, 5000),
                "fix": int(index % 7 == 0),
                "ndev": randomizer.randint(1, 8),
                "age": randomizer.randint(1, 300),
                "nuc": randomizer.randint(1, 80),
                "exp": exp,
                "rexp": round(exp / (1 + randomizer.random() * 5), 4),
                "sexp": randomizer.randint(0, exp),
                "message": f"Synthetic example: {'update validation' if nf >= 7 else 'adjust helper'} {index}",
            }
        )
    return stream.getvalue().encode("utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Write clearly synthetic Kamei-feature examples"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(demo_csv())
    print(f"Synthetic sample written to {args.output}")
