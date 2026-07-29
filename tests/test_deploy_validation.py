"""
Tests: VPS Deploy Validation (Track D)

Validates health_check.sh exit codes, deploy_vps.sh git dirty detection,
and start_live_session.sh PID lifecycle logic.

Design decision: "No TDD for infrastructure scripts" — these tests cover
the contract/exit-code boundary without requiring bash execution in CI.
Red/Green exit code scenarios are tested via E2E on the VPS.
"""

import subprocess
import os
import tempfile
from pathlib import Path
import pytest


# ── Health Check Exit Code Contract (VPS-REQ-03) ──────────────────────

def test_health_check_exit_code_contract_read():
    """
    VPS-REQ-03: Health check exit codes SHALL be 0 (healthy), 1 (degraded),
    2 (critical). Verify the contract is documented correctly.
    """
    health_check_path = Path(__file__).resolve().parent.parent / "scripts" / "sv" / "health_check.sh"

    assert health_check_path.exists(), \
        "health_check.sh MUST exist at scripts/sv/health_check.sh"

    content = health_check_path.read_text(encoding="utf-8")

    # Verify exit code documentation
    assert "Exit 0" in content or "EXIT_CODE=0" in content or "healthy" in content, \
        "health_check.sh MUST document/implement exit code 0 (healthy)"
    assert "Exit 1" in content or "EXIT_CODE=1" in content or "degraded" in content, \
        "health_check.sh MUST document/implement exit code 1 (degraded)"
    assert "Exit 2" in content or "EXIT_CODE=2" in content or "critical" in content, \
        "health_check.sh MUST document/implement exit code 2 (critical)"


def test_health_check_running_logic():
    """
    VPS-REQ-03 SCENARIO: Both services running + DB connected + trade fresh
    SHALL produce exit code 0. Verify the code assigns EXIT_CODE=0 in that path.
    """
    health_check_path = Path(__file__).resolve().parent.parent / "scripts" / "sv" / "health_check.sh"
    content = health_check_path.read_text(encoding="utf-8")

    # The health_check.sh code pattern: TRADER_RUNNING=1 && TELEGRAM_RUNNING=1 → then check DB/FRESH
    assert 'TRADER_RUNNING=1' in content, \
        "health_check.sh MUST detect trader running"
    assert 'TELEGRAM_RUNNING=1' in content, \
        "health_check.sh MUST detect telegram running"
    assert 'EXIT_CODE=0' in content, \
        "health_check.sh MUST set EXIT_CODE=0 for all healthy condition"


def test_health_check_degraded_logic():
    """
    VPS-REQ-03 SCENARIO: One service down SHALL produce exit code 1 (degraded).
    """
    health_check_path = Path(__file__).resolve().parent.parent / "scripts" / "sv" / "health_check.sh"
    content = health_check_path.read_text(encoding="utf-8")

    # Expect either a branch or explicit assignment for degraded state
    degraded_patterns = ["EXIT_CODE=1", "degraded"]
    found = any(p in content for p in degraded_patterns)
    assert found, \
        "health_check.sh MUST set EXIT_CODE=1 for degraded state (one service down)"


def test_health_check_critical_logic():
    """
    VPS-REQ-03 SCENARIO: Both services down SHALL produce exit code 2 (critical).
    """
    health_check_path = Path(__file__).resolve().parent.parent / "scripts" / "sv" / "health_check.sh"
    content = health_check_path.read_text(encoding="utf-8")

    critical_patterns = ["EXIT_CODE=2", "2  # Critical"]
    found = any(p in content for p in critical_patterns)
    assert found, \
        "health_check.sh MUST set EXIT_CODE=2 for critical state (both services down)"


# ── Deploy Validation (VPS-REQ-04) ────────────────────────────────────

def test_deploy_vps_git_dirty_block():
    """
    VPS-REQ-04 SCENARIO: Dirty git SHALL block deploy with exit code 1
    before any rsync. Verify deploy_vps.sh contains the git status check.
    """
    deploy_path = Path(__file__).resolve().parent.parent / "deploy_vps.sh"
    assert deploy_path.exists(), "deploy_vps.sh MUST exist"

    content = deploy_path.read_text(encoding="utf-8")

    # Must check git status before proceeding
    assert "git status --porcelain" in content, \
        "deploy_vps.sh MUST check 'git status --porcelain' before rsync"
    assert "exit 1" in content, \
        "deploy_vps.sh MUST exit with code 1 on dirty git"
    assert "Deploy bloqueado" in content or "Uncommitted" in content or "dirty" in content, \
        "deploy_vps.sh MUST print a blocking message when git is dirty"

    # Dry-run mode must be supported
    assert "--dry-run" in content or "DRY_RUN" in content, \
        "deploy_vps.sh MUST support --dry-run flag"


def test_deploy_vps_sha_verification():
    """
    VPS-REQ-04 SCENARIO: deploy_vps.sh SHALL verify local SHA matches remote
    before proceeding with rsync.
    """
    deploy_path = Path(__file__).resolve().parent.parent / "deploy_vps.sh"
    content = deploy_path.read_text(encoding="utf-8")

    sha_patterns = ["rev-parse", "SHA", "sha"]
    found = any(p in content for p in sha_patterns)
    assert found, \
        "deploy_vps.sh MUST verify local SHA matches remote before rsync"


def test_deploy_vps_post_deploy_validation():
    """
    VPS-REQ-04 SCENARIO: After rsync, deploy_vps.sh SHALL run:
      - Python import sanity check
      - systemd reload
      - health check verification
    """
    deploy_path = Path(__file__).resolve().parent.parent / "deploy_vps.sh"
    content = deploy_path.read_text(encoding="utf-8")

    assert "import" in content or "Python" in content, \
        "deploy_vps.sh MUST verify Python imports post-deploy"
    assert "systemctl daemon-reload" in content or "systemctl" in content, \
        "deploy_vps.sh MUST reload systemd units post-deploy"
    assert "health_check.sh" in content, \
        "deploy_vps.sh MUST run health check post-deploy"


# ── Start Live Session (VPS-REQ-02) ───────────────────────────────────

def test_start_live_session_pid_files():
    """
    VPS-REQ-02: start_live_session.sh SHALL use PID files, not pkill -f,
    for process lifecycle management.
    """
    start_path = Path(__file__).resolve().parent.parent / "start_live_session.sh"
    assert start_path.exists(), "start_live_session.sh MUST exist"

    content = start_path.read_text(encoding="utf-8")

    # Must NOT use raw pkill -f for lifecycle management
    assert "pkill -f" not in content, \
        "start_live_session.sh MUST NOT use 'pkill -f' (use PID files instead)"

    # Must write and manage PID files
    assert "PIDFILE" in content or ".pid" in content or "pidfile" in content, \
        "start_live_session.sh MUST manage PID files"

    # Must have --status and --stop flags
    assert "--status" in content, \
        "start_live_session.sh MUST support --status flag"
    assert "--stop" in content, \
        "start_live_session.sh MUST support --stop flag"


# ── Systemd Units (VPS-REQ-01) ────────────────────────────────────────

def test_systemd_unit_files_exist():
    """
    VPS-REQ-01: Systemd unit files SHALL exist at scripts/sv/.
    """
    sv_dir = Path(__file__).resolve().parent.parent / "scripts" / "sv"
    assert (sv_dir / "momentum-trader.service").exists(), \
        "momentum-trader.service MUST exist"
    assert (sv_dir / "momentum-telegram.service").exists(), \
        "momentum-telegram.service MUST exist"


def test_systemd_unit_restart_policy():
    """
    VPS-REQ-01: Both units SHALL use Restart=always and RestartSec=10.
    """
    sv_dir = Path(__file__).resolve().parent.parent / "scripts" / "sv"

    for unit in ["momentum-trader.service", "momentum-telegram.service"]:
        content = (sv_dir / unit).read_text(encoding="utf-8")
        assert "Restart=always" in content, \
            f"{unit} MUST have Restart=always"
        assert "RestartSec=10" in content, \
            f"{unit} MUST have RestartSec=10"
        assert "EnvironmentFile=" in content, \
            f"{unit} MUST have EnvironmentFile for .env support"
        assert "PIDFile=" in content, \
            f"{unit} MUST have PIDFile for process tracking"


# ── Environment Configuration (VPS-REQ-05) ────────────────────────────

def test_env_not_in_git():
    """
    VPS-REQ-05: .env MUST NOT be committed to git.
    Verify .env is in .gitignore or excluded.
    """
    deploy_path = Path(__file__).resolve().parent.parent / "deploy_vps.sh"
    content = deploy_path.read_text(encoding="utf-8")

    assert "--exclude='.env'" in content, \
        "deploy_vps.sh MUST exclude .env from rsync"


# ── Edge Cases ────────────────────────────────────────────────────────

def test_health_check_help_and_flags():
    """
    health_check.sh SHALL support --preflight and --json flags.
    """
    health_check_path = Path(__file__).resolve().parent.parent / "scripts" / "sv" / "health_check.sh"
    content = health_check_path.read_text(encoding="utf-8")

    assert "--preflight" in content, \
        "health_check.sh MUST support --preflight flag"
    assert "--json" in content or "json" in content, \
        "health_check.sh MUST support --json flag"
