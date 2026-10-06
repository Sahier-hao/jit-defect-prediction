import importlib
import json
from pathlib import Path

import pytest

SAMPLES = (
    Path(__file__).resolve().parents[1] / "docs/数据核查/activemq-2024-sample-20261004"
)
INTEGRATION = "2024-04-22T15:01:36Z"
QUALIFICATION = "2024-04-22T15:07:37.776000+00:00"
INTEGRATION_SOURCE = "https://github.com/apache/activemq/pull/1206"


def report(*, issue=None, patch=None, **overrides):
    module = importlib.import_module("jit_defect.preparation")
    assert callable(getattr(module, "prepare_fix", None)), (
        "historical preparation function is missing"
    )
    kwargs = dict(
        as_of="2024-04-23T00:00:00Z",
        snapshot_at="2026-10-04T02:29:03Z",
        integrated_at=INTEGRATION,
        target_branch="main",
        integration_source=INTEGRATION_SOURCE,
    )
    kwargs.update(overrides)
    return module.prepare_fix(
        patch or (SAMPLES / "fix-72befc14.patch").read_bytes(),
        json.dumps(issue).encode()
        if issue
        else (SAMPLES / "AMQ-9481.json").read_bytes(),
        **kwargs,
    )


def issue_snapshot(key="AMQ-9481"):
    return json.loads((SAMPLES / (key + ".json")).read_bytes())


def test_real_fix_candidate_is_never_an_inducing_label_or_feature_vector():
    result = report()
    assert result["candidate"]["status"] == "candidate"
    assert result["candidate"]["availableAt"] == QUALIFICATION
    assert result["issue"]["stateAtCutoff"] == {
        "issuetype": "Bug",
        "status": "Resolved",
        "resolution": "Fixed",
    }
    assert result["issue"]["rawResolutionDate"] == "2024-04-22T15:07:37.766+0000"
    assert result["inducingLabel"] is None
    assert result["labelStatus"] == "unknown_szz_not_executed"
    assert result["kamei14"] is None
    assert result["attributionPolicy"] == "pending_file_and_comment_review"
    assert result["integration"]["source"] == INTEGRATION_SOURCE
    assert result["integration"]["verification"] == "caller_supplied_requires_review"


def test_authored_before_cutoff_does_not_make_unintegrated_fix_available():
    result = report(as_of="2024-04-22T00:00:00Z")
    assert result["issue"]["stateAtCutoff"] == {
        "issuetype": "Bug",
        "status": "In Progress",
        "resolution": None,
    }
    assert result["candidate"]["status"] == "unverified_issue_state"
    assert result["candidate"]["availableAt"] is None
    assert result["inducingLabel"] is None


@pytest.mark.parametrize(
    "cutoff,status",
    [
        ("2024-04-22T15:07:37.766Z", "unverified_issue_state"),
        ("2024-04-22T15:07:37.775Z", "unverified_issue_state"),
        ("2024-04-22T15:07:37.776Z", "candidate"),
    ],
)
def test_qualification_event_is_not_backdated_to_resolution_field(cutoff, status):
    assert report(as_of=cutoff)["candidate"]["status"] == status


def test_real_non_bug_type_is_reconstructed_before_later_type_change():
    result = report(issue=issue_snapshot("AMQ-9461"))
    assert result["issue"]["stateAtCutoff"]["issuetype"] == "Improvement"
    assert result["candidate"]["status"] == "excluded_non_bug"
    assert result["inducingLabel"] is None
    later = report(issue=issue_snapshot("AMQ-9461"), as_of="2024-07-01T00:00:00Z")
    assert later["issue"]["stateAtCutoff"]["issuetype"] == "Task"


def test_unresolved_bug_stays_unverified_not_clean():
    result = report(issue=issue_snapshot("AMQ-9482"))
    assert result["candidate"]["status"] == "unverified_issue_state"
    assert result["inducingLabel"] is None


@pytest.mark.parametrize("mutation", ["missing_page", "nonzero_start", "missing_log"])
def test_incomplete_history_produces_unknown(mutation):
    issue = issue_snapshot()
    if mutation == "missing_page":
        issue["changelog"]["histories"].pop()
    elif mutation == "nonzero_start":
        issue["changelog"]["startAt"] = 1
    else:
        issue.pop("changelog")
    result = report(issue=issue)
    assert result["candidate"]["status"] == "unknown_incomplete_history"
    assert result["issue"]["stateAtCutoff"] is None


def test_snapshot_cannot_establish_future_issue_state():
    result = report(snapshot_at="2024-04-22T16:00:00Z")
    assert result["candidate"]["status"] == "unknown_snapshot_outdated"


def test_issue_before_creation_is_not_a_clean_label():
    result = report(as_of="2024-04-01T00:00:00Z")
    assert result["candidate"]["status"] == "unknown_issue_not_created"


@pytest.mark.parametrize(
    "override,status",
    [
        ({"integrated_at": None}, "unknown_integration"),
        ({"integration_source": None}, "unknown_integration"),
        ({"integrated_at": "2024-04-24T00:00:00Z"}, "unknown_not_integrated"),
    ],
)
def test_branch_integration_is_required_and_cannot_be_in_future(override, status):
    assert report(**override)["candidate"]["status"] == status


def test_message_link_is_required():
    issue = issue_snapshot()
    issue["key"] = "AMQ-9999"
    assert report(issue=issue)["candidate"]["status"] == "unlinked_issue"


def test_integration_later_than_qualification_sets_availability():
    result = report(integrated_at="2024-04-22T23:00:00Z")
    assert result["candidate"]["availableAt"] == "2024-04-22T23:00:00+00:00"


def test_later_bug_type_is_not_backfilled_to_original_fix_time():
    issue = issue_snapshot("AMQ-9461")
    issue["fields"]["issuetype"]["name"] = "Bug"
    for event in issue["changelog"]["histories"]:
        for item in event["items"]:
            if item["field"] == "issuetype":
                item["toString"] = "Bug"
    patch = (
        (SAMPLES / "fix-72befc14.patch")
        .read_bytes()
        .replace(b"AMQ-9481", b"AMQ-9461", 1)
    )
    assert report(issue=issue, patch=patch)["candidate"]["status"] == "excluded_non_bug"
    later = report(issue=issue, patch=patch, as_of="2024-07-01T00:00:00Z")
    assert later["candidate"]["status"] == "candidate"
    assert later["candidate"]["availableAt"] == "2024-06-02T16:44:41.946000+00:00"


def test_no_qualification_event_is_not_assigned_an_invented_time():
    issue = issue_snapshot()
    issue["changelog"]["histories"] = []
    issue["changelog"]["total"] = 0
    assert report(issue=issue)["candidate"]["status"] == "unknown_qualification_time"


def test_reopening_invalidates_current_qualified_state():
    issue = issue_snapshot()
    issue["changelog"]["histories"].append(
        {
            "id": "test-reopen",
            "created": "2024-04-23T12:00:00Z",
            "items": [
                {"field": "status", "fromString": "Resolved", "toString": "Reopened"},
                {"field": "resolution", "fromString": "Fixed", "toString": None},
            ],
        }
    )
    issue["changelog"]["total"] += 1
    issue["fields"]["status"]["name"] = "Reopened"
    issue["fields"]["resolution"] = None
    assert report(issue=issue)["candidate"]["status"] == "candidate"
    reopened = report(issue=issue, as_of="2024-04-24T00:00:00Z")
    assert reopened["candidate"]["status"] == "unverified_issue_state"


@pytest.mark.parametrize(
    "mutation", ["contradictory_state", "duplicate_id", "bad_time"]
)
def test_inconsistent_complete_history_is_rejected(mutation):
    issue = issue_snapshot()
    if mutation == "contradictory_state":
        issue["fields"]["status"]["name"] = "Open"
    elif mutation == "duplicate_id":
        issue["changelog"]["histories"][1]["id"] = issue["changelog"]["histories"][0][
            "id"
        ]
    else:
        issue["changelog"]["histories"][0]["created"] = "2024-04-15T12:00:00"
    with pytest.raises(ValueError, match="history|timezone"):
        report(issue=issue)


@pytest.mark.parametrize(
    "overrides",
    [
        {"as_of": "2024-04-23"},
        {"snapshot_at": "2026-10-04"},
        {"integrated_at": "2024-04-22"},
        {"target_branch": ""},
    ],
)
def test_invalid_temporal_or_branch_contract_is_rejected(overrides):
    with pytest.raises(ValueError, match="timezone|branch"):
        report(**overrides)
