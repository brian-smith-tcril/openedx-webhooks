"""Tests of task/github.py:pull_request_opened."""

import pytest

from openedx_webhooks.tasks.github import (
    github_community_pr_comment,
    github_contractor_pr_comment,
    pull_request_opened,
)

from . import template_snips


@pytest.fixture
def sync_labels_fn(mocker):
    """A patch on synchronize_labels"""
    return mocker.patch("openedx_webhooks.tasks.github.synchronize_labels")


def test_internal_pr_opened(reqctx, fake_github):
    pr = fake_github.make_pull_request(user="nedbat")
    with reqctx:
        key, anything_happened = pull_request_opened(pr.as_json())
    assert key is None
    assert anything_happened is False
    assert len(pr.comments) == 0


def test_pr_opened_by_bot(reqctx, fake_github):
    fake_github.make_user(login="some_bot", type="Bot")
    pr = fake_github.make_pull_request(user="some_bot")
    with reqctx:
        key, anything_happened = pull_request_opened(pr.as_json())
    assert key is None
    assert anything_happened is False
    assert len(pr.comments) == 0


def test_external_pr_opened_no_cla(reqctx, sync_labels_fn, fake_github, fake_jira):
    fake_github.make_user(login="new_contributor", name="Newb Contributor")
    pr = fake_github.make_pull_request(owner="edx", repo="edx-platform", user="new_contributor")
    prj = pr.as_json()

    with reqctx:
        issue_id, anything_happened = pull_request_opened(prj)

    assert issue_id is not None
    assert issue_id.startswith("OSPR-")
    assert anything_happened is True

    # Check the Jira issue that was created.
    assert len(fake_jira.issues) == 1
    issue = fake_jira.issues[issue_id]
    assert issue.contributor_name == "Newb Contributor"
    assert issue.customer is None
    assert issue.pr_number == prj["number"]
    assert issue.repo == prj["base"]["repo"]["full_name"]
    assert issue.url == prj["html_url"]
    assert issue.description == prj["body"]
    assert issue.issuetype == "Pull Request Review"
    assert issue.summary == prj["title"]
    assert issue.labels == []

    # Check that the Jira issue was moved to Community Manager Review.
    assert issue.status == "Community Manager Review"

    # Check that we synchronized labels.
    sync_labels_fn.assert_called_once_with("edx/edx-platform")

    # Check the GitHub comment that was created.
    assert len(pr.comments) == 1
    body = pr.comments[0].body
    jira_link = "[{id}](https://openedx.atlassian.net/browse/{id})".format(id=issue_id)
    assert jira_link in body
    assert "Thanks for the pull request, @new_contributor!" in body
    assert template_snips.EXTERNAL_TEXT in body
    assert template_snips.NO_CLA_TEXT in body
    assert template_snips.NO_CLA_LINK in body

    # Check the GitHub labels that got applied.
    assert pr.labels == {"community manager review", "open-source-contribution"}


def test_external_pr_opened_with_cla(reqctx, sync_labels_fn, fake_github, fake_jira):
    pr = fake_github.make_pull_request(owner="edx", repo="some-code", user="tusbar", number=11235)
    prj = pr.as_json()

    with reqctx:
        issue_id, anything_happened = pull_request_opened(prj)

    assert issue_id is not None
    assert issue_id.startswith("OSPR-")
    assert anything_happened is True

    # Check the Jira issue that was created.
    assert len(fake_jira.issues) == 1
    issue = fake_jira.issues[issue_id]
    assert issue.contributor_name == "Bertrand Marron"
    assert issue.customer == ["IONISx"]
    assert issue.pr_number == 11235
    assert issue.repo == "edx/some-code"
    assert issue.url == prj["html_url"]
    assert issue.description == prj["body"]
    assert issue.issuetype == "Pull Request Review"
    assert issue.summary == prj["title"]
    assert issue.labels == []

    # Check that the Jira issue is in Needs Triage.
    assert issue.status == "Needs Triage"

    # Check that we synchronized labels.
    sync_labels_fn.assert_called_once_with("edx/some-code")

    # Check the GitHub comment that was created.
    assert len(pr.comments) == 1
    body = pr.comments[0].body
    jira_link = "[{id}](https://openedx.atlassian.net/browse/{id})".format(id=issue_id)
    assert jira_link in body
    assert "Thanks for the pull request, @tusbar!" in body
    assert template_snips.EXTERNAL_TEXT in body
    assert template_snips.NO_CLA_TEXT not in body
    assert template_snips.NO_CLA_LINK not in body

    # Check the GitHub labels that got applied.
    assert pr.labels == {"needs triage", "open-source-contribution"}


def test_core_committer_pr_opened(reqctx, sync_labels_fn, fake_github, fake_jira):
    pr = fake_github.make_pull_request(user="felipemontoya", owner="edx", repo="edx-platform")
    prj = pr.as_json()

    with reqctx:
        issue_id, anything_happened = pull_request_opened(prj)

    assert issue_id is not None
    assert issue_id.startswith("OSPR-")
    assert anything_happened is True

    # Check the Jira issue that was created.
    assert len(fake_jira.issues) == 1
    issue = fake_jira.issues[issue_id]
    assert issue.contributor_name == "Felipe Montoya"
    assert issue.customer == ["EduNEXT"]
    assert issue.pr_number == prj["number"]
    assert issue.repo == prj["base"]["repo"]["full_name"]
    assert issue.url == prj["html_url"]
    assert issue.description == prj["body"]
    assert issue.issuetype == "Pull Request Review"
    assert issue.summary == prj["title"]
    assert issue.labels == ["core-committer"]

    # Check that the Jira issue was moved to Open edX Community Review.
    assert issue.status == "Open edX Community Review"

    # Check that we synchronized labels.
    sync_labels_fn.assert_called_once_with("edx/edx-platform")

    # Check the GitHub comment that was created.
    assert len(pr.comments) == 1
    body = pr.comments[0].body
    jira_link = "[{id}](https://openedx.atlassian.net/browse/{id})".format(id=issue_id)
    assert jira_link in body
    assert "Thanks for the pull request, @felipemontoya!" in body
    assert template_snips.CORE_COMMITTER_TEXT in body
    assert template_snips.NO_CLA_TEXT not in body
    assert template_snips.NO_CLA_LINK not in body

    # Check the GitHub labels that got applied.
    assert pr.labels == {"open edx community review", "open-source-contribution", "core committer"}


def test_external_pr_rescanned(reqctx, fake_github, fake_jira):
    pr = fake_github.make_pull_request(user="tusbar")
    prj = pr.as_json()
    issue = fake_jira.make_issue(key="OSPR-12345")
    with reqctx:
        comment = github_community_pr_comment(prj, jira_issue=issue.as_json())
    pr.add_comment(user=fake_github.login, body=comment)
    assert len(pr.comments) == 1

    with reqctx:
        issue_id, anything_happened = pull_request_opened(prj)

    assert issue_id == "OSPR-12345"
    assert anything_happened is False

    # No Jira issue was created.
    assert len(fake_jira.issues) == 1

    # No new GitHub comment was created.
    assert len(pr.comments) == 1


def test_contractor_pr_opened(reqctx, fake_github, fake_jira):
    pr = fake_github.make_pull_request(user="joecontractor")
    prj = pr.as_json()

    with reqctx:
        issue_id, anything_happened = pull_request_opened(prj)

    assert issue_id is None
    assert anything_happened is True

    # No Jira issue was created.
    assert len(fake_jira.issues) == 0

    # Check the GitHub comment that was created.
    assert len(pr.comments) == 1
    body = pr.comments[0].body
    assert template_snips.CONTRACTOR_TEXT in body
    href = (
        'href="https://openedx-webhooks.herokuapp.com/github/process_pr' +
        '?repo={}'.format(prj["base"]["repo"]["full_name"].replace("/", "%2F")) +
        '&number={}"'.format(prj["number"])
    )
    assert href in body
    assert 'Create an OSPR issue for this pull request' in body


def test_contractor_pr_rescanned(reqctx, fake_github, fake_jira):
    pr = fake_github.make_pull_request(user="joecontractor")
    prj = pr.as_json()
    with reqctx:
        comment = github_contractor_pr_comment(prj)
    pr.add_comment(user=fake_github.login, body=comment)

    with reqctx:
        issue_id, anything_happened = pull_request_opened(prj)

    assert issue_id is None
    assert anything_happened is False

    # No Jira issue was created.
    assert len(fake_jira.issues) == 0

    # No new GitHub comment was created.
    assert len(pr.comments) == 1
