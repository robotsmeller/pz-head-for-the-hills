"""
Head for the Hills! - spawn placement verification.

Session 4's first live run put the well and the generator on the closest legal
square, which was flat against the wall at the foot of the porch steps, and
parked the truck by the same logic. The rules changed in response: bare dirt or
grass, a walkable gap from the building, never on water, and the well and the
generator kept apart. This measures what actually landed against those rules.

It also dumps the starting equipment list. That was meant to answer "why did I
spawn with two ID cards", on the assumption that vanilla issues none. It does:
SpawnItems.lua hands every new character a Base.IDcard unconditionally, so
picking any of the four items that display as plain "ID Card" makes two.

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

--[[ Which placements were actually asked for. Without this the check cannot
     tell "the option was off" from "the mod failed to place anything", and it
     graded the second as a pass. ]]
local sv = SandboxVars and SandboxVars.HeadForTheHills
add("optWell", sv and sv.SpawnWell)
add("optGen", sv and sv.SpawnGenerator)
add("optVehicle", sv and sv.SpawnVehicle)

--[[ A square that has not streamed in yet reads as nil, and an object standing
     on it is invisible to this scan rather than absent. Measured live: a scan
     run just after a fresh spawn reported no well, no generator and no vehicle,
     and all three were found once the chunks had settled. Count the misses so
     the run can refuse to grade instead of reporting a phantom failure. ]]
local nilSquares = 0

local WELL_SPRITES = { ["camping_01_16"] = true }
local gen, well = nil, nil
for dx = -R, R do for dy = -R, R do
    local s = getSquare(cx+dx, cy+dy, cz)
    if not s then nilSquares = nilSquares + 1 end
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

--[[ The mod hands the player the key it made with createVehicleKey(), so
     "the vehicle whose key you are carrying" identifies ours exactly. Nearest
     wins is only a fallback: a map vehicle parked closer than ours gets graded
     in its place, and a neighbour's van on a driveway fails rules our truck
     never broke. getKeyId/haveThisKeyId are vanilla, per ISStartVehicleEngine. ]]
local inv = p:getInventory()
local mine, nearest, nearestDist = nil, nil, 999
local seen, listed = {}, {}
for dx = -R, R do for dy = -R, R do
    local s = getSquare(cx+dx, cy+dy, cz)
    if s then
        local v = s:getVehicleContainer()
        if v then
            local anchor = v:getSquare()
            local key = anchor:getX() .. "," .. anchor:getY()
            if not seen[key] then
                seen[key] = true
                local nm = "?"
                local script = v.getScript and v:getScript()
                if script and script.getName then nm = script:getName() end
                --[[ haveThisKeyId answers with the Key item, not a boolean, so
                     comparing it to true is always false and silently disables
                     this whole branch. Vanilla only ever truthy-tests it. ]]
                local owned = false
                if v.getKeyId and inv and inv.haveThisKeyId then
                    owned = inv:haveThisKeyId(v:getKeyId()) ~= nil
                end
                if owned and not mine then mine = anchor end
                local d = math.max(math.abs(anchor:getX() - cx),
                                   math.abs(anchor:getY() - cy))
                if d < nearestDist then nearestDist = d; nearest = anchor end
                table.insert(listed, nm .. "@" .. key ..
                    (owned and " (key held)" or ""))
            end
        end
    end
end end
add("vehiclesSeen", #listed > 0 and table.concat(listed, " ; ") or "none")
add("vehiclePickedBy", mine and "key" or (nearest and "proximity" or "none"))
local vehicle = mine or nearest
if vehicle then
    add("vehicle", vehicle:getX() .. "," .. vehicle:getY())
    add("vehicleWater", isWater(vehicle))
    add("vehicleBuildingGap", buildingGap(vehicle))
    add("vehicleGround", groundOf(vehicle))
else
    add("vehicle", "none")
end

add("nilSquares", nilSquares)

if wellSq and genSq then
    add("wellGenGap", math.max(math.abs(wellSq:getX() - genSq:getX()),
                               math.abs(wellSq:getY() - genSq:getY())))
end
return table.concat(out, " | ")
"""


def check(fields):
    """Score what landed against the rules the mod now claims to follow."""
    problems, notes = [], []

    if fields.get("vehiclePickedBy") == "proximity":
        notes.append("no vehicle key in your inventory, so the vehicle graded "
                     "below is just the closest one and may belong to the map "
                     "rather than the mod")

    for name, label, clearance, option in (
        ("well", "well", BUILDING_CLEARANCE, "optWell"),
        ("gen", "generator", BUILDING_CLEARANCE, "optGen"),
        ("vehicle", "vehicle", VEHICLE_BUILDING_CLEARANCE, "optVehicle"),
    ):
        where = fields.get(name)
        if not where or where == "none":
            # Absent is only acceptable when it was never asked for. This used
            # to be a note either way, so a spawn that placed nothing at all
            # came back PASS.
            if boolean(fields, option) is True:
                problems.append(
                    f"{label}: the option is on but nothing was placed within "
                    f"{SCAN_RADIUS} tiles")
            else:
                notes.append(f"{label}: not present, and its option is off")
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

    # Refuse to grade a half-loaded cell. Measured live: a scan run just after a
    # fresh spawn found no well, no generator and no vehicle, and all three were
    # sitting there once the chunks finished streaming.
    missing = num(fields, "nilSquares")
    if missing:
        print(f"\nINCONCLUSIVE - {missing:.0f} squares in the scan area have "
              "not streamed in yet.\n  Anything standing on them is invisible "
              "to this scan rather than absent.\n  Stand still for a few "
              "seconds and run it again.")
        return 3

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
