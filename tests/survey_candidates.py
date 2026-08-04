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

Every scan below is centred on the player, so each hop goes through `_pilot`'s
teleport(), which moves the player itself and then confirms the landing square.
pz-test-pilot's own teleport command is unusable on B42.20: measured over a full
12-hop run, it threw every time and never moved the player at all. A candidate
that cannot be reached is reported as unscreened, never scored from the wrong
square.

Requires: PZ running, a save loaded (the harness registers on OnGameStart), and
the PZTestPilot mod enabled.

    python tests/survey_candidates.py

Note: pz-test-pilot reports `harness_dead` whenever PZ is unfocused, because its
heartbeat counts in-game ticks and the clock stops. Keep the game window in the
foreground, or read Zomboid/Lua/TestPilot/result.txt directly.
"""

import sys

from _pilot import (
    load, run_lua, parse, teleport,
    CommandTimeout, HarnessDead, HarnessError,
)


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

# Mirrors SpawnScenario.lua as of the session-4 placement rewrite: the water and
# soft-ground tests, the building-clearance margins, the search radii, and the
# well/generator gap. The mod also has a *fallback* tier for each placement, so
# a square this survey scores is not simply legal or illegal - it is preferred,
# fallback, or nothing, and the difference is the placement quality Rob rejected
# in session 4. If SpawnScenario.lua's rules move again, move these with them.
#
# One deliberate approximation: the mod searches out from the player's spawn
# square inside the cabin, while this searches from the candidate coordinate.
# Close enough to screen with, not close enough to predict the exact square.
SURVEY_LUA = """
local X, Y, Z = %d, %d, 0
local out = {}
local function add(k, v) table.insert(out, k .. "=" .. tostring(v)) end
local function at(s) return s:getX() .. "," .. s:getY() end

local centre = getSquare(X, Y, Z)
if not centre then return "UNLOADED" end

--[[ Radii and margins, from SpawnScenario.lua. ]]
local VEHICLE_MIN_RADIUS, VEHICLE_SEARCH_RADIUS = 6, 16
local OBJECT_MIN_RADIUS, OBJECT_SEARCH_RADIUS = 2, 12
local EXISTING_OBJECT_SCAN_RADIUS = 12
local BUILDING_CLEARANCE, VEHICLE_BUILDING_CLEARANCE = 3, 2
local VEHICLE_CLEARANCE, VEHICLE_FALLBACK_CLEARANCE = 2, 1
local GENERATOR_WELL_GAP = 1

--[[ Standing water, including river and pond squares carrying the tainted flag
     rather than the plain one. Read off the floor sprite's own properties, the
     way vanilla does in ISWoodenStairs.lua. ]]
local function isWaterSquare(s)
    local floor = s:getFloor()
    if not floor then return false end
    local sprite = floor:getSprite()
    local props = sprite and sprite:getProperties()
    if props and props:has(IsoFlagType.water) then return true end
    local sq = s:getProperties()
    return sq ~= nil and sq:has(IsoFlagType.taintedWater)
end

--[[ Bare dirt or grass rather than pavement, gravel, sand or clay. Vanilla
     classifies ground by floor sprite name in ISShovelGroundCursor.lua. ]]
local SOFT_PREFIXES = { "blends_natural_01_", "floors_exterior_natural" }
local NOT_SOFT = {
    ["floors_exterior_natural_01_13"] = true, ["blends_street_01_55"] = true,
    ["blends_street_01_54"] = true, ["blends_street_01_53"] = true,
    ["blends_street_01_48"] = true,
    ["blends_natural_01_0"] = true, ["blends_natural_01_5"] = true,
    ["blends_natural_01_6"] = true, ["blends_natural_01_7"] = true,
    ["floors_exterior_natural_01_24"] = true,
    ["blends_natural_01_96"] = true, ["blends_natural_01_101"] = true,
    ["blends_natural_01_102"] = true, ["blends_natural_01_103"] = true,
}
local function isSoftGround(s)
    local floor = s:getFloor()
    if not floor then return false end
    local sprite = floor:getSprite()
    local name = sprite and sprite:getName()
    if not name or NOT_SOFT[name] then return false end
    for _, p in ipairs(SOFT_PREFIXES) do
        if string.sub(name, 1, string.len(p)) == p then return true end
    end
    return false
end

local function isOpenGround(s)
    return s:isOutside() and s:getBuilding() == nil and s:isFree(false)
        and not isWaterSquare(s)
end

--[[ No building within margin tiles. getBuilding() on the square alone only
     answers "am I standing in one", which is how session 3 put the well flat
     against the cabin wall. ]]
local function isClearOfBuildings(s, margin)
    local x, y, z = s:getX(), s:getY(), s:getZ()
    for dx = -margin, margin do for dy = -margin, margin do
        local n = getSquare(x+dx, y+dy, z)
        if n and n:getBuilding() ~= nil then return false end
    end end
    return true
end

--[[ Field-test isDoor rather than pcall it. Most IsoObjects have no such
     method, and calling it anyway makes PZ dump a full Java stack trace to
     console.txt - 234 of them in one world start, measured in session 4. ]]
local function blocksDoorway(s)
    local x, y, z = s:getX(), s:getY(), s:getZ()
    for dx = -1, 1 do for dy = -1, 1 do
        local n = getSquare(x+dx, y+dy, z)
        if n then
            local o = n:getObjects()
            for i = 0, o:size() - 1 do
                local ob = o:get(i)
                if instanceof(ob, "IsoDoor") then return true end
                if ob.isDoor and ob:isDoor() then return true end
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

--[[ Cheap tests first: Lua short-circuits, and the clearance scans are two
     orders of magnitude dearer than reading a floor sprite. Same order the mod
     uses. ]]
local function isObjectSpot(s)
    return isOpenGround(s) and isSoftGround(s)
        and isClearOfBuildings(s, BUILDING_CLEARANCE) and not blocksDoorway(s)
end
local function isFallbackObjectSpot(s)
    return isOpenGround(s) and isClearOfBuildings(s, 1) and not blocksDoorway(s)
end
local function isVehicleSpot(s)
    return isOpenGround(s) and isClearOfBuildings(s, VEHICLE_BUILDING_CLEARANCE)
        and hasClearance(s, VEHICLE_CLEARANCE) and not blocksDoorway(s)
end
local function isTightVehicleSpot(s)
    return isOpenGround(s) and isClearOfBuildings(s, VEHICLE_BUILDING_CLEARANCE)
        and hasClearance(s, VEHICLE_FALLBACK_CLEARANCE) and not blocksDoorway(s)
end

--[[ 1. Is there a building here? Not "is this exact tile inside one": the
     shortlist coordinates were read off the map site and land in the yard
     beside each cabin, so getBuilding() on the centre square answered false for
     all twelve while every one of them had a cabin within ten tiles. Search a
     radius and report the size, which is also the signal that separates a cabin
     from a farmhouse. ]]
local BUILDING_SEARCH_RADIUS = 12
local nearest, nearestDist, nearestAt = nil, 9999, "none"
for dx = -BUILDING_SEARCH_RADIUS, BUILDING_SEARCH_RADIUS do
for dy = -BUILDING_SEARCH_RADIUS, BUILDING_SEARCH_RADIUS do
    local s = getSquare(X+dx, Y+dy, Z)
    if s then
        local b = s:getBuilding()
        if b then
            local d = math.max(math.abs(dx), math.abs(dy))
            if d < nearestDist then
                nearestDist = d
                nearest = b
                nearestAt = (X+dx) .. "," .. (Y+dy)
            end
        end
    end
end end
add("building", nearest ~= nil)
if nearest then
    add("buildingDist", nearestDist)
    add("buildingAt", nearestAt)
    pcall(function()
        local d = nearest:getDef()
        add("rooms", d:getRooms():size())
        add("size", d:getW() .. "x" .. d:getH())
    end)
end

--[[ 2. Existing water source / generator, using the mod's own detection. ]]
local WELL_SPRITES = { ["camping_01_16"] = true }
local well, gen = false, false
local R = EXISTING_OBJECT_SCAN_RADIUS
for dx = -R, R do for dy = -R, R do
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

--[[ 3. Where would the well go, and on which tier? ]]
local wellTier, wellSquare = "none", nil
wellSquare = findSquare(OBJECT_MIN_RADIUS, OBJECT_SEARCH_RADIUS, isObjectSpot)
if wellSquare then
    wellTier = "preferred"
else
    wellSquare = findSquare(OBJECT_MIN_RADIUS, OBJECT_SEARCH_RADIUS, isFallbackObjectSpot)
    if wellSquare then wellTier = "fallback" end
end
add("wellTier", wellTier)
add("wellAt", wellSquare and at(wellSquare) or "none")

--[[ 4. The generator searches the same rings from the same centre, so it has to
     dodge whatever the well just took. Screening for "one legal square" would
     pass a cabin that only ever has one. ]]
local function isAwayFromWell(s)
    if not wellSquare then return true end
    local gap = math.max(math.abs(s:getX() - wellSquare:getX()),
                         math.abs(s:getY() - wellSquare:getY()))
    return gap > GENERATOR_WELL_GAP
end
local genTier, genSquare = "none", nil
genSquare = findSquare(OBJECT_MIN_RADIUS, OBJECT_SEARCH_RADIUS, function(s)
    return isAwayFromWell(s) and isObjectSpot(s)
end)
if genSquare then
    genTier = "preferred"
else
    genSquare = findSquare(OBJECT_MIN_RADIUS, OBJECT_SEARCH_RADIUS, function(s)
        return isAwayFromWell(s) and isFallbackObjectSpot(s)
    end)
    if genSquare then genTier = "fallback" end
end
add("generatorTier", genTier)
add("generatorAt", genSquare and at(genSquare) or "none")

--[[ 5. Parking. ]]
local vehicleTier, vehicleSquare = "none", nil
vehicleSquare = findSquare(VEHICLE_MIN_RADIUS, VEHICLE_SEARCH_RADIUS, isVehicleSpot)
if vehicleSquare then
    vehicleTier = "roomy"
else
    vehicleSquare = findSquare(VEHICLE_MIN_RADIUS, VEHICLE_SEARCH_RADIUS, isTightVehicleSpot)
    if vehicleSquare then vehicleTier = "tight" end
end
add("vehicleTier", vehicleTier)
add("vehicleAt", vehicleSquare and at(vehicleSquare) or "none")

return table.concat(out, " | ")
"""


def verdict(f):
    """Grade one candidate against the mod's real placement rules.

    Three calls rather than two. The mod falls back rather than failing, so a
    cabin where every placement lands on the fallback tier still produces a
    playable start - it just produces the one Rob rejected in session 4, with
    the well on gravel or a car wedged a tile from the porch. WEAK keeps those
    visible instead of scoring them level with a clean cabin.
    """
    if f.get("_raw"):
        return "SKIP", f["_raw"]
    if f.get("building") != "true":
        return "OUT", "no building within 12 tiles"

    well, gen = f.get("wellTier"), f.get("generatorTier")
    vehicle = f.get("vehicleTier")
    if vehicle == "none":
        return "OUT", "no parking within 16 tiles"
    if well == "none" and f.get("existingWell") != "true":
        return "OUT", "nowhere to put the well"
    if gen == "none" and f.get("existingGenerator") != "true":
        return "OUT", "nowhere to put the generator"

    weak, notes = [], []
    if f.get("existingWell") == "true":
        notes.append("has a well (exercises detection)")
    elif well == "fallback":
        weak.append("well only fits on fallback ground")
    if f.get("existingGenerator") == "true":
        notes.append("has a generator (exercises the adopt branch)")
    elif gen == "fallback":
        weak.append("generator only fits on fallback ground")
    if vehicle == "tight":
        weak.append("vehicle only fits tight")

    if weak:
        return "WEAK", ", ".join(weak + notes)
    return "KEEP", ", ".join(notes) or "clean"


def main():
    cfg = load()
    rows = []
    unscreened = []

    for num, x, y, note in CANDIDATES:
        label = f"#{num:<2} {x},{y}"
        print(f"\n{label}")

        # A candidate the player never reached is unscreened, not OUT. Scoring
        # it anyway would grade whatever square the player is actually standing
        # on and pin the result to this cabin's name.
        try:
            teleport(cfg, (x, y))
        except HarnessError as exc:
            print(f"[SKIP] {label}: {exc}")
            unscreened.append((num, x, y, str(exc)))
            continue
        except (CommandTimeout, HarnessDead) as exc:
            print(f"[DEAD]  {label}: teleport failed: {exc}")
            return 2

        try:
            answer = run_lua(cfg, SURVEY_LUA % (x, y))
        except CommandTimeout:
            print(f"[TIMEOUT] {label}")
            unscreened.append((num, x, y, "survey timed out"))
            continue
        except HarnessError as exc:
            print(f"[ERROR] {label}: {exc}")
            unscreened.append((num, x, y, str(exc)))
            continue
        except HarnessDead as exc:
            print(f"[DEAD]  harness not responding: {exc}")
            print("        If PZ is alive, this is the tick-heartbeat false positive.")
            return 2

        fields = parse(answer)
        call, why = verdict(fields)
        rows.append((num, x, y, call, why, fields, note))
        print(f"[{call:4}] {label:18} {why}")
        print(f"        {answer}")

    keep = [r for r in rows if r[3] == "KEEP"]
    weak = [r for r in rows if r[3] == "WEAK"]
    print(f"\n{len(keep)} clean and {len(weak)} workable of {len(rows)} screened, "
          f"out of {len(CANDIDATES)} on the shortlist.")
    print("Drive time to the nearest town is criterion 2 and still needs a human.")
    for label, group in (("clean", keep), ("workable", weak)):
        if not group:
            continue
        print(f"\n  {label}:")
        for num, x, y, _, why, fields, note in group:
            suffix = f" ({note})" if note else ""
            print(f"    #{num}: {x},{y} - {why}{suffix}")
            print(f"        building {fields.get('size')}, "
                  f"{fields.get('rooms')} rooms, "
                  f"{fields.get('buildingDist')} tiles away")
            print(f"        well {fields.get('wellAt')} | "
                  f"generator {fields.get('generatorAt')} | "
                  f"vehicle {fields.get('vehicleAt')}")

    if unscreened:
        print(f"\n{len(unscreened)} candidate(s) never got screened, so this run "
              "does not cover the shortlist:")
        for num, x, y, why in unscreened:
            print(f"  #{num}: {x},{y} - {why}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
