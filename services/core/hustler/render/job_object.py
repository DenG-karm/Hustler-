"""Windows Job Object: Python ölürse (crash/kill) çocuk süreçleri (ffmpeg) de ölür.

Tek bir süreç-geneli job kullanılır; handle süreç ömrü boyunca açık tutulur.
Python süreci kapanınca handle kapanır ve JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
job'daki tüm süreçleri öldürür. Yalnızca public Win32 API (ctypes) kullanılır.
"""

import sys
import threading

import structlog

logger = structlog.get_logger()

_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
_PROCESS_SET_QUOTA = 0x0100
_PROCESS_TERMINATE = 0x0001

_lock = threading.Lock()
_job_handle: int | None = None
_job_failed = False


def _create_job() -> int | None:
    import ctypes
    from ctypes import wintypes

    class _BasicLimits(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _IoCounters(ctypes.Structure):
        _fields_ = [(n, ctypes.c_uint64) for n in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
        )]

    class _ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimits),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
    ]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    handle = kernel32.CreateJobObjectW(None, None)
    if not handle:
        logger.warning("job_object_create_failed", error=ctypes.get_last_error())
        return None

    info = _ExtendedLimits()
    info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    ok = kernel32.SetInformationJobObject(
        handle,
        _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
        ctypes.byref(info),
        ctypes.sizeof(info),
    )
    if not ok:
        logger.warning("job_object_configure_failed", error=ctypes.get_last_error())
        kernel32.CloseHandle(handle)
        return None
    return int(handle)


def _get_job() -> int | None:
    global _job_handle, _job_failed
    with _lock:
        if _job_handle is None and not _job_failed:
            _job_handle = _create_job()
            _job_failed = _job_handle is None
        return _job_handle


def bind_pid_to_kill_on_close_job(pid: int) -> bool:
    """pid'i job'a bağlar. Başarısızlık ölümcül değildir: False döner ve uyarı loglar."""
    if sys.platform != "win32":
        return False

    import ctypes
    from ctypes import wintypes

    job = _get_job()
    if job is None:
        return False

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    process = kernel32.OpenProcess(_PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, pid)
    if not process:
        logger.warning("job_object_open_process_failed", pid=pid, error=ctypes.get_last_error())
        return False
    try:
        if not kernel32.AssignProcessToJobObject(job, process):
            logger.warning("job_object_assign_failed", pid=pid, error=ctypes.get_last_error())
            return False
        return True
    finally:
        kernel32.CloseHandle(process)
