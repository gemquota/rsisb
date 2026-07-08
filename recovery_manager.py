"""RecoveryManager — git-based rollback on test failure.

Monitors the last verified commit and executes git checkout to return
the project state to that commit when a test failure is detected.
"""

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Optional


class RecoveryManager:
    """Manages git-based rollback to the last verified commit.

    On initialization, records the current HEAD as the last verified commit.
    On rollback(), performs git checkout --hard to that commit.
    """

    def __init__(self, repo_path: Optional[str] = None, state_file: str = ".recovery_state.json"):
        self.repo_path = repo_path or os.getcwd()
        self.state_file = os.path.join(self.repo_path, state_file)
        self._ensure_git_repo()
        self._load_or_init_state()

    def _ensure_git_repo(self):
        """Verify the path is inside a git repository."""
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True, text=True, cwd=self.repo_path,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Not a git repository: {self.repo_path}")

    def _load_or_init_state(self):
        """Load state from file or initialize with current HEAD."""
        if os.path.exists(self.state_file):
            with open(self.state_file) as f:
                data = json.load(f)
            self.last_verified_commit = data.get("last_verified_commit", "")
            self.last_verified_at = data.get("last_verified_at", 0.0)
        else:
            self.last_verified_commit = self._get_current_head()
            self.last_verified_at = time.time()
            self._save_state()

    def _get_current_head(self) -> str:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=self.repo_path,
        )
        if result.returncode != 0:
            raise RuntimeError("Failed to get current HEAD")
        return result.stdout.strip()

    def _save_state(self):
        data = {
            "last_verified_commit": self.last_verified_commit,
            "last_verified_at": self.last_verified_at,
        }
        with open(self.state_file, "w") as f:
            json.dump(data, f, indent=2)

    def record_verification(self):
        """Record the current HEAD as the last verified commit."""
        self.last_verified_commit = self._get_current_head()
        self.last_verified_at = time.time()
        self._save_state()

    def get_uncommitted_changes(self) -> list[str]:
        """Return list of files with uncommitted changes."""
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=self.repo_path,
        )
        if result.returncode != 0:
            raise RuntimeError("Failed to check git status")
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        return lines

    def has_uncommitted_changes(self) -> bool:
        return len(self.get_uncommitted_changes()) > 0

    def rollback(self, reason: str = "") -> dict:
        """Rollback to the last verified commit using git checkout.

        Returns a dict describing the rollback result.
        """
        if not self.last_verified_commit:
            raise RuntimeError("No verified commit to rollback to")

        timestamp = time.time()

        # Stash any in-progress changes first
        subprocess.run(
            ["git", "stash", "--include-untracked"],
            capture_output=True, text=True, cwd=self.repo_path,
        )

        # Hard reset to last verified commit
        result = subprocess.run(
            ["git", "checkout", "--force", self.last_verified_commit],
            capture_output=True, text=True, cwd=self.repo_path,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Rollback failed: {result.stderr}")

        outcome = {
            "action": "rollback",
            "commit": self.last_verified_commit,
            "timestamp": timestamp,
            "reason": reason,
            "success": True,
        }
        return outcome

    def get_status(self) -> dict:
        """Return current recovery manager status."""
        return {
            "last_verified_commit": self.last_verified_commit,
            "last_verified_at": self.last_verified_at,
            "has_uncommitted_changes": self.has_uncommitted_changes(),
            "uncommitted_files": self.get_uncommitted_changes(),
        }
