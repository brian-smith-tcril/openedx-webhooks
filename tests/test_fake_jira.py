"""Tests of FakeJira."""

import requests


# pylint: disable=missing-timeout

class TestIssues:
    """
    Tests of the correct behavior of issuees.
    """
    def test_get_issue(self, fake_jira):
        fake_jira.make_issue(key="HELLO-123", summary="This is a bad bug!")
        resp = requests.get("https://test.atlassian.net/rest/api/2/issue/HELLO-123")
        assert resp.status_code == 200
        issue = resp.json()
        assert issue["key"] == "HELLO-123"
        assert issue["fields"]["summary"] == "This is a bad bug!"

    def test_update_summary(self, fake_jira):
        issue = fake_jira.make_issue(
            project="HELLO",
            summary="This is a bad bug!",
            description="Here are the details so you can see how serious it is.",
        )
        resp = requests.put(
            f"https://test.atlassian.net/rest/api/2/issue/{issue.key}",
            json={"fields": {"summary": "This is OK."}},
        )
        assert resp.status_code == 204
        resp = requests.get(f"https://test.atlassian.net/rest/api/2/issue/{issue.key}")
        assert resp.status_code == 200
        issue2 = resp.json()
        # The title is changed.
        assert issue2["fields"]["summary"] == "This is OK."
        # The body is unchanged.
        assert issue2["fields"]["description"] == "Here are the details so you can see how serious it is."

    def test_delete_issue(self, fake_jira):
        fake_jira.make_issue(key="HELLO-123", summary="This is a bad bug!")
        resp = requests.get("https://test.atlassian.net/rest/api/2/issue/HELLO-123")
        assert resp.status_code == 200
        assert "HELLO-123" in fake_jira.issues

        resp = requests.delete("https://test.atlassian.net/rest/api/2/issue/HELLO-123")
        assert resp.status_code == 204

        resp = requests.get("https://test.atlassian.net/rest/api/2/issue/HELLO-123")
        assert resp.status_code == 404
        assert "HELLO-123" not in fake_jira.issues

    def test_move_issue(self, fake_jira):
        issue1 = fake_jira.make_issue(project="HELLO", summary="This is a bad bug!")
        key1 = issue1.key
        issue2 = fake_jira.move_issue(issue1, "BLENDED")
        key2 = issue2.key
        assert key2.startswith("BLENDED-")

        # Look it up under the old key.
        resp = requests.get(f"https://test.atlassian.net/rest/api/2/issue/{key1}")
        assert resp.status_code == 200
        jissue1 = resp.json()
        assert jissue1["key"] == key2   # it has the new key.
        assert jissue1["fields"]["summary"] == "This is a bad bug!"

        # Look it up under the new key.
        resp = requests.get(f"https://test.atlassian.net/rest/api/2/issue/{key2}")
        assert resp.status_code == 200
        jissue2 = resp.json()
        assert jissue2["key"] == key2
        assert jissue2["fields"]["summary"] == "This is a bad bug!"

    def test_empty_values(self, fake_jira):
        fake_jira.make_issue(key="HELLO-123", summary="", description="")
        resp = requests.get("https://test.atlassian.net/rest/api/2/issue/HELLO-123")
        assert resp.status_code == 200
        issue = resp.json()
        assert issue["key"] == "HELLO-123"
        assert issue["fields"]["summary"] is None
        assert issue["fields"]["description"] is None


class TestBadRequests:
    """
    Tests of the error edge cases.
    """
    def test_no_such_put(self, fake_jira):
        resp = requests.put("https://test.atlassian.net/rest/api/2/issue/XYZ-999")
        assert resp.status_code == 404

    def test_no_such_delete(self, fake_jira):
        resp = requests.delete("https://test.atlassian.net/rest/api/2/issue/XYZ-999")
        assert resp.status_code == 404

    def test_no_such_transitions(self, fake_jira):
        resp = requests.get("https://test.atlassian.net/rest/api/2/issue/XYZ-999/transitions")
        assert resp.status_code == 404

    def test_baffling_search(self, fake_jira):
        resp = requests.get("https://test.atlassian.net/rest/api/2/search?jql=xyzzy")
        assert resp.status_code == 500
