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
-- Every one is in the mod, hand-picked by Rob (sessions 7 and 10). The spread is
-- deliberate and not an oversight waiting to be tidied: the buildings run from a
-- one-room cabin to a 20x11 farmhouse, and the straight-line haul to the town
-- runs 610 tiles (#9, Riverside) to 2383 (#7, Brandenburg), so a random draw
-- varies how hard the start is. Do not cut the list back to the ones that look
-- most cabin-like.
--
-- 1-12 were measured live as interior squares. 13-17 came off the map site in
-- session 10 and have not had that treatment, so each is the coordinate Rob
-- picked rather than a verified in-a-room tile. The spawn code copes either way:
-- a coordinate that lands outside the building still gets its well, generator
-- and cabin key, because those measure from the nearest building rather than
-- from the player.
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
    { posX = 14070, posY = 5203, posZ = 0 },  -- 12: the cabin at this site
                                              --     (14050,5195 was its shed)
    { posX = 3818,  posY = 12538, posZ = 0 }, -- 13: far south-west
    { posX = 8059,  posY = 7620, posZ = 0 },  -- 14: 22 tiles west of #10, see below
    { posX = 10208, posY = 6799, posZ = 0 },  -- 15
    { posX = 11242, posY = 8952, posZ = 0 },  -- 16
    { posX = 6392,  posY = 5900, posZ = 0 },  -- 17
}

-- #14 sits 22 tiles from #10, which is further apart than the widest building in
-- this list, so it is kept as its own entry rather than folded in. If it turns
-- out to be the same property from a different corner, the only cost is that
-- that property draws twice as often as the others.
--
-- Three of the coordinates Rob supplied in session 10 were already here and were
-- not added again: 9049,8732 is #5, 13631,7222 is #3, and 6482,6168 is #9, each
-- within three tiles of the entry already in the list.

-- Exported for the client-side screen hook, which has to name the same region
-- to find its row on the Starting Location list. Read lazily over there, inside
-- the wrapped methods, so the order shared and client Lua load in does not
-- matter and neither file has to hold a second copy of the name.
HFTH_SpawnRegion = {
    NAME = REGION_NAME,
    CABINS = CABINS,
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

-- ----------------------------------------------- custom spawn point (#12) ---
--
-- The table this file inserts is the same object MapSpawnSelect freezes at
-- clickNext:644, and CharacterCreationProfession.initWorld:1086 reads that exact
-- object back at world creation before taking .points[profession] at 1097. So
-- overwriting the points at any moment before world creation redirects the
-- spawn, with no second mechanism needed.
--
-- The client hook does it from the sandbox screen, because PLAY there is the
-- first moment SandboxVars exists (SandboxOptions.lua:972 calls setSandboxVars,
-- which runs options:toLua()). An earlier read gets the option's default, which
-- is what made the first design for this feature look impossible.
--
-- The parser lives here rather than in the client hook so run_lua can exercise
-- it in a loaded world, without reaching the main menu.

local function trim(text)
    return (string.gsub(text or "", "^%s*(.-)%s*$", "%1"))
end

--- Parse "x,y" into a spawn point, or nil plus a short reason.
--- Accepts a comma, a semicolon, an x or plain whitespace between the two
--- numbers, because a coordinate copied off the map site arrives in all of
--- those shapes. The x matters most: map.projectzomboid.com puts coordinates
--- in its own URL as "?12462x8938", so that is the form someone pastes without
--- thinking about it, and rejecting it looks like the feature is broken.
--- posZ is forced to 0: every cabin in this mod is at ground level, and a
--- z value typed by hand is a way to spawn inside terrain.
function HFTH_SpawnRegion.parsePoint(text)
    text = trim(text)
    if text == "" then return nil, "empty" end

    local x, y = string.match(text, "^(%-?%d+)%s*[,;xX%s]%s*(%-?%d+)$")
    if not x then return nil, "format" end

    x, y = tonumber(x), tonumber(y)
    if x < 0 or y < 0 then return nil, "negative" end

    -- No bounds check beyond this. There is no metagrid at menu time to ask how
    -- big the world is, and MoreMapsB42 moves the edges anyway, so a made-up
    -- maximum would reject legitimate coordinates on exactly the installs this
    -- mod is built for. A wrong-but-plausible number lands somewhere empty and
    -- the player can see that; a rejected valid one just looks broken.
    return { posX = x, posY = y, posZ = 0 }
end

--- Point every profession key at one list of spawn points.
local function pointEveryProfessionAt(points, list)
    for _, key in ipairs(professionKeys()) do
        points[key] = list
    end
end

--- Send the region to a single custom point, or back to the cabin list.
---
--- Called on every pass rather than only when a point is set. The region table
--- is long-lived and the screen can be backed out of and re-entered, so a
--- coordinate typed once and then cleared would otherwise stay live in the
--- frozen table and quietly override the list on a later character. That is
--- the failure the pre-flight review described as "the kind of bug that shows
--- up once, months later, and looks like the mod is haunted".
function HFTH_SpawnRegion.setCustomPoint(region, point)
    if not region or not region.points then return false end
    pointEveryProfessionAt(region.points, point and { point } or CABINS)
    return true
end

--- True when the region is currently pointed at a single custom spot.
function HFTH_SpawnRegion.hasCustomPoint(region)
    local points = region and region.points and region.points.unemployed
    return points ~= nil and #points == 1 and points ~= CABINS
end

-- --------------------------------------------------------------------------

--- True when `regions` already holds an entry under this name.
local function hasRegion(regions, name)
    for _, region in ipairs(regions) do
        if region.name == name then return true end
    end
    return false
end

local function onSpawnRegionsLoaded(regions)
    if not regions then return end

    -- MapSpawnSelect calls getSpawnRegions() several times while the screen is
    -- open and each call fires this event, so refuse to add a second copy. The
    -- guard skips the one region rather than returning out of the handler: it
    -- behaves identically while this file adds a single entry, and does not
    -- quietly swallow a second one added alongside it later.
    if not hasRegion(regions, REGION_NAME) then
        table.insert(regions, { name = REGION_NAME, points = buildPoints() })
    end
end

Events.OnSpawnRegionsLoaded.Add(onSpawnRegionsLoaded)
