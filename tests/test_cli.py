import json
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "compliance_chronicle", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def good_issue_json(tmp_path, sample_issue):
    path = tmp_path / "issue.json"
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(sample_issue.to_dict(), handle)
    return str(path)


class TestValidate:
    def test_valid_issue_exit_0(self, good_issue_json):
        result = run_cli("validate", good_issue_json)
        assert result.returncode == 0
        assert "SHIPPABLE" in result.stdout

    def test_broken_issue_exit_1(self, tmp_path, sample_issue):
        sample_issue.items[0].citation = None
        path = tmp_path / "bad.json"
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(sample_issue.to_dict(), handle)
        result = run_cli("validate", str(path))
        assert result.returncode == 1
        assert "NOT SHIPPABLE" in result.stdout
        assert "model-validation" in result.stdout

    def test_missing_file_exit_2(self):
        result = run_cli("validate", "/no/such/file.json")
        assert result.returncode == 2


class TestAssemble:
    def test_assemble_samples(self, tmp_path):
        out = tmp_path / "issue.json"
        result = run_cli(
            "assemble",
            "--report", os.path.join(REPO_ROOT, "samples", "sample_research_report.json"),
            "--curation", os.path.join(REPO_ROOT, "samples", "sample_curation.json"),
            "--out", str(out),
        )
        assert result.returncode == 0, result.stderr
        assert out.exists()

    def test_assemble_refuses_gate_failures_without_force(self, tmp_path):
        with open(os.path.join(REPO_ROOT, "samples", "sample_curation.json")) as handle:
            curation = json.load(handle)
        curation["publish_date"] = "2026-12-31"  # after every reported deadline
        bad_curation = tmp_path / "curation.json"
        with open(bad_curation, "w", encoding="utf-8") as handle:
            json.dump(curation, handle)
        out = tmp_path / "issue.json"
        result = run_cli(
            "assemble",
            "--report", os.path.join(REPO_ROOT, "samples", "sample_research_report.json"),
            "--curation", str(bad_curation),
            "--out", str(out),
        )
        assert result.returncode == 1
        assert not out.exists()
        assert "lead-time" in result.stdout

        forced = run_cli(
            "assemble",
            "--report", os.path.join(REPO_ROOT, "samples", "sample_research_report.json"),
            "--curation", str(bad_curation),
            "--out", str(out),
            "--force",
        )
        assert forced.returncode == 1  # still reports failure...
        assert out.exists()  # ...but wrote the artifact for inspection


class TestRender:
    def test_render_email(self, good_issue_json, tmp_path):
        out_dir = tmp_path / "email"
        result = run_cli("render-email", good_issue_json, "--out-dir", str(out_dir))
        assert result.returncode == 0
        with open(out_dir / "issue-001.txt", encoding="utf-8") as handle:
            assert "THE COMPLIANCE CHRONICLE" in handle.read()
        assert (out_dir / "issue-001.html").exists()

    def test_render_pdf(self, good_issue_json, tmp_path):
        out = tmp_path / "issue.pdf"
        result = run_cli("render-pdf", good_issue_json, "--out", str(out))
        assert result.returncode == 0
        with open(out, "rb") as handle:
            assert handle.read(8) == b"%PDF-1.4"

    def test_archive(self, good_issue_json, tmp_path):
        result = run_cli(
            "archive", "--issues", good_issue_json, "--out-dir", str(tmp_path / "arch")
        )
        assert result.returncode == 0
        assert (tmp_path / "arch" / "index.html").exists()


class TestBuildSample:
    def test_build_sample_end_to_end(self, tmp_path):
        result = run_cli("build-sample", "--out-dir", str(tmp_path))
        assert result.returncode == 0, result.stderr
        assert (tmp_path / "issue-001.json").exists()
        assert (tmp_path / "issue-001.txt").exists()
        assert (tmp_path / "issue-001.html").exists()
        assert (tmp_path / "archive" / "issue-001.pdf").exists()
        assert (tmp_path / "archive" / "issue-002.pdf").exists()
        assert (tmp_path / "archive" / "index.html").exists()
