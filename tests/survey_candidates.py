"""
Head for the Hills! - candidate cabin survey (issue #1).

Teleports a running game to each shortlisted coordinate and reports whether
`SpawnScenario.lua` would actually succeed there. The point is to cut 12
candidates down to 2-3 without eyeballing each one on map.projectzomboid.com and
guessing.

The Lua below deliberately mirrors the mod's own predicates (`isOpenGround`,
`blocksDoorway`, `hasClearance`, the well sprite, the search radii). If those
change in SpawnScenario.lua, change them here too, otherwise the survey answers
a question the mod is no longer asking.

**Run this in a throwaway world.** It teleports the player around the map.

Requires: PZ running, a save loaded (the harness registers on OnGameStart), and
the PZTestPilot mod enabled.

    python tests/survey_candidates.py

Note: pz-test-pilot reports `harness_dead` whenever PZ is unfocused, because its
heartbeat counts in-game ticks and the clock stops. Keep the game window in the
foreground, or read Zomboid/Lua/TestPilot/result.txt directly.
"""

import os
import sys
import time
from pathlib import Path

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

from config import load as load_config          # noqa: E402
from _ipc import send_command, CommandTimeout, HarnessDead  # noqa: E402


# Issue #1 shortlist, session 2. #4 is the only known existing-well test case.
CANDIDATES = [
    (1, 12472, 8912, ""),
    (2, 12730, 8749, ""),
    (3, 13633, 7232, ""),
    (4, 9668, 8782, "has a well already"),
    (5, 9046, 8740, ""),
    (6, 6114, 8052, ""),
    (7, 4240, 7234, ""),
    (8, 2171, 11218, "far corner, may be too remote"),
    (9, 6489, 6166, ""),
    (10, 8066, 7622, ""),
    (11, 9497, 6620, ""),
    (12, 14058, 5198, "far corner, may be too remote"),
]

# Seconds to let the cell stream in after a teleport. The harness has no
# wait_ticks command exposed, so this is a plain sleep rather than a condition.
CELL_LOAD_SECONDS = 3.0

# Kept in step with SpawnScenario.lua.
SURVEY_LUA = """
local X, Y, Z = %d, %d, 0
local out = {}
local function add(k, v) table.insert(out, k .. "=" .. tostring(v)) end

local centre = getSquare(X, Y, Z)
if not centre then return "UNLOADED" end

local function isOpenGround(s)
    return s:isOutside() and s:getBuilding() == nil and s:isFree(false)
end
local function blocksDoorway(s)
    local x, y, z = s:getX(), s:getY(), s:getZ()
    for dx = -1, 1 do for dy = -1, 1 do
        local n = getSquare(x+dx, y+dy, z)
        if n then
            local o = n:getObjects()
            for i = 0, o:size() - 1 do
                if instanceof(o:get(i), "IsoDoor") then return true end
                local d = false
                pcall(function() d = o:get(i):isDoor() end)
                if d then return true end
            end
        end
    end end
    return false
end
local function hasClearance(s, margin)
    if margin <= 0 then return true end
    local x, y, z = s:getX(), s:getY(), s:getZ()
    for dx = -margin, margin do for dy = -margin, margin do
        local n = getSquare(x+dx, y+dy, z)
        if not n or not isOpenGround(n) then return false end
    end end
    return true
end
local function findSquare(minR, maxR, accept)
    for r = minR, maxR do
        for dx = -r, r do for dy = -r, r do
            if math.abs(dx) == r or math.abs(dy) == r then
                local s = getSquare(X+dx, Y+dy, Z)
                if s and accept(s) then return s end
            end
        end end
    end
    return nil
end

--[[ 1. Is there actually a building here? ]]
local building = centre:getBuilding()
add("building", building ~= nil)
if building then
    pcall(function()
        local d = building:getDef()
        add("rooms", d:getRooms():size())
        add("area", d:getW() * d:getH())
    end)
end

--[[ 3. Existing water source / generator, using the mod's own detection. ]]
local WELL_SPRITES = { ["camping_01_16"] = true }
local well, gen = false, false
for dx = -12, 12 do for dy = -12, 12 do
    local s = getSquare(X+dx, Y+dy, Z)
    if s then
        local o = s:getObjects()
        for i = 0, o:size() - 1 do
            local ob = o:get(i)
            local sp = ob:getSprite()
            local nm = sp and sp:getName()
            if nm and WELL_SPRITES[nm] then well = true end
            if not well then
                local ok, fc = pcall(function() return ob:getFluidContainer() end)
                if ok and fc ~= nil then well = true end
            end
            if instanceof(ob, "IsoGenerator") then gen = true end
        end
    end
end end
add("existingWell", well)
add("existingGenerator", gen)

--[[ 4. Would placement succeed? Same radii and clearances as the mod. ]]
local roomy = findSquare(6, 16, function(s)
    return isOpenGround(s) and hasClearance(s, 2) and not blocksDoorway(s)
end)
local tight = findSquare(6, 16, function(s)
    return isOpenGround(s) and hasClearance(s, 1) and not blocksDoorway(s)
end)
local objectSpot = findSquare(2, 10, function(s)
    return isOpenGround(s) and not blocksDoorway(s)
end)
add("vehicleRoomy", roomy ~= nil)
add("vehicleTight", tight ~= nil)
add("objectSpot", objectSpot ~= nil)

return table.concat(out, " | ")
"""


def flatten(lua):
    """Collapse a Lua chunk to one line for the IPC hop.

    A `--` line comment would swallow everything after it once the newlines are
    gone, and the result still compiles, so the failure is silent: the chunk
    returns nil for every candidate and looks like an empty map rather than a
    bug. Use `--[[ ]]` block comments in SURVEY_LUA instead.
    """
    flat = " ".join(line.strip() for line in lua.strip().splitlines())
    if "--" in flat.replace("--[[", "").replace("]]", ""):
        raise AssertionError(
            "SURVEY_LUA contains a '--' line comment, which flattening turns "
            "into a silent truncation. Use --[[ ]] block comments."
        )
    return flat


def parse(result_text):
    """Turn 'k=v | k=v' into a dict; pass anything else through as a marker."""
    if "=" not in result_text:
        return {"_raw": result_text}
    fields = {}
    for chunk in result_text.split("|"):
        if "=" in chunk:
            k, v = chunk.strip().split("=", 1)
            fields[k] = v
    return fields


def verdict(f):
    """Fast-eliminate on the criteria from issue #1, in eliminating order."""
    if f.get("_raw"):
        return "SKIP", f["_raw"]
    if f.get("building") != "true":
        return "OUT", "no building at these coordinates"
    if f.get("vehicleRoomy") != "true" and f.get("vehicleTight") != "true":
        return "OUT", "no vehicle placement within 16 tiles"
    if f.get("objectSpot") != "true":
        return "OUT", "nowhere to put the well or generator"
    notes = []
    if f.get("vehicleRoomy") != "true":
        notes.append("vehicle only fits tight")
    if f.get("existingWell") == "true":
        notes.append("has a well (exercises detection)")
    if f.get("existingGenerator") == "true":
        notes.append("has a generator")
    return "KEEP", ", ".join(notes) or "clean"


def main():
    cfg = load_config(TEST_PILOT_SCRIPTS.parent / "pz-test-pilot.json")
    rows = []

    for num, x, y, note in CANDIDATES:
        label = f"#{num:<2} {x},{y}"
        try:
            send_command(cfg, "teleport", {"x": x, "y": y, "z": 0})
        except (CommandTimeout, HarnessDead) as exc:
            print(f"[DEAD]  {label}: teleport failed: {exc}")
            return 2

        time.sleep(CELL_LOAD_SECONDS)

        chunk = flatten(SURVEY_LUA % (x, y))
        try:
            result = send_command(cfg, "run_lua", {"code": chunk})
        except CommandTimeout:
            print(f"[TIMEOUT] {label}")
            continue
        except HarnessDead as exc:
            print(f"[DEAD]  harness not responding: {exc}")
            print("        If PZ is alive, this is the tick-heartbeat false positive.")
            return 2

        fields = parse(str(result.get("result", result)))
        call, why = verdict(fields)
        rows.append((num, x, y, call, why, fields, note))
        print(f"[{call:4}] {label:18} {why}")
        print(f"        {result.get('result')}")

    keep = [r for r in rows if r[3] == "KEEP"]
    print(f"\n{len(keep)} of {len(rows)} candidates survive automated screening.")
    print("Drive time to the nearest town is criterion 2 and still needs a human.")
    for num, x, y, _, why, _, note in keep:
        suffix = f" ({note})" if note else ""
        print(f"  #{num}: {x},{y} - {why}{suffix}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
