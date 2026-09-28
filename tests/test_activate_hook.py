#!/usr/bin/env python3
"""Tests for hooks/activate.py, against a fake `docker` on PATH.

The fake records every call and answers `docker inspect` the way the real
one does in each situation the hook must tell apart.

Run: python3 tests/test_activate_hook.py
"""
import json
import os
import pathlib
import stat
import subprocess
import sys
import tempfile

HOOK = pathlib.Path(__file__).resolve().parents[1] / "hooks" / "activate.py"
FAKE = """#!/bin/sh
echo "$*" >> "$DOCKER_CALLS"
case "$1" in
  inspect) printf '%s' "$INSPECT_OUT"; printf '%s' "$INSPECT_ERR" >&2; exit "$INSPECT_RC" ;;
  restart) exit "$RESTART_RC" ;;
esac
"""

failures = []


def check(label, got, want):
    if got != want:
        failures.append(f"{label}: got {got!r}, want {want!r}")


def run(tmp, *, inspect_out="", inspect_err="", inspect_rc=0, restart_rc=0,
        with_docker=True):
    bindir = os.path.join(tmp, "bin")
    os.makedirs(bindir, exist_ok=True)
    fake = os.path.join(bindir, "docker")
    if with_docker:
        with open(fake, "w") as fh:
            fh.write(FAKE)
        os.chmod(fake, stat.S_IRWXU)
    elif os.path.exists(fake):
        os.unlink(fake)
    calls = os.path.join(tmp, "calls")
    if os.path.exists(calls):
        os.unlink(calls)
    env = dict(os.environ, PATH=bindir, DOCKER_CALLS=calls,
               INSPECT_OUT=inspect_out, INSPECT_ERR=inspect_err,
               INSPECT_RC=str(inspect_rc), RESTART_RC=str(restart_rc))
    proc = subprocess.run([sys.executable, str(HOOK), "--phase", "activate"],
                          input=json.dumps({"package": {}, "hw": {}, "answers": {}}),
                          env=env, capture_output=True, text=True)
    made = open(calls).read().splitlines() if os.path.exists(calls) else []
    return proc.returncode, made, proc.stdout, proc.stderr


with tempfile.TemporaryDirectory() as tmp:
    code, calls, _, _ = run(tmp, inspect_out="true\n")
    check("a running Home Assistant is restarted",
          (code, calls), (0, ["inspect -f {{.State.Running}} homeassistant",
                              "restart homeassistant"]))

    code, calls, out, _ = run(tmp, inspect_out="false\n")
    check("a stopped container is left stopped", (code, len(calls)), (0, 1))
    check("and the hook says so", "left stopped" in out, True)

    code, calls, out, _ = run(tmp, inspect_rc=1,
                              inspect_err="Error: No such object: homeassistant")
    check("no container: nothing to restart", (code, len(calls)), (0, 1))
    check("stated, not silent", "not running here" in out, True)

    code, calls, _, _ = run(tmp, inspect_rc=1, inspect_err=(
        "Cannot connect to the Docker daemon at unix:///var/run/docker.sock."))
    check("no daemon: nothing to restart", (code, len(calls)), (0, 1))

    code, calls, _, _ = run(tmp, with_docker=False)
    check("no docker at all: nothing to restart", (code, calls), (0, []))

    code, _, _, err = run(tmp, inspect_rc=1, inspect_err="permission denied")
    check("an unexpected docker failure is raised", code, 1)
    check("with docker's own message", "permission denied" in err, True)

    code, _, _, err = run(tmp, inspect_out="true\n", restart_rc=1)
    check("a failed restart fails the phase", code, 1)


if failures:
    print(f"FAIL ({len(failures)})")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("OK - all activate hook tests passed")
