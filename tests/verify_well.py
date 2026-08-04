"""
Head for the Hills! - the well's skip-existing branch.

spawnWell() bails out early when hasWellNearby() finds one, so a cabin that
already has a well on the map keeps it instead of getting a second dug beside
it. Every other branch of the spawn had been driven live by session 6; this one
never had, because it only fires at a location that already has a well.

    python tests/verify_well.py --at 9668,8775

Cabin #4 is the known one. Any coordinate with a map well works.

Unlike verify_generator.py, this restores the sandbox vars it arms, so it is
safe to point at a save you care about. Arming is still a real write to the
loaded save while it runs.

Requires: PZ running, a save loaded, the PZTestPilot mod enabled.
"""

import argparse
import sys

from _pilot import (
    load, run_lua, parse, num, teleport, snapshot_options, restore_options,
    CommandTimeout, HarnessDead, HarnessError,
)

# Matches EXISTING_OBJECT_SCAN_RADIUS in SpawnScenario.lua, so this asks the
# question the mod is actually asking.
SCAN_RADIUS = 12

# How the mod itself recognises a well: the sprite B42's Base.Well entity
# declares, or any object carrying a FluidContainer, which is what catches
# modded wells and pumps on their own sprites.
SCAN_LUA = """
local R = __R__
local p = getPlayer()
if not p then return "NOPLAYER" end
local c = p:getCurrentSquare()
if not c then return "NOSQUARE" end
local cx, cy, cz = c:getX(), c:getY(), c:getZ()
local WELL_SPRITES = { ["camping_01_16"] = true }
local wells, at, nilSquares = 0, "none", 0
for dx = -R, R do for dy = -R, R do
    local s = getSquare(cx + dx, cy + dy, cz)
    if not s then nilSquares = nilSquares + 1 else
        local o = s:getObjects()
        for i = 0, o:size() - 1 do
            local ob = o:get(i)
            local sp = ob:getSprite()
            local nm = sp and sp:getName()
            local isWell = nm ~= nil and WELL_SPRITES[nm] == true
            if not isWell then
                local okFc, fc = pcall(function() return ob:getFluidContainer() end)
                isWell = okFc and fc ~= nil
            end
            if isWell then
                wells = wells + 1
                if at == "none" then at = s:getX() .. "," .. s:getY() end
            end
        end
    end
end end
return "player=" .. cx .. "," .. cy .. " | wells=" .. wells
    .. " | wellAt=" .. at .. " | nilSquares=" .. nilSquares
"""

# Narrow the re-fired OnNewGame down to the well alone, so nothing else this
# mod places lands in the save as a side effect of the test. Season 0 falls off
# the end of SEASON_START_MONTH, which makes applySeason a no-op rather than
# moving the clock on the way past.
ARM_LUA = """
local sv = SandboxVars and SandboxVars.HeadForTheHills
if not sv then return "NOOPTIONS" end
sv.SpawnVehicle = false
sv.SpawnGenerator = false
sv.SpawnStartingEquipment = false
sv.ZombieFreeRadius = 0
sv.Season = 0
sv.SpawnWell = true
return "armed | triggerEvent=" .. type(triggerEvent)
"""

TRIGGER_LUA = """
local p = getPlayer()
if not p then return "NOPLAYER" end
if type(triggerEvent) ~= "function" then return "NOTRIGGER" end
local ok, err = pcall(function() triggerEvent("OnNewGame", p, p:getCurrentSquare()) end)
return "triggered=" .. tostring(ok) .. " | err=" .. tostring(err)
"""


def scan(cfg, radius):
    return parse(run_lua(cfg, SCAN_LUA.replace("__R__", str(radius))))


def report(label, fields):
    print(f"  {label}:")
    for key, value in fields.items():
        print(f"    {key:12} {value}")


def check(cfg, args):
    print("The mod should leave a cabin's own well alone, not dig a second.\n")
    if args.at:
        teleport(cfg, args.at)

    before = scan(cfg, args.radius)
    report("before", before)

    # An unstreamed square reads as nil and is indistinguishable from an empty
    # one, so a scan that caught the cell mid-load would grade a well that is
    # really there as absent. Measured in session 6; refuse rather than guess.
    if num(before, "nilSquares"):
        print(f"\nINCONCLUSIVE - {before['nilSquares']} squares had not streamed "
              "in yet.\n  Wait for the cell to settle and run it again.")
        return 3

    wells = num(before, "wells")
    if not wells:
        print("\nSKIP - no well here, so the skip-existing path cannot fire.")
        print("       Cabin #4 at 9668,8775 has one.")
        return 3

    snapshot = snapshot_options(cfg)
    try:
        armed = run_lua(cfg, ARM_LUA)
        print(f"\n  arm: {armed}")
        if "NOOPTIONS" in str(armed):
            print("\nFAIL\n  - SandboxVars.HeadForTheHills is missing; the mod "
                  "did not load in this save.")
            return 1
        if "triggerEvent=function" not in str(armed):
            print("\nFAIL\n  - triggerEvent is not a callable global, so "
                  "OnNewGame cannot be re-fired.")
            return 1

        fired = run_lua(cfg, TRIGGER_LUA)
        print(f"  fire: {fired}")
        if "triggered=true" not in str(fired):
            print("\nFAIL\n  - OnNewGame did not fire.")
            return 1

        after = scan(cfg, args.radius)
        print()
        report("after", after)
    finally:
        restore_options(cfg, snapshot)

    problems = []
    if num(after, "wells") != wells:
        problems.append(
            f"well count went {wells:.0f} -> {num(after, 'wells'):.0f}; the mod "
            "dug a second one instead of leaving the map's alone")
    if after.get("wellAt") != before.get("wellAt"):
        problems.append(f"nearest well moved from {before.get('wellAt')} "
                        f"to {after.get('wellAt')}")

    if problems:
        print("\nFAIL")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\nPASS - the cabin's own well was kept and no second one appeared")
    return 0


def coordinates(text):
    try:
        x, y = (int(part) for part in text.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError("expected X,Y - e.g. 9668,8775")
    return x, y


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--at", type=coordinates,
                        help="teleport here first, as X,Y")
    parser.add_argument("--radius", type=int, default=SCAN_RADIUS,
                        help=f"scan radius in tiles (default {SCAN_RADIUS}, "
                             "matching the mod)")
    args = parser.parse_args()

    try:
        return check(load(), args)
    except HarnessDead as exc:
        print(f"\n[DEAD] {exc}")
        print("       If PZ is alive and just unfocused, this is the "
              "tick-heartbeat false positive.")
        print("       Check Zomboid/Lua/TestPilot/result.txt and log.txt.")
        return 2
    except CommandTimeout as exc:
        print(f"\n[TIMEOUT] {exc}")
        return 2
    except HarnessError as exc:
        print(f"\n[HARNESS] {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
