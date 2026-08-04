"""
Head for the Hills! - starting equipment verification (issue #9).

The mod handed the player an ID card on top of the one vanilla already gives
every new character in shared/Items/SpawnItems.lua, so anyone who ticked "ID
Card" in the picker spawned holding two. The fix is a skip-if-already-carried
guard on the equipment loop, general rather than ID-card specific: vanilla also
issues a badge to a ranger, police officer or firefighter and a pager to a
doctor, and another mod's loadout collides the same way.

This re-fires OnNewGame in a loaded world, the way verify_generator.py's
`existing` phase does, and runs it twice over the same item:

    pass 1  an item the player does not carry must be issued
    pass 2  the same item, now carried, must NOT be issued again

Testing only the second half would pass just as well if the loop had stopped
issuing anything at all, which is why both run.

It deliberately does NOT test with an ID card, even though that is the bug.
triggerEvent re-runs *every* registered OnNewGame handler, vanilla's included,
and vanilla's grants a card unconditionally - so a card count going 1 -> 2 in
here says nothing about our guard. Measured live: it went 1 -> 2 while
console.txt carried our own "already carrying Base.IDcard" line from the same
event. A tool item vanilla never grants isolates our loop from theirs. The
real ID-card case is one look at a freshly created character.

Because vanilla's handler re-runs each time, every pass also re-issues the
vanilla loadout: more ID cards, more keyrings. Harmless in a throwaway world
and another reason not to point this at a save you care about.

    python tests/verify_equipment.py

**Run this in a throwaway world.** It rewrites sandbox vars and re-fires
OnNewGame, which is not something to do to a save you care about.

Requires: PZ running with a save loaded, the PZTestPilot mod enabled, and the
mod's current Lua actually loaded - quit PZ to desktop and back in after any
edit to SpawnScenario.lua, or this measures the previous build.
"""

import sys

from _pilot import (
    load, run_lua, parse, num,
    CommandTimeout, HarnessDead, HarnessError,
)

# The collision case. Vanilla grants this to every character unconditionally.
DUPLICATE_TYPE = "Base.IDcard"

# Candidates for the "not carried yet" half. The first one the player does not
# already have is used, because a starting profession or another mod may well
# have supplied any single item on this list.
FRESH_CANDIDATES = [
    "Base.Hammer", "Base.Screwdriver", "Base.Crowbar", "Base.Saw",
    "Base.HandTorch", "Base.Wrench",
]


COUNT_LUA = """
local inv = getPlayer():getInventory()
local items = inv:getItems()
local wanted = { %s }
local counts = {}
for i = 1, #wanted do counts[wanted[i]] = 0 end
for i = 0, items:size() - 1 do
    local t = tostring(items:get(i):getFullType())
    if counts[t] ~= nil then counts[t] = counts[t] + 1 end
end
local out = {}
for i = 1, #wanted do
    table.insert(out, wanted[i] .. "=" .. counts[wanted[i]])
end
return table.concat(out, " | ")
"""


# Everything except the equipment is switched off, so a re-fired OnNewGame does
# not also try to park a second car or dig a second well next to the player.
ARM_LUA = """
local sv = SandboxVars and SandboxVars.HeadForTheHills
if not sv then return "NOOPTIONS" end
sv.SpawnVehicle = false
sv.SpawnWell = false
sv.SpawnGenerator = false
sv.GeneratorFueledAndRunning = false
sv.ZombieFreeRadius = 0
sv.Season = 0
sv.SpawnStartingEquipment = true
sv.StartingEquipmentList = "%s"
return "armed | list=" .. tostring(sv.StartingEquipmentList)
    .. " | triggerEvent=" .. type(triggerEvent)
"""


TRIGGER_LUA = """
local p = getPlayer()
if not p then return "NOPLAYER" end
if type(triggerEvent) ~= "function" then return "NOTRIGGER" end
local ok, err = pcall(function() triggerEvent("OnNewGame", p, p:getCurrentSquare()) end)
return "triggered=" .. tostring(ok) .. " | err=" .. tostring(err)
"""


def count(cfg, types):
    """How many of each full type the player is holding, top level."""
    quoted = ", ".join(f'"{t}"' for t in types)
    return parse(run_lua(cfg, COUNT_LUA % quoted))


def fire(cfg, item):
    """Arm the sandbox with one item and re-fire OnNewGame."""
    armed = run_lua(cfg, ARM_LUA % item)
    if "NOOPTIONS" in str(armed):
        raise HarnessError("SandboxVars.HeadForTheHills is missing; the mod "
                           "did not load in this save")
    if "triggerEvent=function" not in str(armed):
        raise HarnessError("triggerEvent is not a callable global, so "
                           "OnNewGame cannot be re-fired from here")
    fired = run_lua(cfg, TRIGGER_LUA)
    if "triggered=true" not in str(fired):
        raise HarnessError(f"OnNewGame did not fire: {fired}")
    return fired


def main():
    cfg = load()
    print("Starting equipment: the loop must issue an item the player lacks, "
          "and skip it\nthe second time round once they are carrying it.\n")

    before = count(cfg, FRESH_CANDIDATES)
    item = next((t for t in FRESH_CANDIDATES if not num(before, t)), None)
    if not item:
        print("SKIP - the player already carries every candidate item, so this "
              "run could not\n       tell a working loop from a dead one. Drop "
              "one and try again.")
        return 3
    print(f"  using {item}, which this character is not carrying")

    fire(cfg, item)
    first = num(count(cfg, [item]), item)
    print(f"  pass 1: {item} x{first:.0f}")

    fire(cfg, item)
    second = num(count(cfg, [item]), item)
    print(f"  pass 2: {item} x{second:.0f}")

    problems = []
    if first != 1:
        problems.append(
            f"{item} came back x{first:.0f} after the first spawn, expected 1; "
            "the loop is not issuing equipment at all")
    elif second != 1:
        problems.append(
            f"{item} went {first:.0f} -> {second:.0f} on the second spawn; the "
            "guard did not skip an item the player was already carrying")

    if problems:
        print("\nFAIL")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"\nPASS - {item} was issued once and not duplicated on the second "
          "pass")
    print("\nThe ID card case cannot be measured here, because re-firing "
          "OnNewGame also\nre-runs vanilla's own handler and that grants a card "
          "unconditionally. Check it\non a freshly created character with 'ID "
          "Card' ticked in the picker.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except HarnessDead as exc:
        print(f"\n[DEAD] {exc}")
        print("       If PZ is alive and just unfocused, this is the "
              "tick-heartbeat false positive.")
        print("       Check Zomboid/Lua/TestPilot/result.txt and log.txt.")
        sys.exit(2)
    except CommandTimeout as exc:
        print(f"\n[TIMEOUT] {exc}")
        sys.exit(2)
    except HarnessError as exc:
        print(f"\n[HARNESS] {exc}")
        sys.exit(2)
