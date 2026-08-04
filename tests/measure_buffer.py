"""
Head for the Hills! - how far the zombie-free buffer can actually reach (#13).

ZombieFreeRadius offers up to 100 tiles, but clearZombies() can only remove
what getCell():getObjectListForLua() is holding, and the cell holds the loaded
area. So the option's real ceiling is however far that reaches, and no choice
of API moves it - a square that has not streamed in reads as nil to every one
of them. (Vanilla's own hint that unloaded zombies are somewhere else entirely
is Challenge1.lua:135, on VirtualZombieManager. That is a comment, not a
measurement, which is what this script is for.)

Two measurements, one command, nothing written:

  reach   - how far getSquare() answers in each of the eight directions before
            returning nil. This is the ceiling itself, and it needs no zombies,
            so it can be taken at a cabin as well as beside a town.
  zombies - every IsoZombie the cell is holding, by distance from the player.
            The radius where the running count stops growing is the ceiling
            measured from the other side. Needs somewhere with zombies in it.

Read-only: no sandbox vars are armed, no zombies are removed, OnNewGame is not
re-fired. Safe to point at a save you care about.

    python tests/measure_buffer.py
    python tests/measure_buffer.py --at 10480,9280

Requires: PZ running, a save loaded, the PZTestPilot mod enabled, and the game
window focused - PZ stops ticking when it loses focus.
"""

import argparse
import sys

from _pilot import (
    load, run_lua, parse, num, teleport,
    CommandTimeout, HarnessDead, HarnessError,
)

# How far out to probe for loaded squares. Higher than the option's 100 on
# purpose: a probe that stops at the option's own maximum cannot tell "the
# world ends here" from "the probe ended here".
PROBE = 140

# The distance bands the zombie count is reported in.
BANDS = (10, 20, 30, 40, 50, 60, 70, 80, 90, 100)

DIRECTIONS = ("E", "W", "N", "S", "NE", "NW", "SE", "SW")

# getCell():getWidthInTiles() is vanilla's own way of asking how big the loaded
# area is (Challenge1.lua:137 uses it as a spawn-distance bound). It is
# field-tested rather than called blind: a method that does not exist throws
# straight past pcall on B42 and costs a Java stack dump in console.txt.
MEASURE_LUA = """
local PROBE, BANDS = __PROBE__, { __BANDS__ }
local p = getPlayer()
if not p then return "NOPLAYER" end
local c = p:getCurrentSquare()
if not c then return "NOSQUARE" end
local cx, cy, cz = c:getX(), c:getY(), c:getZ()
local cell = getCell()
local cellWidth = "nil"
if cell and cell.getWidthInTiles then cellWidth = cell:getWidthInTiles() end
local dirs = { E = {1,0}, W = {-1,0}, N = {0,-1}, S = {0,1},
               NE = {1,-1}, NW = {-1,-1}, SE = {1,1}, SW = {-1,1} }
local order = { "E", "W", "N", "S", "NE", "NW", "SE", "SW" }
local out = {}
for _, name in ipairs(order) do
    local d = dirs[name]
    local r, last = 1, 0
    while r <= PROBE do
        if getSquare(cx + d[1] * r, cy + d[2] * r, cz) == nil then break end
        last = r
        r = r + 1
    end
    table.insert(out, "reach" .. name .. "=" .. last)
end
local objects = cell:getObjectListForLua()
local total, far, beyond = 0, 0, 0
local counts = {}
for i = 1, #BANDS do counts[i] = 0 end
for i = 0, objects:size() - 1 do
    local o = objects:get(i)
    if instanceof(o, "IsoZombie") then
        total = total + 1
        local dist = IsoUtils.DistanceTo(cx + 0.5, cy + 0.5, o:getX(), o:getY())
        if dist > far then far = dist end
        local counted = false
        for b = 1, #BANDS do
            if dist < BANDS[b] then counts[b] = counts[b] + 1 counted = true end
        end
        if not counted then beyond = beyond + 1 end
    end
end
table.insert(out, "cellWidth=" .. tostring(cellWidth))
table.insert(out, "player=" .. cx .. "," .. cy)
table.insert(out, "zTotal=" .. total)
table.insert(out, "zFar=" .. string.format("%.1f", far))
table.insert(out, "zBeyond=" .. beyond)
for b = 1, #BANDS do
    table.insert(out, "z" .. BANDS[b] .. "=" .. counts[b])
end
return table.concat(out, " | ")
"""


def measure(cfg):
    lua = (MEASURE_LUA
           .replace("__PROBE__", str(PROBE))
           .replace("__BANDS__", ", ".join(str(b) for b in BANDS)))
    fields = parse(run_lua(cfg, lua))
    if "_raw" in fields:
        raise HarnessError(f"could not measure: {fields['_raw']!r}")
    return fields


def report(fields):
    """Print both measurements and the ceiling they agree on.

    Returns the recommended cap in tiles, or None when the run cannot support
    one - which is its own answer, not a pass.
    """
    print(f"\n  at {fields.get('player')}, cell width {fields.get('cellWidth')} tiles")

    print("\n  loaded reach, tiles before getSquare returns nil:")
    reaches = {}
    for name in DIRECTIONS:
        value = num(fields, "reach" + name)
        reaches[name] = value
        marker = "  (hit the probe limit)" if value == PROBE else ""
        print(f"    {name:<2} {int(value) if value is not None else '?':>4}{marker}")

    values = [v for v in reaches.values() if v is not None]
    if not values:
        print("\n  no reach measured; nothing to cap on")
        return None

    nearest, furthest = min(values), max(values)
    if furthest >= PROBE:
        print(f"\n  the probe stopped at {PROBE}, not the world. Raise PROBE and re-run.")
        return None

    print("\n  zombies the cell is holding, by distance:")
    total = num(fields, "zTotal") or 0
    if total == 0:
        print("    none loaded here, so this half of the measurement says nothing.")
        print("    Re-run somewhere with zombies in it to confirm from the other side.")
    else:
        for band in BANDS:
            print(f"    within {band:>3}: {int(num(fields, 'z%d' % band) or 0):>4}")
        print(f"    beyond {BANDS[-1]}: {int(num(fields, 'zBeyond') or 0):>4}")
        print(f"    total {int(total)}, furthest {fields.get('zFar')} tiles")

    # The loaded area is a square, so the corners sit about 1.4x further out
    # than the edges. That is why the zombie column above can hold one at 105
    # tiles while the guaranteed radius is 72: a circle only fits inside the
    # square out to the nearest edge, and everything past that is the shape
    # being generous in some directions and not others.
    corner = nearest * (2 ** 0.5)
    print(f"\n  the loaded area is a square {int(nearest)} tiles to the nearest edge")
    print(f"  and about {corner:.0f} to its corners, so a circle the buffer can")
    print(f"  promise in every direction stops at {int(nearest)}.")
    return int(nearest)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--at", metavar="X,Y",
                    help="move here first, e.g. a spot near a town")
    args = ap.parse_args()

    cfg = load()
    try:
        if args.at:
            x, y = (int(part) for part in args.at.split(","))
            teleport(cfg, (x, y))
        cap = report(measure(cfg))
    except (CommandTimeout, HarnessDead, HarnessError) as exc:
        print(f"\nFAILED: {exc}")
        print("If this was a timeout, delete command.txt and command_ready.txt "
              "from Zomboid/Lua/TestPilot/ before the game regains focus.")
        return 1
    except ValueError:
        print("--at wants X,Y as two whole numbers")
        return 2

    if cap is None:
        return 1
    print(f"\n  ZombieFreeRadius should offer at most {cap}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
