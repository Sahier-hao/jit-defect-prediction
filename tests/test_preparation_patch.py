import importlib
import importlib.util
from pathlib import Path

import pytest

SAMPLES = (
    Path(__file__).resolve().parents[1] / "docs/数据核查/activemq-2024-sample-20261004"
)


def preparation():
    assert importlib.util.find_spec("jit_defect.preparation") is not None, (
        "offline preparation module is missing"
    )
    return importlib.import_module("jit_defect.preparation")


def text_patch(body, *, message="AMQ-1 example"):
    return (
        "From " + "a" * 40 + " Mon Sep 17 00:00:00 2001\n"
        "From: Test <test@example.com>\n"
        "Date: Mon, 22 Apr 2024 00:00:00 +0000\n"
        f"Subject: [PATCH] {message}\n\n"
        "---\n\n" + body
    ).encode()


def test_real_patch_counts_and_message_only_issue_links():
    patch = preparation().parse_patch((SAMPLES / "fix-72befc14.patch").read_bytes())
    assert patch.commit_id == "72befc14fbb69c24bdec0c7d4a1002da8874380d"
    assert patch.issue_refs == ("AMQ-9481",)
    assert "on timeout" in patch.message
    assert patch.raw_counts == {"NF": 2, "LA": 17, "LD": 8}
    production = patch.files[1]
    assert [(line.old_line, line.kind) for line in production.removed] == [
        (118, "-"),
        (119, "-"),
        (120, "-"),
        (121, "-"),
    ]
    assert "//" in production.removed[1].text
    assert "context.complete();" in production.removed[3].text


def test_hunks_reconstruct_independent_fixed_snapshot():
    patch = preparation().parse_patch((SAMPLES / "fix-72befc14.patch").read_bytes())
    parent = (SAMPLES / "parent-AsyncServletRequest.java.txt").read_text().splitlines()
    expected = (SAMPLES / "fixed-AsyncServletRequest.java.txt").read_text().splitlines()
    result = []
    cursor = 0
    for hunk in patch.files[1].hunks:
        result.extend(parent[cursor : hunk.old_start - 1])
        cursor = hunk.old_start - 1
        for line in hunk.lines:
            if line.old_line is not None:
                assert parent[cursor] == line.text
                cursor += 1
            if line.new_line is not None:
                result.append(line.text)
    result.extend(parent[cursor:])
    assert result == expected


@pytest.mark.parametrize(
    "filename",
    ["backport-827ad101.patch", "amq9330-dc892d3d.patch", "amq9330-8b6072d0.patch"],
)
def test_other_real_patches_preserve_cherry_pick_origins(filename):
    patch = preparation().parse_patch((SAMPLES / filename).read_bytes())
    if filename.startswith("backport"):
        assert patch.cherry_picked_from == ("72befc14fbb69c24bdec0c7d4a1002da8874380d",)
    elif "dc892" in filename:
        assert patch.cherry_picked_from == (
            "8b6072d03e273b02288e71cac6eef0539c48ea02",
            "45a1bd54d3e1202d775388cf5b7d63e4c96183a5",
        )
    else:
        assert patch.cherry_picked_from == ()


@pytest.mark.parametrize(
    "body,diagnostic",
    [
        ("diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1,2 +1,2 @@\n-a\n+b\n", "hunk"),
        ("diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n+extra\n", "hunk"),
        ("diff --git a/x b/x\nBinary files a/x and b/x differ\n", "unsupported"),
        (
            "diff --git a/x b/y\nsimilarity index 100%\nrename from x\nrename to y\n",
            "unsupported",
        ),
        ("diff --git a/x b/x\nold mode 100644\nnew mode 100755\n", "unsupported"),
        (
            "diff --git a/../x b/../x\n--- a/../x\n+++ b/../x\n@@ -1 +1 @@\n-a\n+b\n",
            "path",
        ),
        ("diff --git a/x b/x\n--- a/wrong\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n", "path"),
        (
            "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -2 +2 @@\n-a\n+b\n@@ -1 +1 @@\n-a\n+b\n",
            "hunk",
        ),
    ],
)
def test_invalid_or_unsupported_patch_is_explicit_failure(body, diagnostic):
    with pytest.raises(ValueError, match=diagnostic):
        preparation().parse_patch(text_patch(body))


def test_new_and_deleted_files_have_zero_sided_ranges():
    body = (
        "diff --git a/new.txt b/new.txt\nnew file mode 100644\n"
        "--- /dev/null\n+++ b/new.txt\n@@ -0,0 +1,2 @@\n+first\n+second\n"
        "diff --git a/old.txt b/old.txt\ndeleted file mode 100644\n"
        "--- a/old.txt\n+++ /dev/null\n@@ -1 +0,0 @@\n-old\n"
    )
    patch = preparation().parse_patch(text_patch(body))
    assert patch.raw_counts == {"NF": 2, "LA": 2, "LD": 1}
    assert patch.files[0].path_before is None
    assert patch.files[1].path_after is None
    assert patch.files[1].removed[0].old_line == 1


def test_no_newline_marker_and_crlf_transport_are_preserved():
    body = (
        "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n"
        "-old\n\\ No newline at end of file\n"
        "+new\n\\ No newline at end of file\n"
    )
    raw = text_patch(body).replace(b"\n", b"\r\n")
    patch = preparation().parse_patch(raw)
    assert patch.raw_counts == {"NF": 1, "LA": 1, "LD": 1}
    assert all(line.no_newline for line in patch.files[0].hunks[0].lines)


def test_single_patch_utf8_and_size_bounds():
    module = preparation()
    raw = (SAMPLES / "fix-72befc14.patch").read_bytes()
    with pytest.raises(ValueError, match="single"):
        module.parse_patch(raw + raw)
    with pytest.raises(ValueError, match="UTF-8"):
        module.parse_patch(b"\xff")
    with pytest.raises(ValueError, match="size"):
        module.parse_patch(raw, max_bytes=10)


def test_subject_only_message_does_not_read_issue_refs_from_diffstat():
    raw = text_patch(
        "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n"
    ).replace(b"\n---\n\n", b"\n---\n AMQ-999.java | 2 +-\n\n")
    assert preparation().parse_patch(raw).issue_refs == ("AMQ-1",)


def test_inconsistent_old_new_hunk_offsets_are_rejected():
    raw = text_patch("diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +50 @@\n-old\n+new\n")
    with pytest.raises(ValueError, match="hunk"):
        preparation().parse_patch(raw)
