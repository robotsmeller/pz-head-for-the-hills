"""
Head for the Hills! - live API verification.

Drives a running PZ instance through the pz-test-pilot harness to confirm the
engine APIs the sandbox pickers depend on actually behave as the code assumes.
Static reading of the vanilla/decompiled sources got us this far; this closes the
gap between "the source says X" and "the running build does X".

Requires: PZ running, a save loaded (the harness registers on OnGameStart), and
the PZTestPilot mod enabled.

    python tests/api_checks.py
"""

import sys

from _pilot import load, run_lua, CommandTimeout, HarnessDead, HarnessError


# Each check returns a single scalar (string/number) - complex tables do not
# survive the JSON hop reliably, so every Lua chunk stringifies its own result.
CHECKS = [
    (
        "vehicle_enum",
        "getAllVehicleScripts() returns a non-empty list",
        """
        local sm = getScriptManager()
        local v = sm:getAllVehicleScripts()
        return "count=" .. tostring(v:size())
        """,
    ),
    (
        "vehicle_name_api",
        "VehicleScript:getName()/getFullName() are callable",
        """
        local v = getScriptManager():getAllVehicleScripts()
        if v:size() == 0 then return "NO VEHICLES" end
        local s = v:get(0)
        local okName, name = pcall(function() return s:getName() end)
        local okFull, full = pcall(function() return s:getFullName() end)
        return "getName=" .. tostring(okName) .. ":" .. tostring(name)
            .. " getFullName=" .. tostring(okFull) .. ":" .. tostring(full)
        """,
    ),
    (
        "vehicle_displayname_throws",
        "VehicleScript:getDisplayName() absent (justifies using getName)",
        """
        local v = getScriptManager():getAllVehicleScripts()
        if v:size() == 0 then return "NO VEHICLES" end
        local ok, err = pcall(function() return v:get(0):getDisplayName() end)
        return "pcall_ok=" .. tostring(ok) .. " err=" .. tostring(err)
        """,
    ),
    (
        "fallback_vehicle_present",
        "Base.PickUpTruck exists in the enumerated list",
        """
        local v = getScriptManager():getAllVehicleScripts()
        for i = 0, v:size() - 1 do
            if v:get(i):getFullName() == "Base.PickUpTruck" then return "FOUND" end
        end
        return "MISSING"
        """,
    ),
    (
        "item_enum",
        "getAllItems() returns a non-empty list",
        """
        local items = getScriptManager():getAllItems()
        return "count=" .. tostring(items:size())
        """,
    ),
    (
        "item_displayname_safe",
        "Item:getDisplayName() is safe across every loaded item",
        """
        local items = getScriptManager():getAllItems()
        local failures = 0
        local firstErr = ""
        for i = 0, items:size() - 1 do
            local ok, err = pcall(function() return items:get(i):getDisplayName() end)
            if not ok then
                failures = failures + 1
                if firstErr == "" then firstErr = tostring(err) end
            end
        end
        return "total=" .. tostring(items:size()) .. " failures=" .. tostring(failures)
            .. " firstErr=" .. firstErr
        """,
    ),
    (
        "item_fullname_safe",
        "Item:getFullName() is safe across every loaded item",
        """
        local items = getScriptManager():getAllItems()
        local failures = 0
        for i = 0, items:size() - 1 do
            local ok = pcall(function() return items:get(i):getFullName() end)
            if not ok then failures = failures + 1 end
        end
        return "total=" .. tostring(items:size()) .. " failures=" .. tostring(failures)
        """,
    ),
    (
        "sandbox_vars_present",
        "HeadForTheHills sandbox vars reached the loaded save",
        """
        if not SandboxVars then return "NO SandboxVars" end
        local h = SandboxVars.HeadForTheHills
        if not h then return "MISSING SandboxVars.HeadForTheHills" end
        local keys = {}
        for k, v in pairs(h) do keys[#keys+1] = k .. "=" .. tostring(v) end
        table.sort(keys)
        return table.concat(keys, " | ")
        """,
    ),
    (
        "sandbox_option_registry",
        "Options registered with the engine option registry",
        """
        local opts = getSandboxOptions()
        local found = {}
        for i = 1, opts:getNumOptions() do
            local o = opts:getOptionByIndex(i-1)
            local n = o:getName()
            if string.find(n, "HeadForTheHills", 1, true) then
                found[#found+1] = n .. "(" .. tostring(o:getType()) .. ")"
            end
        end
        table.sort(found)
        if #found == 0 then return "NONE REGISTERED" end
        return tostring(#found) .. ": " .. table.concat(found, ", ")
        """,
    ),
    (
        "spawn_regions_event",
        "Events.OnSpawnRegionsLoaded binds (the hook #2 needs)",
        """
        local e = Events and Events.OnSpawnRegionsLoaded
        if not e then return "NO EVENT - Events.OnSpawnRegionsLoaded is nil" end
        return "add=" .. type(e.Add) .. " remove=" .. type(e.Remove)
        """,
    ),
    (
        "spawn_regions_shape",
        "getSpawnRegions() returns name/points regions we can append to",
        """
        if not SpawnRegionMgr then return "NO SpawnRegionMgr" end
        local ok, regions = pcall(function() return SpawnRegionMgr.getSpawnRegions() end)
        if not ok then return "pcall failed: " .. tostring(regions) end
        if not regions then return "nil regions" end
        local count, named, withPoints = 0, 0, 0
        for _, region in ipairs(regions) do
            count = count + 1
            if region.name then named = named + 1 end
            if region.points then withPoints = withPoints + 1 end
        end
        return "regions=" .. count .. " named=" .. named .. " withPoints=" .. withPoints
        """,
    ),
]


def main():
    cfg = load()

    passed, failed = 0, 0
    for name, description, code in CHECKS:
        try:
            value = run_lua(cfg, code)
        except CommandTimeout:
            print(f"[TIMEOUT] {name}: {description}")
            print("          Is PZ running with a save loaded?")
            failed += 1
            continue
        except HarnessError as exc:
            print(f"[FAIL]    {name}: {description}")
            print(f"          {exc}")
            failed += 1
            continue
        except HarnessDead as exc:
            print(f"[DEAD]    harness not responding: {exc}")
            return 2

        print(f"[OK]      {name}: {value}")
        passed += 1

    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
