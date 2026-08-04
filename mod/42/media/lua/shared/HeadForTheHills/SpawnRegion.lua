-- Head for the Hills! - "Remote Cabin" starting location
--
-- Adds one entry to the Starting Location list on the new-game screen. Picking
-- it wakes the player in one of the cabins below, chosen at random by the game.
--
-- WHY A HOOK RATHER THAN A spawnregions.lua FILE:
-- SpawnRegionMgr.getSpawnRegionsAux() only reads media/maps/<map>/spawnregions.lua
-- when getWorld():getMap() contains no ";". That name is semicolon-joined as soon
-- as extra maps load, which is the normal case here (Rob runs MoreMapsB42), so a
-- shipped file would be silently ignored on exactly the installs this mod is for.
-- getSpawnRegions() fires OnSpawnRegionsLoaded with the assembled list, so we
-- append to that instead and work either way.
--
-- MULTIPLAYER: vanilla only fires this event when not isClient(), so a connected
-- client never runs the handler and takes the server's list, which is the correct
-- behaviour. Hooking it costs nothing on a client that never fires it.

local REGION_NAME = "Remote Cabin"

-- Interior squares, one per cabin, measured live rather than read off the map
-- site: each is the standable, in-a-room tile nearest the middle of the building
-- so the player wakes up in the room instead of pressed against a wall.
--
-- All twelve are in the mod, hand-picked by Rob (session 7). The spread is
-- deliberate and not an oversight waiting to be tidied: the buildings run from a
-- 3x3 shed to a 20x11 farmhouse, and the straight-line haul to the nearest town
-- runs 610 tiles (#9, Riverside) to 2383 (#7, Brandenburg), so a random draw
-- varies how hard the start is. Do not cut the list back to the ones that look
-- most cabin-like.
local CABINS = {
    { posX = 12473, posY = 8919, posZ = 0 },  -- 1: 8x8, 2 rooms
    { posX = 12719, posY = 8749, posZ = 0 },  -- 2: 13x9, 7 rooms
    { posX = 13632, posY = 7224, posZ = 0 },  -- 3: 5x8, 3 rooms
    { posX = 9668,  posY = 8775, posZ = 0 },  -- 4: 8x5, 3 rooms, has a well already
    { posX = 9049,  posY = 8733, posZ = 0 },  -- 5: 9x10, 5 rooms
    { posX = 6098,  posY = 8055, posZ = 0 },  -- 6: 20x11, 7 rooms (farmhouse)
    { posX = 4246,  posY = 7227, posZ = 0 },  -- 7: 11x5, 3 rooms
    { posX = 2165,  posY = 11218, posZ = 0 }, -- 8: 5x5, 1 room, far corner
    { posX = 6484,  posY = 6171, posZ = 0 },  -- 9: 6x7, 1 room
    { posX = 8081,  posY = 7621, posZ = 0 },  -- 10: 10x9, 5 rooms
    { posX = 9505,  posY = 6608, posZ = 0 },  -- 11: 6x6, 2 rooms (army storage)
    { posX = 14050, posY = 5195, posZ = 0 },  -- 12: 3x3, 1 room (shed)
}

--- Every profession key the game might look this region up by.
--- Vanilla's per-town spawnpoints.lua keys its point lists by profession, so a
--- region that only defines one key sends everyone else somewhere else. Vanilla's
--- own synthetic regions (the server spawn point and the safehouse respawn in
--- MapSpawnSelect.lua) define nothing but `unemployed`, which says there is a
--- fallback to that key - so `unemployed` is listed first and always present,
--- and the rest are belt and braces.
--- Professions are enumerated rather than hardcoded so a mod-added one is covered
--- too. getType() answers a namespaced id ("base:burgerflipper", measured live);
--- the vanilla files key on the bare name, so the namespace is stripped.
local function professionKeys()
    local keys = { "unemployed" }
    if not CharacterProfessionDefinition then return keys end

    local ok, list = pcall(function()
        return CharacterProfessionDefinition.getProfessions()
    end)
    if not ok or not list then return keys end

    for i = 0, list:size() - 1 do
        local profession = list:get(i)
        local id = profession and tostring(profession:getType())
        if id then
            local bare = string.match(id, "([^:]+)$") or id
            if bare ~= "" and bare ~= "unemployed" then
                table.insert(keys, bare)
            end
        end
    end
    return keys
end

--- One shared point list under every profession key, so the cabin the player
--- wakes in does not depend on the occupation they chose. Vanilla shares list
--- tables between keys the same way (see poor_houses in any town's file).
local function buildPoints()
    local points = {}
    for _, key in ipairs(professionKeys()) do
        points[key] = CABINS
    end
    return points
end

local function onSpawnRegionsLoaded(regions)
    if not regions then return end

    -- MapSpawnSelect calls getSpawnRegions() several times while the screen is
    -- open and each call fires this event, so refuse to add a second copy.
    for _, region in ipairs(regions) do
        if region.name == REGION_NAME then return end
    end

    table.insert(regions, { name = REGION_NAME, points = buildPoints() })
end

Events.OnSpawnRegionsLoaded.Add(onSpawnRegionsLoaded)
