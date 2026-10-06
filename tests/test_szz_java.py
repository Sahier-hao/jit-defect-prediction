import importlib
import importlib.util

import pytest
from test_preparation_patch import SAMPLES, text_patch


def module():
    assert importlib.util.find_spec("jit_defect.szz_inputs") is not None, (
        "whole-parent Java SZZ input preparation is missing"
    )
    return importlib.import_module("jit_defect.szz_inputs")


@pytest.mark.parametrize(
    "source,expected",
    [
        (b"// note\n \t\f\nint x; // note\n", ["comment", "blank", "code"]),
        (b"/* start\nno prefix here\n*/\nrun();\n", ["comment"] * 3 + ["code"]),
        (b"/* start\n*/ run();\n", ["comment", "code"]),
        (b"/* a /* // b */ int x;\n", ["code"]),
        (b'var s = "http://host/*value*/"; // note\n', ["code"]),
        (b'var s = "escaped \\" // text";\n// real\n', ["code", "comment"]),
        (b"char slash = '/'; char quote = '\\''; /* note */\n", ["code"]),
        (
            b'String s = """\n// literal\n/* literal */\n   \n""";\n// real\n',
            ["code"] * 5 + ["comment"],
        ),
        (
            b'String s = """\n\\""" still literal\n""";\n/* real */\n',
            ["code"] * 3 + ["comment"],
        ),
        (b"/* note */\r\nint x;\r\n", ["comment", "code"]),
        ('// 中文\nString s = "值";'.encode(), ["comment", "code"]),
    ],
)
def test_whole_parent_java_context(source, expected):
    assert module().classify_java(source) == expected


@pytest.mark.parametrize(
    "source,diagnostic",
    [
        (b"/* unfinished\n", "unterminated"),
        (b'"unfinished\n', "unterminated"),
        (b"'unfinished", "unterminated"),
        (b'String s = """\nunfinished\n', "unterminated"),
        (b'String s = """no newline""";', "text block"),
        (b"// \\u000a run();\n", "Unicode"),
        (b"// \\uu002f note\n", "Unicode"),
        (b"// \\uBAD\n", "Unicode"),
        (b"// note\rint x;\n", "CR"),
        (b"\xff", "UTF-8"),
    ],
)
def test_unsupported_java_does_not_guess(source, diagnostic):
    with pytest.raises(ValueError, match=diagnostic):
        module().classify_java(source)


def test_all_hunks_reconstruct_real_full_file():
    from jit_defect.preparation import parse_patch

    file = parse_patch((SAMPLES / "fix-72befc14.patch").read_bytes()).files[1]
    parent = (SAMPLES / "parent-AsyncServletRequest.java.txt").read_bytes()
    fixed = (SAMPLES / "fixed-AsyncServletRequest.java.txt").read_bytes()
    old = module().verify_file_diff(file, parent, fixed)
    assert old[120] == "            context.complete();\n"
    with pytest.raises(ValueError, match="context"):
        module().verify_file_diff(
            file, parent.replace(b"context.complete();", b"bad();"), fixed
        )
    with pytest.raises(ValueError, match="fixed"):
        module().verify_file_diff(file, parent, fixed + b"// outside hunk\n")


@pytest.mark.parametrize("terminal", [True, False])
def test_terminal_newline_is_verified(terminal):
    from jit_defect.preparation import parse_patch

    marker = "" if terminal else "\\ No newline at end of file\n"
    patch = text_patch(
        "diff --git a/x.java b/x.java\n--- a/x.java\n+++ b/x.java\n"
        "@@ -1 +1 @@\n-old\n" + marker + "+new\n" + marker
    )
    file = parse_patch(patch).files[0]
    suffix = b"\n" if terminal else b""
    module().verify_file_diff(file, b"old" + suffix, b"new" + suffix)
    with pytest.raises(ValueError):
        module().verify_file_diff(
            file, b"old\n" if not terminal else b"old", b"new" + suffix
        )


def test_multiple_hunks_and_insertion_anchor():
    from jit_defect.preparation import parse_patch

    patch = text_patch(
        "diff --git a/x.java b/x.java\n--- a/x.java\n+++ b/x.java\n"
        "@@ -0,0 +1 @@\n+zero\n@@ -2 +3 @@\n-two\n+TWO\n"
    )
    file = parse_patch(patch).files[0]
    assert module().verify_file_diff(
        file, b"one\ntwo\nthree\n", b"zero\none\nTWO\nthree\n"
    ) == ["one\n", "two\n", "three\n"]
