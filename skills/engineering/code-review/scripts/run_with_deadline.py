#!/usr/bin/env python3
"""Run one reviewer in a bounded process group and record its status."""

from __future__ import annotations

import argparse
import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import BinaryIO

TIMEOUT_EXIT_CODE = 124
CLEANUP_ERROR_EXIT_CODE = 125
SPAWN_ERROR_EXIT_CODE = 127


class _SupervisorSignal(Exception):
    def __init__(self, signum: int) -> None:
        super().__init__(signum)
        self.signum = signum


def _write_status(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        Path(temporary).unlink(missing_ok=True)
        raise


def _group_exists(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Darwin can transiently return EPERM for a group that just vanished.
        # Resolve the ambiguity with a bounded process-table check; any failure
        # remains fail-closed.
        try:
            completed = subprocess.run(
                ["ps", "-ax", "-o", "pgid="],
                capture_output=True,
                timeout=0.5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return True
        if completed.returncode != 0:
            return True
        groups = {
            int(value)
            for value in completed.stdout.split()
            if value.isdigit()
        }
        return process_group_id in groups


def _terminate_group(process: subprocess.Popen[bytes], grace_seconds: float) -> bool:
    """Terminate the supervised process group without any unbounded wait."""
    process_group_id = process.pid
    if _group_exists(process_group_id):
        try:
            os.killpg(process_group_id, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError:
            pass

    deadline = time.monotonic() + grace_seconds
    while _group_exists(process_group_id) and time.monotonic() < deadline:
        time.sleep(min(0.05, max(deadline - time.monotonic(), 0.0)))

    if _group_exists(process_group_id):
        try:
            os.killpg(process_group_id, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            pass

    reaped = False
    reap_timeout = max(min(grace_seconds, 1.0), 0.1)
    try:
        process.wait(timeout=reap_timeout)
        reaped = True
    except subprocess.TimeoutExpired:
        try:
            os.kill(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            pass
        try:
            process.wait(timeout=0.5)
            reaped = True
        except subprocess.TimeoutExpired:
            pass

    group_deadline = time.monotonic() + 2.0
    while _group_exists(process_group_id) and time.monotonic() < group_deadline:
        time.sleep(0.05)
    group_alive = _group_exists(process_group_id)
    # A transient EPERM during signalling is harmless only if the bounded
    # process-table verification proves the group no longer exists.
    return reaped and not group_alive


def _open_output(path: Path | None) -> BinaryIO | None:
    if path is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    return os.fdopen(descriptor, "wb")


def run(
    *,
    name: str,
    command: list[str],
    timeout_seconds: float,
    grace_seconds: float,
    progress_seconds: float,
    status_file: Path,
    stdout_file: Path | None = None,
    stderr_file: Path | None = None,
) -> int:
    started = time.monotonic()
    stdout_handle = _open_output(stdout_file)
    stderr_handle = _open_output(stderr_file)
    supervised_signals = {signal.SIGINT, signal.SIGTERM, signal.SIGHUP}
    old_mask = signal.pthread_sigmask(signal.SIG_BLOCK, supervised_signals)
    old_handlers: dict[signal.Signals, object] = {}
    process: subprocess.Popen[bytes] | None = None
    pending_error: BaseException | None = None
    state = "supervisor_error"
    timed_out = False
    cleanup_succeeded = True
    return_code = 1

    def handle_signal(signum: int, _frame: object) -> None:
        raise _SupervisorSignal(signum)

    try:
        old_handlers = {
            signum: signal.signal(signum, handle_signal)
            for signum in supervised_signals
        }
        print(
            f"reviewer={name} state=starting deadline_seconds={timeout_seconds:g}",
            file=sys.stderr,
            flush=True,
        )
        try:
            process = subprocess.Popen(
                command,
                start_new_session=True,
                stdout=stdout_handle,
                stderr=stderr_handle,
                # Close the supervisor's spawn race without forcing reviewers
                # to inherit blocked shutdown signals.
                preexec_fn=lambda: signal.pthread_sigmask(
                    signal.SIG_SETMASK, old_mask
                ),
            )
        except OSError as exc:
            state = "spawn_error"
            return_code = SPAWN_ERROR_EXIT_CODE
            print(
                f"reviewer={name} state=spawn_error error={type(exc).__name__}",
                file=sys.stderr,
                flush=True,
            )
        else:
            _write_status(
                status_file,
                {
                    "cleanupSucceeded": None,
                    "elapsedSeconds": 0.0,
                    "name": name,
                    "returnCode": None,
                    "state": "running",
                    "timedOut": False,
                },
            )
            print(f"reviewer={name} state=running", file=sys.stderr, flush=True)
            # Any signal received since the pre-spawn block is delivered only
            # after the process handle and handlers both exist.
            signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
            deadline = started + timeout_seconds
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout_seconds)
                try:
                    return_code = process.wait(
                        timeout=min(progress_seconds, remaining)
                    )
                    state = "completed"
                    break
                except subprocess.TimeoutExpired:
                    elapsed = time.monotonic() - started
                    if elapsed >= timeout_seconds:
                        raise
                    print(
                        f"reviewer={name} state=running elapsed_seconds={elapsed:.1f}",
                        file=sys.stderr,
                        flush=True,
                    )
    except subprocess.TimeoutExpired:
        timed_out = True
        state = "timed_out"
        return_code = TIMEOUT_EXIT_CODE
    except _SupervisorSignal as exc:
        state = "interrupted"
        return_code = 128 + exc.signum
    except KeyboardInterrupt:
        state = "interrupted"
        return_code = 128 + signal.SIGINT
    except BaseException as exc:
        state = "supervisor_error"
        pending_error = exc
        return_code = 1
    finally:
        # One unconditional cleanup path covers normal completion, timeout,
        # signals arriving inside exception handlers, and status/output errors.
        signal.pthread_sigmask(signal.SIG_BLOCK, supervised_signals)
        finalization_error: BaseException | None = None
        try:
            if process is not None:
                try:
                    cleanup_succeeded = _terminate_group(process, grace_seconds)
                except BaseException as exc:
                    cleanup_succeeded = False
                    finalization_error = exc
                if not cleanup_succeeded:
                    state = "cleanup_error"
                    return_code = CLEANUP_ERROR_EXIT_CODE
            for handle in (stdout_handle, stderr_handle):
                if handle is None:
                    continue
                try:
                    handle.close()
                except BaseException as exc:
                    if finalization_error is None:
                        finalization_error = exc
                    if cleanup_succeeded:
                        state = "supervisor_error"
                        return_code = 1
            elapsed = round(time.monotonic() - started, 3)
            try:
                _write_status(
                    status_file,
                    {
                        "cleanupSucceeded": cleanup_succeeded,
                        "elapsedSeconds": elapsed,
                        "name": name,
                        "returnCode": return_code,
                        "state": state,
                        "timedOut": timed_out,
                    },
                )
                print(
                    f"reviewer={name} state={state} return_code={return_code} "
                    f"elapsed_seconds={elapsed:g} cleanup_succeeded="
                    f"{str(cleanup_succeeded).lower()}",
                    file=sys.stderr,
                    flush=True,
                )
            except BaseException as exc:
                if finalization_error is None:
                    finalization_error = exc
        finally:
            # Coalesce any shutdown signal that arrived during finalization.
            # Otherwise restoring a default handler before unblocking could
            # overwrite the recorded status/exit contract with signal death.
            for signum in supervised_signals:
                signal.signal(signum, signal.SIG_IGN)
            signal.pthread_sigmask(signal.SIG_UNBLOCK, supervised_signals)
            for signum, handler in old_handlers.items():
                signal.signal(signum, handler)
            signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
        if not cleanup_succeeded:
            # An unverified process-group teardown is the primary failure and
            # must match the recorded cleanup_error/125 status.
            pending_error = None
        elif pending_error is None and finalization_error is not None:
            pending_error = finalization_error

    if pending_error is not None:
        raise pending_error
    return return_code


def _finite_positive(parser: argparse.ArgumentParser, name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0:
        parser.error(f"{name} must be finite and positive")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--timeout-seconds", required=True, type=float)
    parser.add_argument("--grace-seconds", type=float, default=10.0)
    parser.add_argument("--progress-seconds", type=float, default=120.0)
    parser.add_argument("--status-file", required=True, type=Path)
    parser.add_argument("--stdout-file", type=Path)
    parser.add_argument("--stderr-file", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required after --")
    _finite_positive(parser, "timeout", args.timeout_seconds)
    _finite_positive(parser, "progress interval", args.progress_seconds)
    if not math.isfinite(args.grace_seconds) or args.grace_seconds < 0:
        parser.error("grace must be finite and non-negative")
    return run(
        name=args.name,
        command=command,
        timeout_seconds=args.timeout_seconds,
        grace_seconds=args.grace_seconds,
        progress_seconds=args.progress_seconds,
        status_file=args.status_file,
        stdout_file=args.stdout_file,
        stderr_file=args.stderr_file,
    )


if __name__ == "__main__":
    raise SystemExit(main())
