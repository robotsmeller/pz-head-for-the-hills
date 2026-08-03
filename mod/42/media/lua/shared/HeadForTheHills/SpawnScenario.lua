-- Head for the Hills! - start scenario spawn logic
--
-- Applies the sandbox settings when a new character is created: starting
-- vehicle, starting equipment, a well and generator on the property if the
-- cabin lacks them, the zombie-free buffer, and the starting season.
--
-- MULTIPLAYER: this file guards on `isClient()` and lives in shared/, the same
-- shape vanilla uses for server/Map/MapObjects/MOGenerator.lua and
-- shared/Items/SpawnItems.lua. The singleplayer host and a dedicated server run
-- it; MP clients return immediately so world objects are created once, by the
-- authority, rather than once per connected player. Spawned generators call
-- transmitCompleteItemToClients() so remote clients see them.

if isClient() then return end

local FALLBACK_VEHICLE = "Base.PickUpTruck"
local GENERATOR_ITEM = "Base.Generator"

-- Search limits, in tiles, from the player's spawn square.
local VEHICLE_SEARCH_RADIUS = 14
local OBJECT_SEARCH_RADIUS = 8
local EXISTING_OBJECT_SCAN_RADIUS = 12

-- "Starting Season" enum -> vanilla StartMonth. Order must match the
-- option1..option4 keys in Sandbox_EN.txt: Spring, Summer, Fall, Winter.
local SEASON_START_MONTH = { 4, 7, 10, 1 }

local function options()
    return SandboxVars and SandboxVars.HeadForTheHills or nil
end

--- Walk squares outward from a centre in rings so the nearest match wins.
local function findSquare(centre, maxRadius, accept)
    if not centre then return nil end
    local cx, cy, cz = centre:getX(), centre:getY(), centre:getZ()
    for radius = 1, maxRadius do
        for dx = -radius, radius do
            for dy = -radius, radius do
                -- Ring edge only; interior squares were covered by smaller radii.
                if math.abs(dx) == radius or math.abs(dy) == radius then
                    local square = getSquare(cx + dx, cy + dy, cz)
                    if square and accept(square) then
                        return square
                    end
                end
            end
        end
    end
    return nil
end

--- Outdoors, not part of a building's footprint, and clear enough to place on.
--- getBuilding() is what keeps wells and generators off the cabin's interior
--- tiles; isOutside() alone would still allow a porch or enclosed shed.
local function isOpenGround(square)
    return square:isOutside()
        and square:getBuilding() == nil
        and square:isFree(false)
end

--- True if any square within radius already holds an object matching predicate.
local function objectExistsNearby(centre, radius, matches)
    if not centre then return false end
    local cx, cy, cz = centre:getX(), centre:getY(), centre:getZ()
    for dx = -radius, radius do
        for dy = -radius, radius do
            local square = getSquare(cx + dx, cy + dy, cz)
            if square then
                local objects = square:getObjects()
                for i = 0, objects:size() - 1 do
                    if matches(objects:get(i)) then
                        return true
                    end
                end
            end
        end
    end
    return false
end

-- ------------------------------------------------------------------ season ---

local function applySeason(opts)
    local month = SEASON_START_MONTH[opts.Season]
    if month then
        SandboxVars.StartMonth = month
    end
end

-- --------------------------------------------------------------- equipment ---

local function giveStartingEquipment(playerObj, opts)
    if not opts.SpawnStartingEquipment then return end
    local list = opts.StartingEquipmentList
    if not list or list == "" then return end

    local inventory = playerObj:getInventory()
    for fullName in string.gmatch(list, "([^;]+)") do
        -- A chosen item can vanish if the mod that supplied it was removed
        -- between world creation and this spawn, so never let one bad entry
        -- abort the rest of the loadout.
        local ok = pcall(function() inventory:AddItem(fullName) end)
        if not ok then
            print("[HeadForTheHills] could not add starting item: " .. tostring(fullName))
        end
    end
end

-- ----------------------------------------------------------------- vehicle ---

local function applyVehicleCondition(vehicle, percent)
    if not percent or percent >= 100 then return end
    for index = 1, vehicle:getPartCount() do
        local part = vehicle:getPartByIndex(index - 1)
        if part then
            pcall(function() part:setCondition(percent) end)
        end
    end
end

local function applyVehicleFuel(vehicle, percent)
    local tank = vehicle:getPartById("GasTank")
    if not tank then return end
    local capacity = tank:getContainerCapacity()
    if not capacity or capacity <= 0 then return end
    tank:setContainerContentAmount(capacity * (percent or 0) / 100)
end

local function spawnStartingVehicle(playerObj, opts)
    if not opts.SpawnVehicle then return end

    local square = findSquare(playerObj:getCurrentSquare(), VEHICLE_SEARCH_RADIUS, isOpenGround)
    if not square then
        print("[HeadForTheHills] no open ground found for the starting vehicle")
        return
    end

    local script = opts.StartingVehicle
    if not script or script == "" then script = FALLBACK_VEHICLE end

    local x, y, z = square:getX(), square:getY(), square:getZ()
    local ok, vehicle = pcall(addVehicle, script, x, y, z)
    if not ok or not vehicle then
        -- The saved choice can name a vehicle from a mod that is no longer
        -- installed; fall back rather than leaving the player stranded.
        print("[HeadForTheHills] could not spawn '" .. tostring(script) ..
              "', falling back to " .. FALLBACK_VEHICLE)
        ok, vehicle = pcall(addVehicle, FALLBACK_VEHICLE, x, y, z)
        if not ok or not vehicle then return end
    end

    vehicle:repair()
    applyVehicleCondition(vehicle, opts.VehicleCondition)
    applyVehicleFuel(vehicle, opts.VehicleFuel)

    local key = vehicle:createVehicleKey()
    if key then
        playerObj:getInventory():AddItem(key)
    end
end

-- -------------------------------------------------------- well / generator ---

local function hasGeneratorNearby(centre)
    return objectExistsNearby(centre, EXISTING_OBJECT_SCAN_RADIUS, function(object)
        return instanceof(object, "IsoGenerator")
    end)
end

--- Best-effort detection of an existing well.
--- Wells are B42 entities with a FluidContainer component and no dedicated Lua
--- class to test with instanceof, so this matches on the sprite name. That is
--- weaker than the generator check and is the most likely thing to need
--- adjusting once the real cabin tiles are inspected in-game.
local function hasWellNearby(centre)
    return objectExistsNearby(centre, EXISTING_OBJECT_SCAN_RADIUS, function(object)
        local sprite = object:getSprite()
        local name = sprite and sprite:getName()
        return name ~= nil and string.find(string.lower(name), "well", 1, true) ~= nil
    end)
end

local function spawnGenerator(playerObj, opts)
    if not opts.SpawnGenerator then return end

    local centre = playerObj:getCurrentSquare()
    if hasGeneratorNearby(centre) then return end

    -- Deliberately starts the ring search at radius 1 and requires open ground,
    -- so the generator lands beside the cabin and never inside it.
    local square = findSquare(centre, OBJECT_SEARCH_RADIUS, isOpenGround)
    if not square then
        print("[HeadForTheHills] no open ground found for the generator")
        return
    end

    local item = instanceItem(GENERATOR_ITEM)
    if not item then return end

    local running = opts.GeneratorFueledAndRunning and true or false
    item:setCondition(100)
    item:getModData().fuel = running and 100 or 0

    local generator = IsoGenerator.new(item, getWorld():getCell(), square)
    if not generator then return end

    if running then
        -- setActivated is gated on connected + fuel + condition, so connect
        -- first; this is the same state the plug-in timed action produces.
        generator:setConnected(true)
        generator:setActivated(true)
    end

    pcall(function() generator:transmitCompleteItemToClients() end)
end

local function spawnWell(playerObj, opts)
    if not opts.SpawnWell then return end

    local centre = playerObj:getCurrentSquare()
    if hasWellNearby(centre) then return end

    local square = findSquare(centre, OBJECT_SEARCH_RADIUS, isOpenGround)
    if not square then
        print("[HeadForTheHills] no open ground found for the well")
        return
    end

    -- Wells are entities rather than plain IsoObjects in B42; the exact
    -- construction call is unverified, so this is intentionally guarded and
    -- reports failure instead of erroring the whole spawn sequence.
    local ok = pcall(function()
        square:AddTileObject(IsoObject.new(square, "location_water_well_01_0", "location_water_well_01_0"))
    end)
    if not ok then
        print("[HeadForTheHills] well placement failed; sprite/entity name needs verifying in-game")
    end
end

-- ------------------------------------------------------------ zombie buffer ---

local function clearZombies(playerObj, opts)
    local radius = opts.ZombieFreeRadius
    if not radius or radius <= 0 then return end

    -- Vanilla's own spawn-area removal is a coarse 4-value enum with no radius.
    -- Switching it to "anywhere" hands this mod sole control instead of leaving
    -- two systems clearing the same area to different rules.
    if SandboxVars.ZombieLore then
        SandboxVars.ZombieLore.PlayerSpawnZombieRemoval = 4
    end

    local objects = getCell():getObjectListForLua()
    for i = objects:size(), 1, -1 do
        local object = objects:get(i - 1)
        if instanceof(object, "IsoZombie") and playerObj:DistTo(object) < radius then
            object:removeFromWorld()
            object:removeFromSquare()
        end
    end
end

-- ------------------------------------------------------------------- entry ---

local function onNewGame(playerObj, square)
    local opts = options()
    if not opts or not playerObj then return end

    applySeason(opts)
    giveStartingEquipment(playerObj, opts)
    spawnStartingVehicle(playerObj, opts)
    spawnWell(playerObj, opts)
    spawnGenerator(playerObj, opts)
    clearZombies(playerObj, opts)
end

Events.OnNewGame.Add(onNewGame)
