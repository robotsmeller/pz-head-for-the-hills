"""
Head for the Hills! - custom start coordinate (issue #12).

A sandbox setting redirects the start to a coordinate the player typed, instead
of one of the twelve cabins. It works because nothing builds the point list from
the option: MapSpawnSelect:clickNext:644 freezes a live reference to the region
table SpawnRegion.lua inserted, the sandbox screen fills SandboxVars at
SandboxOptions.lua:972, and CharacterCreationProfession.initWorld:1086 reads that
same table afterwards. Overwriting its points in between redirects the spawn.

What this checks, in a loaded world:

    parser      every accepted and rejected coordinate shape, from shared Lua
    redirect    setCustomPoint swaps the twelve for one point and back again
    wrap        the sandbox screen hook is installed on the class
    option      the setting reached SandboxVars

The parser and the redirect are the whole risk surface and both are plain Lua,
so they are tested properly here rather than by eye.

What this canNOT check: that typing into the box on the sandbox screen ends with
the player waking at that coordinate. That path runs through the main menu,
which a harness registering on OnGameStart cannot reach. It also cannot check
the water rescue, which needs a character created at a coordinate in a lake.

    python tests/verify_custom_spawn.py

Requires: PZ running with a save loaded, the PZTestPilot mod enabled, and the
mod's current Lua loaded - quit to desktop and back in after editing it.
"""

import sys

from _pilot import (
    load, run_lua, parse, num, boolean,
    CommandTimeout, HarnessDead, HarnessError,
)

EXPECTED_CABINS = 12

# Each row is the typed text and what it should produce: either "x,y" for a
# point, or the short reason parsePoint returns when it refuses.
PARSE_CASES = [
    ("9668,8775", "9668,8775"),
    ("9668, 8775", "9668,8775"),
    ("9668 8775", "9668,8775"),
    ("9668;8775", "9668,8775"),
    ("  9668,8775  ", "9668,8775"),
    ("", "empty"),
    ("   ", "empty"),
    ("abc", "format"),
    ("9668", "format"),
    ("9668,8775,3", "format"),
    ("9668.5,8775", "format"),
    ("-5,10", "negative"),
]


def lua_cases():
    rows = ", ".join('{ "%s", "%s" }' % (text, want) for text, want in PARSE_CASES)
    return "{ " + rows + " }"


CHECK_LUA = """
local out = {}
local function add(k, v) table.insert(out, k .. "=" .. tostring(v)) end

if not HFTH_SpawnRegion then return "NOEXPORT" end
add("parseType", type(HFTH_SpawnRegion.parsePoint))
add("setType", type(HFTH_SpawnRegion.setCustomPoint))
if type(HFTH_SpawnRegion.parsePoint) ~= "function" then
    return table.concat(out, " | ")
end

local cases = __CASES__
local failures = {}
for _, case in ipairs(cases) do
    local point, reason = HFTH_SpawnRegion.parsePoint(case[1])
    local got
    if point then got = point.posX .. "," .. point.posY else got = tostring(reason) end
    if got ~= case[2] then
        table.insert(failures, "[" .. case[1] .. "] gave " .. got .. " wanted " .. case[2])
    end
end
add("parseCases", #cases)
add("parseFailures", #failures == 0 and "none" or table.concat(failures, " / "))

--[[ posZ is forced rather than parsed, because a hand-typed z is a way to
     spawn inside terrain. ]]
local typed = HFTH_SpawnRegion.parsePoint("1234,5678")
add("forcedPosZ", typed and typed.posZ)

--[[ Redirect a stand-in region rather than the real one, so a test run cannot
     leave the live table pointed somewhere odd. ]]
local fake = { name = HFTH_SpawnRegion.NAME, points = {} }
HFTH_SpawnRegion.setCustomPoint(fake, typed)
local custom = fake.points.unemployed
add("customCount", custom and #custom or 0)
add("customAt", custom and custom[1] and (custom[1].posX .. "," .. custom[1].posY) or "none")
add("customFlag", HFTH_SpawnRegion.hasCustomPoint(fake))

--[[ Every profession has to follow the custom point too, or the coordinate
     only applies to some occupations. ]]
local keys, wrong = 0, 0
for _, list in pairs(fake.points) do
    keys = keys + 1
    if #list ~= 1 or list[1].posX ~= 1234 then wrong = wrong + 1 end
end
add("customKeys", keys)
add("customKeysWrong", wrong)

--[[ Clearing has to put the twelve back. A coordinate typed once and then
     removed must not survive in the region table. ]]
HFTH_SpawnRegion.setCustomPoint(fake, nil)
local restored = fake.points.unemployed
add("restoredCount", restored and #restored or 0)
add("restoredFlag", HFTH_SpawnRegion.hasCustomPoint(fake))

add("screenWrapped", SandboxOptionsScreen ~= nil
    and SandboxOptionsScreen.HFTH_customSpawnWrapped == true)
local sv = SandboxVars and SandboxVars.HeadForTheHills
add("optionPresent", sv ~= nil and sv.CustomSpawnPoint ~= nil)
return table.concat(out, " | ")
"""


def main():
    cfg = load()
    print("Custom start coordinate: the parser and the redirect must both hold.\n")

    fields = parse(run_lua(cfg, CHECK_LUA.replace("__CASES__", lua_cases())))
    if fields.get("_raw"):
        print(f"FAIL\n  - {fields['_raw']}")
        return 1

    for key, value in fields.items():
        print(f"  {key:18} {value}")

    problems = []

    if fields.get("parseType") != "function":
        problems.append(
            "HFTH_SpawnRegion.parsePoint is missing, so SpawnRegion.lua is the "
            "old version; quit to desktop and back in")
        print("\nFAIL")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    if fields.get("parseFailures") != "none":
        problems.append(f"parser disagreed: {fields.get('parseFailures')}")
    if num(fields, "forcedPosZ") != 0:
        problems.append(
            f"posZ came back as {fields.get('forcedPosZ')}, expected 0; a "
            "non-zero floor can put the player inside terrain")

    if num(fields, "customCount") != 1:
        problems.append(
            f"a custom point produced {num(fields, 'customCount'):.0f} spawn "
            "points, expected exactly 1")
    if fields.get("customAt") != "1234,5678":
        problems.append(
            f"the custom point landed at {fields.get('customAt')}, expected "
            "1234,5678")
    if boolean(fields, "customFlag") is not True:
        problems.append("hasCustomPoint did not recognise its own custom point")
    if num(fields, "customKeysWrong"):
        problems.append(
            f"{num(fields, 'customKeysWrong'):.0f} of "
            f"{num(fields, 'customKeys'):.0f} profession keys did not follow "
            "the custom point, so the coordinate would only apply to some jobs")

    if num(fields, "restoredCount") != EXPECTED_CABINS:
        problems.append(
            f"clearing the coordinate left {num(fields, 'restoredCount'):.0f} "
            f"points, expected the {EXPECTED_CABINS} cabins back; a coordinate "
            "typed once would survive into a later character")
    if boolean(fields, "restoredFlag") is not False:
        problems.append("hasCustomPoint still reports a custom point after clearing")

    if boolean(fields, "screenWrapped") is not True:
        problems.append(
            "the sandbox screen hook is not installed, so a typed coordinate "
            "would never be applied; CustomSpawnPoint.lua did not run")
    if boolean(fields, "optionPresent") is not True:
        problems.append(
            "SandboxVars.HeadForTheHills.CustomSpawnPoint is missing, so the "
            "setting is not in sandbox-options.txt or this save predates it")

    if problems:
        print("\nFAIL")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print(f"\nPASS - {len(PARSE_CASES)} coordinate shapes parsed as expected, "
          f"the redirect\n       swaps in one point across "
          f"{num(fields, 'customKeys'):.0f} profession keys and puts the "
          f"{EXPECTED_CABINS}\n       cabins back when cleared, and the sandbox "
          "hook is installed")
    print("\nStill needs eyes: type a coordinate on the sandbox screen and check "
          "you wake\nup there. That path runs through the main menu, which the "
          "harness cannot reach.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except HarnessDead as exc:
        print(f"\n[DEAD] {exc}")
        print("       If PZ is alive and just unfocused, this is the "
              "tick-heartbeat false positive.")
        sys.exit(2)
    except CommandTimeout as exc:
        print(f"\n[TIMEOUT] {exc}")
        sys.exit(2)
    except HarnessError as exc:
        print(f"\n[HARNESS] {exc}")
        sys.exit(2)
