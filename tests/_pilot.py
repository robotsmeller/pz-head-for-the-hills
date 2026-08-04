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
    "num", "boolean", "teleport", "snapshot_options", "restore_options",
    "CELL_LOAD_SECONDS", "TELEPORT_TOLERANCE",
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


# Move the player with the game's own teleportTo, measured live on B42.20.
#
# setX/setY does NOT work and fails in the most misleading way available: the
# call takes, getX() reads back the new coordinates immediately, and about a
# second later the character is back where they started. The square never
# changes at all, because the destination chunk is not loaded and nothing about
# setting a coordinate asks for it to be. teleportTo streams the chunk in and
# the square follows within a second.
#
# setLx/setLy do not exist on B42's player at all (type() reads nil), so the
# field-test below is not defensive habit - calling them throws.
MOVE_LUA = """
local X, Y = %d, %d
local p = getPlayer()
if not p then return "NOPLAYER" end
if not p.teleportTo then return "NOTELEPORTTO" end
p:teleportTo(X, Y, 0)
return "moved=true"
"""


def teleport(cfg, at, settle=CELL_LOAD_SECONDS, tolerance=TELEPORT_TOLERANCE):
    """Move the player to (x, y), then confirm they actually arrived.

    Does not use pz-test-pilot's `teleport` command. Measured on B42.20, a live
    12-hop run: every call answered "Object tried to call nil in teleport
    java.lang.RuntimeException" and the player did not move at all, staying on
    the same square for all twelve. An earlier reading of that failure had it
    moving the player first and throwing afterwards; the survey run disproved
    that. Either way the command is unusable, so this sets the position through
    run_lua instead.

    The confirmation stays regardless of how the move is issued. Every scan in
    these tests is centred on the player, so a hop that silently fails measures
    the wrong place: it reports a healthy object as missing, or grades a cabin
    on ground belonging to somewhere else entirely.

    Lives here rather than in one test because both callers need the identical
    guard, and a copy in each is how they drift apart.

    Returns the confirmed (x, y). Raises HarnessError if the player is not
    within `tolerance` tiles of the requested square.
    """
    x, y = at
    print(f"  moving to {x},{y} and waiting {settle:.0f}s for the cell")
    moved = parse(run_lua(cfg, MOVE_LUA % (x, y)))
    if moved.get("moved") != "true":
        raise HarnessError(f"could not move the player to {x},{y}: "
                           f"{moved.get('_raw', moved)}")
    time.sleep(settle)

    where = parse(run_lua(cfg, WHERE_LUA)).get("player", "")
    try:
        px, py = (int(part) for part in where.split(","))
    except ValueError:
        raise HarnessError("could not read the player position after "
                           f"moving to {x},{y} (got {where!r})")

    drift = max(abs(px - x), abs(py - y))
    if drift > tolerance:
        raise HarnessError(
            f"asked to move to {x},{y} but the player is at {px},{py}, "
            f"{drift} tiles away; this would measure the wrong place")
    print(f"  player at {px},{py}")
    return px, py


# A test that re-fires OnNewGame has to arm the sandbox vars first, and the
# arming is a write to whatever save happens to be loaded. verify_generator.py
# tells you in its docstring to only run it in a throwaway world, which is a
# rule a person has to remember at the wrong moment. These two turn that into
# something the test does for itself.
DUMP_OPTIONS_LUA = """
local sv = SandboxVars and SandboxVars.HeadForTheHills
if not sv then return "NOOPTIONS" end
local keys = {}
for k in pairs(sv) do table.insert(keys, k) end
table.sort(keys)
local out = {}
for _, k in ipairs(keys) do table.insert(out, k .. "=" .. tostring(sv[k])) end
return table.concat(out, " | ")
"""


def _lua_literal(text):
    """A dumped value as Lua source: booleans and numbers bare, the rest quoted."""
    if text in ("true", "false", "nil"):
        return text
    try:
        float(text)
        return text
    except ValueError:
        return '"%s"' % text.replace("\\", "\\\\").replace('"', '\\"')


def snapshot_options(cfg):
    """Every HeadForTheHills sandbox var as a dict, for restore_options."""
    fields = parse(run_lua(cfg, DUMP_OPTIONS_LUA))
    if "_raw" in fields:
        raise HarnessError(
            "could not read SandboxVars.HeadForTheHills (got "
            f"{fields['_raw']!r}); the mod may not be loaded in this save")
    return fields


def restore_options(cfg, snapshot):
    """Put a snapshot back, then read it again and prove it took.

    Verifying the write matters more here than it looks: this runs at the end
    of a destructive test, which is exactly when nobody is watching the output.
    A silent failure would leave someone's save rewritten.
    """
    assignments = " ".join(
        "sv.%s = %s" % (key, _lua_literal(value))
        for key, value in snapshot.items())
    lua = ("local sv = SandboxVars and SandboxVars.HeadForTheHills "
           "if not sv then return \"NOOPTIONS\" end "
           "%s return \"restored\"" % assignments)
    if "restored" not in str(run_lua(cfg, lua)):
        raise HarnessError("could not restore the sandbox vars")

    after = snapshot_options(cfg)
    drifted = [k for k, v in snapshot.items() if after.get(k) != v]
    if drifted:
        raise HarnessError(
            "sandbox vars did not come back as they were: "
            + ", ".join("%s is %s, expected %s" % (k, after.get(k), snapshot[k])
                        for k in drifted))
    print("  sandbox vars restored")
