"""
Head for the Hills! - generator verification (issue #6).

Everything else in SpawnScenario.lua was verified live in session 3. The
generator was not: `spawnGenerator`'s fuel-and-connect behaviour has never
executed, on either of its two branches. It is never switched on: the mod
fills the tank and wires it to the cabin, and the player flips the switch.

    spawn     the freshly placed generator, straight after a new world.
              Run this first, before doing anything else in the save.

    existing  the other branch: the cabin already has a generator, so the mod
              starts theirs instead of adding a second. Needs a coordinate with
              a real map generator - survey_candidates.py reports which of the
              #1 candidates have one. Re-fires OnNewGame in place.

    persist   re-check after a save-and-reload. A car spawned into geometry in
              session 3 looked fine until the reload and then came back a
              chunk-orphaned ghost, so "it exists" is not the same claim as
              "it survived".

Usage:

    python tests/verify_generator.py spawn
    python tests/verify_generator.py existing --at 9668,8782
    python tests/verify_generator.py persist --at 9670,8784

**Run this in a throwaway world.** `existing` rewrites sandbox vars and re-fires
OnNewGame, which is not something to do to a save you care about.

Requires: PZ running, a save loaded (the harness registers on OnGameStart), and
the PZTestPilot mod enabled. `harness_dead` while PZ is unfocused is the
tick-heartbeat false positive; read Zomboid/Lua/TestPilot/result.txt first.
"""

import argparse
import sys

from _pilot import (
    load, run_lua, parse, num, boolean, teleport,
    CommandTimeout, HarnessDead, HarnessError,
)

# Matches EXISTING_OBJECT_SCAN_RADIUS in SpawnScenario.lua. If that changes,
# change this, otherwise the check answers a question the mod is not asking.
SCAN_RADIUS = 12

# Where the mod is allowed to place the generator, from SpawnScenario.lua. The
# search radius is measured from the player and is only a sanity bound now; the
# rule that matters is GENERATOR_BUILDING_MAX_RELAXED, measured from the house.
# Keep these in step with the mod, otherwise the check answers a question the
# mod is not asking.
GENERATOR_MIN_RADIUS = 1
GENERATOR_SEARCH_RADIUS = 16
GENERATOR_BUILDING_MAX_RELAXED = 2

# The generator is never started for the player, so it never burns fuel and the
# cap can be demanded exactly at every phase. The old tolerance existed because
# a running generator consumes: measured at 10 down to 9.998 over a save, a
# reload and a couple of minutes. Kept small rather than zero because a save
# round trip is still free to round the float.
PERSIST_FUEL_TOLERANCE = 0.01


INSPECT_LUA = """
local R = __R__
local p = getPlayer()
if not p then return "NOPLAYER" end
local c = p:getCurrentSquare()
if not c then return "NOSQUARE" end
local cx, cy, cz = c:getX(), c:getY(), c:getZ()
local out = {}
local function add(k, v) table.insert(out, k .. "=" .. tostring(v)) end
--[[ Probe rather than assume: a getter this mod never called before may not
     exist on B42's IsoGenerator, and an unguarded call would kill the chunk
     and report as a dead harness. ]]
local function try(f) local ok, v = pcall(f) if ok then return v end return "ERR" end
add("player", cx .. "," .. cy .. "," .. cz)
local WELL_SPRITES = { ["camping_01_16"] = true }
local gens, wells = 0, 0
local best, bestDist = nil, 9999
local wellAt = "none"
for dx = -R, R do for dy = -R, R do
    local s = getSquare(cx + dx, cy + dy, cz)
    if s then
        local o = s:getObjects()
        for i = 0, o:size() - 1 do
            local ob = o:get(i)
            if instanceof(ob, "IsoGenerator") then
                gens = gens + 1
                local d = math.max(math.abs(dx), math.abs(dy))
                if d < bestDist then bestDist = d; best = ob end
            end
            local sp = ob:getSprite()
            local nm = sp and sp:getName()
            local isWell = nm ~= nil and WELL_SPRITES[nm] == true
            if not isWell then
                local okFc, fc = pcall(function() return ob:getFluidContainer() end)
                isWell = okFc and fc ~= nil
            end
            if isWell then
                wells = wells + 1
                if wellAt == "none" then wellAt = s:getX() .. "," .. s:getY() end
            end
        end
    end
end end
add("generators", gens)
add("wells", wells)
add("wellAt", wellAt)
if not best then return table.concat(out, " | ") end
local bs = best:getSquare()
add("genAt", bs:getX() .. "," .. bs:getY() .. "," .. bs:getZ())
add("genDist", bestDist)
add("fuel", try(function() return best:getFuel() end))
add("maxFuel", try(function() return best:getMaxFuel() end))
add("activated", try(function() return best:isActivated() end))
add("connected", try(function() return best:isConnected() end))
add("condition", try(function() return best:getCondition() end))
add("genSprite", try(function() local s = best:getSprite() return s and s:getName() end))
add("genInBuilding", bs:getBuilding() ~= nil)
add("genOutside", bs:isOutside())
--[[ Distance to the nearest building tile, which is what the placement rule is
     actually written in terms of. The generator belongs against the house, so
     this is the number under test, not the distance from the player. ]]
local gb = 9999
for bx = -6, 6 do for by = -6, 6 do
    local s2 = getSquare(bs:getX() + bx, bs:getY() + by, bs:getZ())
    if s2 and s2:getBuilding() ~= nil then
        local d2 = math.max(math.abs(bx), math.abs(by))
        if d2 < gb then gb = d2 end
    end
end end
add("genToBuilding", gb)
return table.concat(out, " | ")
"""


# Narrow the re-fired OnNewGame down to the generator. Season 0 falls off the
# end of SEASON_START_MONTH, which makes applySeason a no-op rather than
# shunting the clock into another month on the way past.
ARM_LUA = """
local sv = SandboxVars and SandboxVars.HeadForTheHills
if not sv then return "NOOPTIONS" end
sv.SpawnVehicle = false
sv.SpawnWell = false
sv.SpawnStartingEquipment = false
sv.Season = 0
sv.SpawnGenerator = true
sv.GeneratorFueled = true
sv.GeneratorConnected = true
return "armed | triggerEvent=" .. type(triggerEvent)
"""


TRIGGER_LUA = """
local p = getPlayer()
if not p then return "NOPLAYER" end
if type(triggerEvent) ~= "function" then return "NOTRIGGER" end
local ok, err = pcall(function() triggerEvent("OnNewGame", p, p:getCurrentSquare()) end)
return "triggered=" .. tostring(ok) .. " | err=" .. tostring(err)
"""


def inspect(cfg, radius=SCAN_RADIUS):
    """Scan around the player and return the generator/well picture."""
    return parse(run_lua(cfg, INSPECT_LUA.replace("__R__", str(radius))))


def report(label, fields):
    print(f"  {label}:")
    if fields.get("_raw"):
        print(f"    {fields['_raw']}")
        return
    for key, value in fields.items():
        print(f"    {key:14} {value}")


def check_running(fields, where, fuel_tolerance=0.0):
    """The claim under test: fuelled to the cap, connected, and NOT running.

    Fuel is checked against the generator's own getMaxFuel() rather than 100.
    setFuel clamps down to that cap (measured at 10 on B42.20) and the UI draws
    the cap as 100%, so asking for 100 quietly leaves the tank at a tenth.

    Switched off is a requirement, not an absence of one. The mod fills and
    wires a generator but never flips the switch: a machine running before the
    player has touched it burns fuel they did not choose to spend and makes
    noise from the first second of the game.
    """
    problems = []

    count = num(fields, "generators")
    if not count:
        return [f"no generator within {SCAN_RADIUS} tiles of {where}"]

    fuel, max_fuel = num(fields, "fuel"), num(fields, "maxFuel")
    if fuel is None or max_fuel is None:
        problems.append(f"fuel unreadable (fuel={fields.get('fuel')}, "
                        f"maxFuel={fields.get('maxFuel')})")
    elif fuel < max_fuel - fuel_tolerance:
        problems.append(f"fuel {fuel} below the cap of {max_fuel}"
                        + (f" by more than the {fuel_tolerance} a save round "
                           "trip could have rounded away"
                           if fuel_tolerance else ""))

    if boolean(fields, "activated") is not False:
        problems.append(f"running when it should be switched off "
                        f"(activated={fields.get('activated')})")
    if boolean(fields, "connected") is not True:
        problems.append(f"not connected (connected={fields.get('connected')})")

    return problems


def check_placement(fields):
    """Against the cabin, not inside it, and not blocking the way in.

    The rule under test is the distance to the nearest *building* tile, not to
    the player. A generator powers the building it is wired to, so beside the
    wall is where one belongs, and that is the opposite of the well's rule.
    """
    problems = []
    if boolean(fields, "genInBuilding") is not False:
        problems.append("generator landed inside a building footprint")
    if boolean(fields, "genOutside") is not True:
        problems.append("generator landed indoors")

    to_building = num(fields, "genToBuilding")
    if to_building is None:
        problems.append("no distance to the building reported")
    elif to_building > GENERATOR_BUILDING_MAX_RELAXED:
        problems.append(f"generator {to_building:.0f} tiles from the nearest "
                        f"building; it is supposed to sit against the house, "
                        f"within {GENERATOR_BUILDING_MAX_RELAXED}")

    distance = num(fields, "genDist")
    if distance is None:
        problems.append("no distance reported")
    elif distance < GENERATOR_MIN_RADIUS:
        problems.append(f"generator only {distance:.0f} tiles from the player")
    elif distance > GENERATOR_SEARCH_RADIUS:
        problems.append(f"generator {distance:.0f} tiles out, past the "
                        f"{GENERATOR_SEARCH_RADIUS}-tile search limit")

    if num(fields, "wells") and fields.get("wellAt") == ",".join(
            fields.get("genAt", "").split(",")[:2]):
        problems.append("well and generator share a square")

    return problems


def verdict(problems, ok_message):
    if problems:
        print("\nFAIL")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"\nPASS - {ok_message}")
    return 0


def phase_spawn(cfg, args):
    """The freshly placed generator, straight after a new world."""
    print("Fresh-spawn branch: a generator the mod placed and started itself.\n")
    fields = inspect(cfg, args.radius)
    report("at spawn", fields)

    # Without #2 the player still spawns wherever vanilla puts them, so a house
    # with its own generator inside is possible. That takes the other branch,
    # and judging it against the placement rules would report a failure that is
    # really a mis-aimed test.
    if boolean(fields, "genInBuilding") is True:
        print("\nINCONCLUSIVE - the nearest generator is inside a building, so "
              "this is\n  a map generator the mod adopted, not one it placed. "
              "Roll another world\n  for the fresh branch; this save can still "
              "serve `existing`.")
        report("generator state", {k: fields[k] for k in
                                 ("fuel", "maxFuel", "activated", "connected")
                                 if k in fields})
        return 3

    problems = check_running(fields, "the player") + check_placement(fields)
    code = verdict(problems, "generator placed outside, fuelled to its cap, "
                             "fuelled and connected, switched off")

    where = fields.get("genAt", "").split(",")
    if len(where) >= 2:
        print(f"\nNext: save and reload, then\n"
              f"  python tests/verify_generator.py persist --at {where[0]},{where[1]}")
    return code


def phase_existing(cfg, args):
    """The other branch: start the cabin's own generator, do not add a second."""
    print("Existing-generator branch: the mod should start what is already "
          "there and not add a second.\n")
    if args.at:
        teleport(cfg, args.at)

    before = inspect(cfg, args.radius)
    report("before", before)

    count = num(before, "generators")
    if not count:
        print("\nSKIP - no generator here, so this branch cannot be exercised.")
        print("       Run survey_candidates.py and pick a coordinate reporting "
              "existingGenerator=true.")
        return 3
    # The discriminator is no longer "is it running", because the mod never
    # starts one. It is whether the generator is already in the state the mod
    # would put it in: a map generator is built with no fuel and disconnected
    # (MOGenerator.lua), so anything else here means something already touched
    # it and the branch cannot be told apart from the starting conditions.
    if boolean(before, "connected") is True and (num(before, "fuel") or 0) > 0:
        print("\nSKIP - the generator here is already fuelled and connected, so "
              "setting it up again would prove nothing.")
        return 3

    armed = run_lua(cfg, ARM_LUA)
    print(f"\n  arm: {armed}")
    if "NOOPTIONS" in str(armed):
        print("\nFAIL\n  - SandboxVars.HeadForTheHills is missing; the mod did "
              "not load in this save.")
        return 1
    if "triggerEvent=function" not in str(armed):
        print("\nFAIL\n  - triggerEvent is not a callable global, so OnNewGame "
              "cannot be re-fired from here.")
        return 1

    fired = run_lua(cfg, TRIGGER_LUA)
    print(f"  fire: {fired}")
    if "triggered=true" not in str(fired):
        print("\nFAIL\n  - OnNewGame did not fire.")
        return 1

    after = inspect(cfg, args.radius)
    print()
    report("after", after)

    problems = check_running(after, "the player")
    if num(after, "generators") != count:
        problems.append(
            f"generator count went {count:.0f} -> {num(after, 'generators'):.0f}; "
            "the mod added one instead of starting the existing one")
    if after.get("genAt") != before.get("genAt"):
        problems.append(f"nearest generator moved from {before.get('genAt')} "
                        f"to {after.get('genAt')}")

    return verdict(problems, "the map's own generator was fuelled and started, "
                             "and no second one appeared")


def phase_persist(cfg, args):
    """Same generator, after a save and reload."""
    print("Persistence: the generator should still be there, still fuelled and wired.\n")
    if args.at:
        teleport(cfg, args.at)

    fields = inspect(cfg, args.radius)
    report("after reload", fields)

    problems = check_running(fields, "the given coordinates",
                             fuel_tolerance=PERSIST_FUEL_TOLERANCE)
    return verdict(problems, "generator survived the reload with its fuel and "
                             "state intact")


PHASES = {
    "spawn": phase_spawn,
    "existing": phase_existing,
    "persist": phase_persist,
}


def coordinates(text):
    try:
        x, y = (int(part) for part in text.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError("expected X,Y - e.g. 9668,8782")
    return x, y


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("phase", choices=sorted(PHASES))
    parser.add_argument("--at", type=coordinates,
                        help="teleport here first, as X,Y")
    parser.add_argument("--radius", type=int, default=SCAN_RADIUS,
                        help=f"scan radius in tiles (default {SCAN_RADIUS}, "
                             "matching the mod)")
    args = parser.parse_args()

    try:
        return PHASES[args.phase](load(), args)
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
