"""Tests for the RecoveryManager."""

import os
import json
import subprocess
import tempfile

import pytest

from recovery_manager import RecoveryManager


@pytest.fixture
def git_repo():
    """Create a temporary git repo for testing."""
    tmp = tempfile.mkdtemp()
    subprocess.run(["git", "init"], capture_output=True, cwd=tmp)
    subprocess.run(["git", "config", "user.email", "test@test.com"], capture_output=True, cwd=tmp)
    subprocess.run(["git", "config", "user.name", "Test"], capture_output=True, cwd=tmp)
    # Initial commit
    test_file = os.path.join(tmp, "hello.py")
    with open(test_file, "w") as f:
        f.write("x = 1\n")
    subprocess.run(["git", "add", "-A"], capture_output=True, cwd=tmp)
    subprocess.run(["git", "commit", "-m", "init"], capture_output=True, cwd=tmp)
    return tmp


class TestRecoveryManager:
    def test_init_records_head(self, git_repo):
        rm = RecoveryManager(repo_path=git_repo, state_file=".test_recovery.json")
        head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=git_repo).stdout.strip()
        assert rm.last_verified_commit == head
        # Cleanup
        _cleanup(rm)

    def test_has_uncommitted_changes_true(self, git_repo):
        rm = RecoveryManager(repo_path=git_repo, state_file=".test_recovery.json")
        with open(os.path.join(git_repo, "new_file.py"), "w") as f:
            f.write("y = 2\n")
        assert rm.has_uncommitted_changes() is True
        _cleanup(rm)

    def test_record_verification_updates_head(self, git_repo):
        rm = RecoveryManager(repo_path=git_repo, state_file=".test_recovery.json")
        old_head = rm.last_verified_commit
        # Make a new commit
        with open(os.path.join(git_repo, "v2.py"), "w") as f:
            f.write("v2\n")
        subprocess.run(["git", "add", "-A"], capture_output=True, cwd=git_repo)
        subprocess.run(["git", "commit", "-m", "v2"], capture_output=True, cwd=git_repo)
        rm.record_verification()
        assert rm.last_verified_commit != old_head
        _cleanup(rm)

    def test_rollback_restores_verified_state(self, git_repo):
        rm = RecoveryManager(repo_path=git_repo, state_file=".test_recovery.json")
        original_head = rm.last_verified_commit
        # Make an uncommitted change
        with open(os.path.join(git_repo, "hello.py"), "w") as f:
            f.write("x = 999\n")
        # Rollback
        result = rm.rollback(reason="test")
        assert result["success"] is True
        assert result["commit"] == original_head
        # Verify file content restored
        with open(os.path.join(git_repo, "hello.py")) as f:
            content = f.read()
        assert content.strip() == "x = 1"
        _cleanup(rm)

    def test_get_status(self, git_repo):
        rm = RecoveryManager(repo_path=git_repo, state_file=".test_recovery.json")
        status = rm.get_status()
        assert "last_verified_commit" in status
        assert "has_uncommitted_changes" in status
        _cleanup(rm)


def _cleanup(rm):
    sf = rm.state_file
    if os.path.exists(sf):
        os.remove(sf)
