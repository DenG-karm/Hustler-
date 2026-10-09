"""doctor.py: biçimleme, dizin boyutu ve rapor; yalnızca nvidia-smi alt süreci / PATH sahte."""

import shutil
import subprocess
from pathlib import Path

import colorama
import pytest

from services.core.hustler import doctor


@pytest.mark.parametrize(
    ("size", "text"),
    [
        (0, "0.00 B"),
        (1023, "1023.00 B"),
        (1024, "1.00 KB"),
        (1536, "1.50 KB"),
        (1024**2, "1.00 MB"),
        (1024**3 * 5, "5.00 GB"),
        (1024**4, "1.00 TB"),
        (1024**5, "1.00 PB"),
    ],
)
def test_format_size(size: float, text: str) -> None:
    assert doctor.format_size(size) == text


def test_dir_size_sums_nested_files_only(tmp_path: Path) -> None:
    (tmp_path / "a.bin").write_bytes(b"x" * 10)
    (tmp_path / "sub" / "deep").mkdir(parents=True)
    (tmp_path / "sub" / "deep" / "b.bin").write_bytes(b"y" * 5)

    assert doctor.get_dir_size(tmp_path) == 15


def test_dir_size_of_missing_dir_is_zero(tmp_path: Path) -> None:
    assert doctor.get_dir_size(tmp_path / "yok") == 0


def test_check_ffmpeg_found_and_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: r"C:\bin\ffmpeg.exe")
    assert "Bulundu" in doctor.check_ffmpeg()
    assert r"C:\bin\ffmpeg.exe" in doctor.check_ffmpeg()

    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert "Bulunamadı" in doctor.check_ffmpeg()


def _run(code: int, out: str) -> object:
    def fake(*a: object, **k: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(["nvidia-smi"], code, stdout=out)

    return fake


def test_check_cuda_reports_third_line_of_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subprocess, "run", _run(0, "l0\nl1\n  Driver 555  \nl3"))

    assert "Driver 555" in doctor.check_cuda()


def test_check_cuda_short_output_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", _run(0, "tek"))

    assert "Erişilebilir" in doctor.check_cuda()


def test_check_cuda_nonzero_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", _run(9, ""))

    assert "Kod: 9" in doctor.check_cuda()


def test_check_cuda_missing_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a: object, **k: object) -> None:
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", boom)

    assert "bulunamadı" in doctor.check_cuda()


def test_run_doctor_reports_existing_db_and_runs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pkg").mkdir()
    monkeypatch.setattr(doctor, "__file__", str(tmp_path / "pkg" / "doctor.py"))
    monkeypatch.setattr(shutil, "which", lambda n: None)
    monkeypatch.setattr(subprocess, "run", _run(9, ""))
    monkeypatch.setattr(colorama, "init", lambda: None)
    (tmp_path / "hustler.db").write_bytes(b"d" * 2048)
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / "r.bin").write_bytes(b"r" * 1024)

    doctor.run_doctor()

    out = capsys.readouterr().out
    assert "Hustler Doctor - Sistem Tanılama Raporu" in out
    assert "2.00 KB" in out and "1.00 KB" in out
    assert "Henüz oluşturulmamış" not in out
    assert out.rstrip().endswith("Tanılama tamamlandı.")


def test_run_doctor_reports_missing_db_and_runs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pkg").mkdir()
    monkeypatch.setattr(doctor, "__file__", str(tmp_path / "pkg" / "doctor.py"))
    monkeypatch.setattr(shutil, "which", lambda n: "ffmpeg")
    monkeypatch.setattr(subprocess, "run", _run(0, "a\nb\nc"))
    monkeypatch.setattr(colorama, "init", lambda: None)

    doctor.run_doctor()

    out = capsys.readouterr().out
    assert out.count("Henüz oluşturulmamış") == 2
    assert "Bulundu" in out
