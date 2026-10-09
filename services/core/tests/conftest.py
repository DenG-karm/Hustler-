"""Test politikası: CI'da (HUSTLER_CI=1) skip = kırmızı; gerçek ffmpeg gerektiren testler ffmpeg yoksa FAIL."""

import os
import shutil

import pytest

_CI = os.environ.get("HUSTLER_CI") == "1"
_skipped: list[str] = []


@pytest.fixture(autouse=True)
def _require_ffmpeg(request: pytest.FixtureRequest) -> None:
    if request.node.get_closest_marker("ffmpeg") and shutil.which("ffmpeg") is None:
        pytest.fail("ffmpeg PATH'te yok; bu test gerçek ffmpeg gerektirir (skip edilmez).", pytrace=False)


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    # xfail de 'skipped' olarak raporlanır; ikisi de CI'da yasak.
    if _CI and report.skipped:
        _skipped.append(report.nodeid)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if _CI and _skipped:
        writer = session.config.get_terminal_writer()
        writer.line(f"\nHUSTLER_CI=1: {len(_skipped)} test atlandı (skip/xfail yasak):", red=True)
        for node_id in _skipped:
            writer.line(f"  - {node_id}", red=True)
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
