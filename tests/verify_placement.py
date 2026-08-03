"""
Head for the Hills! - spawn placement verification.

Session 4's first live run put the well and the generator on the closest legal
square, which was flat against the wall at the foot of the porch steps, and
parked the truck by the same logic. The rules changed in response: bare dirt or
grass, a walkable gap from the building, never on water, and the well and the
generator kept apart. This measures what actually landed against those rules.

It also dumps the starting equipment list, which is the fastest way to answer
"why did I spawn with two ID cards" - vanilla issues none at spawn, so a
duplicate comes from the saved option string or from a mod.

Usage, in a fresh throwaway world, straight after spawning:

    python tests/verify_placement.py

Requires: PZ running, a save loaded (the harness registers on OnGameStart), and
the PZTestPilot mod enabled. `harness_dead` while PZ is unfocused is the
tick-heartbeat false positive; read Zomboid/Lua/TestPilot/result.txt first.
"""

import sys

from _pilot import (
    load, run_lua, parse, num, boolean,
    CommandTimeout, HarnessDead, HarnessError,
)

# Kept in step with SpawnScenario.lua. If those change, change these, otherwise
# this answers a question the mod is no longer asking.
BUILDING_CLEARANCE = 3
VEHICLE_BUILDING_CLEARANCE = 2
GENERATOR_WELL_GAP = 1
SCAN_RADIUS = 16


# Mirrors isSoftGround / isWaterSquare in SpawnScenario.lua, which in turn
# mirror vanilla's ISShovelGroundCursor.GetDirtGravelSand and the floor-sprite
# water flag used by ISWoodenStairs.lua.
SURVEY_LUA = """
local R = __R__
local p = getPlayer()
if not p then return "NOPLAYER" end
local c = p:getCurrentSquare()
if not c then return "NOSQUARE" end
local cx, cy, cz = c:getX(), c:getY(), c:getZ()
local out = {}
local function add(k, v) table.insert(out, k .. "=" .. tostring(v)) end
local function try(f) local ok, v = pcall(f) if ok then return v end return "ERR" end

local sv = SandboxVars and SandboxVars.HeadForTheHills
add("equipmentList", sv and (sv.StartingEquipmentList or "") or "NOOPTIONS")

local NOT_SOFT = {
    ["floors_exterior_natural_01_13"]=true, ["blends_street_01_55"]=true,
    ["blends_street_01_54"]=true, ["blends_street_01_53"]=true,
    ["blends_street_01_48"]=true, ["blends_natural_01_0"]=true,
    ["blends_natural_01_5"]=true, ["blends_natural_01_6"]=true,
    ["blends_natural_01_7"]=true, ["floors_exterior_natural_01_24"]=true,
    ["blends_natural_01_96"]=true, ["blends_natural_01_101"]=true,
    ["blends_natural_01_102"]=true, ["blends_natural_01_103"]=true,
}
local function startsWith(t, pre) return string.sub(t, 1, string.len(pre)) == pre end
local function groundOf(s)
    local floor = s:getFloor()
    if not floor then return "nofloor" end
    local sp = floor:getSprite()
    local nm = sp and sp:getName()
    if not nm then return "nosprite" end
    if NOT_SOFT[nm] then return "hard:" .. nm end
    if startsWith(nm, "blends_natural_01_") or startsWith(nm, "floors_exterior_natural") then
        return "soft:" .. nm
    end
    return "other:" .. nm
end
local function isWater(s)
    local floor = s:getFloor()
    if not floor then return false end
    local sp = floor:getSprite()
    local pr = sp and sp:getProperties()
    if pr and pr:has(IsoFlagType.water) then return true end
    local sq = s:getProperties()
    return sq ~= nil and sq:has(IsoFlagType.taintedWater)
end
--[[ Chebyshev distance to the nearest square belonging to any building. ]]
local function buildingGap(s)
    local x, y, z = s:getX(), s:getY(), s:getZ()
    for margin = 0, 8 do
        for dx = -margin, margin do for dy = -margin, margin do
            if math.abs(dx) == margin or math.abs(dy) == margin then
                local n = getSquare(x+dx, y+dy, z)
                if n and n:getBuilding() ~= nil then return margin end
            end
        end end
    end
    return 99
end

local WELL_SPRITES = { ["camping_01_16"] = true }
local gen, well = nil, nil
for dx = -R, R do for dy = -R, R do
    local s = getSquare(cx+dx, cy+dy, cz)
    if s then
        local o = s:getObjects()
        for i = 0, o:size() - 1 do
            local ob = o:get(i)
            if not gen and instanceof(ob, "IsoGenerator") then gen = ob end
            if not well then
                local sp = ob:getSprite()
                local nm = sp and sp:getName()
                local isWell = nm ~= nil and WELL_SPRITES[nm] == true
                if not isWell then
                    local okFc, fc = pcall(function() return ob:getFluidContainer() end)
                    isWell = okFc and fc ~= nil
                end
                if isWell then well = ob end
            end
        end
    end
end end

local function describe(prefix, object)
    if not object then add(prefix, "none") return nil end
    local s = object:getSquare()
    add(prefix, s:getX() .. "," .. s:getY())
    add(prefix .. "Ground", groundOf(s))
    add(prefix .. "Water", isWater(s))
    add(prefix .. "BuildingGap", buildingGap(s))
    return s
end

local wellSq = describe("well", well)
local genSq = describe("gen", gen)

local vehicle = nil
local best = 999
for dx = -R, R do for dy = -R, R do
    local s = getSquare(cx+dx, cy+dy, cz)
    if s then
        local v = s:getVehicleContainer()
        if v then
            local d = math.max(math.abs(dx), math.abs(dy))
            if d < best then best = d; vehicle = s end
        end
    end
end end
if vehicle then
    add("vehicle", vehicle:getX() .. "," .. vehicle:getY())
    add("vehicleWater", isWater(vehicle))
    add("vehicleBuildingGap", buildingGap(vehicle))
    add("vehicleGround", groundOf(vehicle))
else
    add("vehicle", "none")
end

if wellSq and genSq then
    add("wellGenGap", math.max(math.abs(wellSq:getX() - genSq:getX()),
                               math.abs(wellSq:getY() - genSq:getY())))
end
return table.concat(out, " | ")
"""


def check(fields):
    """Score what landed against the rules the mod now claims to follow."""
    problems, notes = [], []

    for name, label, clearance in (
        ("well", "well", BUILDING_CLEARANCE),
        ("gen", "generator", BUILDING_CLEARANCE),
        ("vehicle", "vehicle", VEHICLE_BUILDING_CLEARANCE),
    ):
        where = fields.get(name)
        if not where or where == "none":
            notes.append(f"{label}: not present (option off, or placement skipped)")
            continue

        if boolean(fields, f"{name}Water") is True:
            problems.append(f"{label} at {where} is on water")

        gap = num(fields, f"{name}BuildingGap")
        if gap is None:
            problems.append(f"{label} at {where}: building distance unreadable")
        elif gap < clearance:
            problems.append(f"{label} at {where} is {gap:.0f} tiles from a "
                            f"building; the rule is {clearance}")

        ground = fields.get(f"{name}Ground", "")
        # The vehicle is allowed on a road or driveway; only the well and the
        # generator are required to stand on bare dirt or grass.
        if name != "vehicle" and not ground.startswith("soft:"):
            problems.append(f"{label} at {where} is on '{ground}', not dirt or grass")

    gap = num(fields, "wellGenGap")
    if gap is not None and gap <= GENERATOR_WELL_GAP:
        problems.append(f"well and generator are {gap:.0f} tiles apart; "
                        f"the rule is more than {GENERATOR_WELL_GAP}")

    return problems, notes


def main():
    try:
        answer = run_lua(load(), SURVEY_LUA.replace("__R__", str(SCAN_RADIUS)))
    except HarnessDead as exc:
        print(f"[DEAD] {exc}")
        print("       If PZ is alive and just unfocused, this is the "
              "tick-heartbeat false positive.")
        return 2
    except CommandTimeout as exc:
        print(f"[TIMEOUT] {exc}")
        return 2
    except HarnessError as exc:
        print(f"[HARNESS] {exc}")
        return 2

    fields = parse(answer)
    if fields.get("_raw"):
        print(f"[RAW] {fields['_raw']}")
        return 2

    equipment = fields.pop("equipmentList", "")
    print("Starting equipment list:")
    entries = [e for e in equipment.split(";") if e]
    if not entries:
        print("  (empty)")
    for entry in entries:
        print(f"  {entry}")
    duplicates = {e for e in entries if entries.count(e) > 1}
    if duplicates:
        print(f"  DUPLICATE ENTRIES: {', '.join(sorted(duplicates))}")

    print("\nPlacement:")
    for key, value in fields.items():
        print(f"  {key:20} {value}")

    problems, notes = check(fields)
    for note in notes:
        print(f"\n  note: {note}")
    if problems:
        print("\nFAIL")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\nPASS - everything placed on legal ground, clear of the building "
          "and out of the water")
    return 0


if __name__ == "__main__":
    sys.exit(main())
