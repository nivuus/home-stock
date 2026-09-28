#!/usr/bin/env python3
"""Activate phase of home-stock: make a running Home Assistant load this version.

The install phase lays the integration's files in the configuration
directory. Home Assistant only imports a custom integration at startup, so a
Home Assistant that was already running keeps executing the PREVIOUS version
until it restarts - an update that is laid but not in effect.

So this phase restarts the `homeassistant` container, and only when it is
running. Every other outcome is stated, none is an error:

  - no such container, or no Docker daemon: Home Assistant is not running
    here, and it will load this version whenever it starts;
  - container present but stopped: someone stopped it on purpose, and this
    phase does not start what it did not stop.

At first boot this runs next to home-manager's own activate, which starts the
stack: the container is then absent (nothing to do) or just started (one
extra restart, harmless). Any other Docker failure is raised, not swallowed.
"""
import argparse
import json
import subprocess
import sys

# The container name home-manager's compose file gives Home Assistant.
CONTAINER = "homeassistant"


def emit(event):
    print(json.dumps(event), flush=True)


def container_running():
    """True, False, or None when no container / no daemon exists to ask."""
    try:
        proc = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", CONTAINER],
            capture_output=True, text=True)
    except FileNotFoundError:
        return None
    if proc.returncode == 0:
        return proc.stdout.strip() == "true"
    detail = proc.stderr.strip()
    if "No such object" in detail or "Cannot connect to the Docker daemon" in detail:
        return None
    raise RuntimeError(f"docker inspect {CONTAINER} failed: {detail}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True)
    parser.add_argument("--root", default="/")
    parser.parse_args()
    json.load(sys.stdin)          # the context is read; nothing here needs it

    try:
        running = container_running()
    except RuntimeError as exc:
        print(f"home-stock activate: {exc}", file=sys.stderr)
        return 1

    if running is None:
        emit({"event": "progress", "pct": 100,
              "msg": "Home Assistant is not running here; it will load this "
                     "version when it starts"})
    elif not running:
        emit({"event": "progress", "pct": 100,
              "msg": f"container {CONTAINER} is stopped and left stopped; it "
                     "will load this version when it is started"})
    else:
        emit({"event": "progress", "pct": 50,
              "msg": "Restarting Home Assistant to load this version"})
        proc = subprocess.run(["docker", "restart", CONTAINER],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"home-stock activate: docker restart {CONTAINER} failed: "
                  f"{proc.stderr.strip()}", file=sys.stderr)
            return 1
    emit({"event": "done"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
