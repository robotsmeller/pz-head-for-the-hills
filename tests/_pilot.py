"""
Head for the Hills! - shared plumbing for the live tests.

Every test in this directory talks to a running PZ instance the same way: find
the sibling pz-test-pilot checkout, load its config, push a Lua chunk over the
file IPC, and read one string back. That boilerplate lives here so the tests
themselves are just Lua and assertions.

Not a CLI script. Imported by api_checks.py, survey_candidates.py and
verify_generator.py.
"""

import os
import sys
import time
from pathlib import Path

# Sibling checkout by default; override when pz-test-pilot lives elsewhere.
TEST_PILOT_ROOT = Path(
    os.environ.get("PZ_TEST_PILOT", Path(__file__).resolve().parents[2] / "pz-test-pilot")
)
TEST_PILOT_SCRIPTS = TEST_PILOT_ROOT / "scripts"
if not TEST_PILOT_SCRIPTS.is_dir():
    sys.exit(
        f"pz-test-pilot not found at {TEST_PILOT_ROOT}\n"
        "Set PZ_TEST_PILOT to its checkout path."
    )
sys.path.insert(0, str(TEST_PILOT_SCRIPTS))

from config import load as load_config                       # noqa: E402
from _ipc import send_command, CommandTimeout, HarnessDead   # noqa: E402

__all__ = [
    "load", "send_command", "run_lua", "payload", "flatten", "parse",
    "num", "boolean", "teleport", "CELL_LOAD_SECONDS", "TELEPORT_TOLERANCE",
    "CommandTimeout", "HarnessDead", "HarnessError",
]

# Seconds to let the cell stream in after a teleport. The harness exposes no
# wait_ticks command, so this is a plain sleep rather than a condition.
CELL_LOAD_SECONDS = 3.0

# How far from the requested square the player may land and still be measuring
# the right place.
TELEPORT_TOLERANCE = 2


class HarnessError(Exception):
    """The harness answered, but with an error or a shape we cannot read."""


def load():
    """Load the pz-test-pilot config from its own checkout."""
    return load_config(TEST_PILOT_SCRIPTS.parent / "pz-test-pilot.json")


def payload(result):
    """Pull the Lua return value out of a harness response.

    CommandRouter.dispatch answers {id, command, status, data:{result}, tick},
    so `result["result"]` never exists. Reading it with a `.get(k, result)`
    fallback is worse than a KeyError: the whole envelope comes back instead,
    and its repr still contains '=' and '|', so a parser downstream produces
    plausible nonsense rather than failing. Go through this function.
    """
    if not isinstance(result, dict):
        raise HarnessError(f"expected a response dict, got {result!r}")
    if result.get("status") != "ok":
        raise HarnessError(result.get("error") or f"harness error: {result!r}")
    data = result.get("data")
    if not isinstance(data, dict) or "result" not in data:
        raise HarnessError(f"no data.result in response: {result!r}")
    return data["result"]


def flatten(lua):
    """Collapse a Lua chunk to one line for the IPC hop.

    A `--` line comment would swallow everything after it once the newlines are
    gone, and the result still compiles, so the failure is silent: the chunk
    returns nil and looks like an empty answer rather than a bug. Use `--[[ ]]`
    block comments instead.
    """
    flat = " ".join(line.strip() for line in lua.strip().splitlines())
    if "--" in flat.replace("--[[", "").replace("]]", ""):
        raise AssertionError(
            "Lua chunk contains a '--' line comment, which flattening turns "
            "into a silent truncation. Use --[[ ]] block comments."
        )
    return flat


def run_lua(cfg, lua):
    """Flatten a chunk, run it in the game, return the string it produced."""
    return payload(send_command(cfg, "run_lua", {"code": flatten(lua)}))


def parse(text):
    """Turn 'k=v | k=v' into a dict; anything else comes back under '_raw'."""
    text = str(text)
    if "=" not in text:
        return {"_raw": text}
    fields = {}
    for chunk in text.split("|"):
        if "=" in chunk:
            k, v = chunk.strip().split("=", 1)
            fields[k.strip()] = v.strip()
    return fields


def num(fields, key):
    """A numeric field, or None when absent or non-numeric (e.g. 'ERR')."""
    try:
        return float(fields.get(key))
    except (TypeError, ValueError):
        return None


def boolean(fields, key):
    """A Lua boolean field as a Python bool, or None when it is neither."""
    value = fields.get(key)
    if value == "true":
        return True
    if value == "false":
        return False
    return None


WHERE_LUA = """
local p = getPlayer()
if not p then return "NOPLAYER" end
local s = p:getCurrentSquare()
if not s then return "NOSQUARE" end
return "player=" .. s:getX() .. "," .. s:getY()
"""


def teleport(cfg, at, settle=CELL_LOAD_SECONDS, tolerance=TELEPORT_TOLERANCE):
    """Move the player to (x, y), then confirm they actually arrived.

    Measured on B42.20: pz-test-pilot's teleport sets the position and *then*
    throws on a follow-up nil call ("Object tried to call nil in teleport"), so
    a failed status does not mean the player stayed put. Sending the command and
    never reading the reply is worse than either outcome: every scan in these
    tests is centred on the player, so silently landing somewhere else measures
    the wrong place and reports a healthy object as missing, or grades a cabin
    for reasons that have nothing to do with the map.

    Lives here rather than in one test because both callers need the identical
    guard, and a copy in each is how they drift apart.

    Returns the confirmed (x, y). Raises HarnessError if the player is not
    within `tolerance` tiles of the requested square.
    """
    x, y = at
    print(f"  teleporting to {x},{y} and waiting {settle:.0f}s for the cell")
    reply = send_command(cfg, "teleport", {"x": x, "y": y, "z": 0})
    if not isinstance(reply, dict) or reply.get("status") != "ok":
        detail = reply.get("error") if isinstance(reply, dict) else repr(reply)
        print(f"  warning: teleport reported failure ({detail}); "
              "checking where the player actually landed")
    time.sleep(settle)

    where = parse(run_lua(cfg, WHERE_LUA)).get("player", "")
    try:
        px, py = (int(part) for part in where.split(","))
    except ValueError:
        raise HarnessError("could not read the player position after "
                           f"teleporting to {x},{y} (got {where!r})")

    drift = max(abs(px - x), abs(py - y))
    if drift > tolerance:
        raise HarnessError(
            f"asked to teleport to {x},{y} but the player is at {px},{py}, "
            f"{drift} tiles away; this would measure the wrong place")
    print(f"  player at {px},{py}")
    return px, py
