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

-- The sprite B42 declares for the Base.Well entity, from
-- media/scripts/generated/entities/appliances/workstations/entity_well.txt
-- (component SpriteConfig -> face S -> row). Fountains reuse it, which is fine:
-- both count as an existing water source for our purposes. Add to this list if a
-- map pack ships a well on a different sprite.
local WELL_SPRITES = { ["camping_01_16"] = true }
local WELL_SPRITE = "camping_01_16"

-- Search limits, in tiles, from the player's spawn square. The player starts
-- inside the cabin, so every placement has to walk out of the building first.
-- The minimums exist because searching from radius 1 returns whatever square
-- happens to touch the outside wall, which parks the car half inside the porch
-- and stands the well in a doorway.
local VEHICLE_MIN_RADIUS = 6
local VEHICLE_SEARCH_RADIUS = 16
local OBJECT_MIN_RADIUS = 2
local OBJECT_SEARCH_RADIUS = 10
local EXISTING_OBJECT_SCAN_RADIUS = 12

-- How much open ground each placement needs around its own square. A vehicle
-- body spans several tiles, so one free square is not enough to judge by.
-- Measured the hard way: spawning a car two tiles from the player put it
-- through the porch, and it came back as a chunk-orphaned ghost that rendered
-- as a floating shadow and did not survive a reload. Hence 5x5 preferred, 3x3
-- tolerated, and nothing at all rather than another wreck.
local VEHICLE_CLEARANCE = 2
local VEHICLE_FALLBACK_CLEARANCE = 1

-- "Starting Season" enum -> vanilla StartMonth. Order must match the
-- option1..option4 keys in Sandbox_EN.txt: Spring, Summer, Fall, Winter.
local SEASON_START_MONTH = { 4, 7, 10, 1 }

local function options()
    return SandboxVars and SandboxVars.HeadForTheHills or nil
end

--- Walk squares outward from a centre in rings so the nearest match wins.
--- Starts at minRadius rather than 1, because the nearest legal square is
--- usually the worst one: hard against the wall the player just came through.
local function findSquare(centre, minRadius, maxRadius, accept)
    if not centre then return nil end
    local cx, cy, cz = centre:getX(), centre:getY(), centre:getZ()
    for radius = minRadius, maxRadius do
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

--- True if the square is a doorway or sits directly beside one. Sealing the
--- cabin door with a well is worse than not placing the well at all, so this is
--- a hard reject rather than a preference.
local function blocksDoorway(square)
    local x, y, z = square:getX(), square:getY(), square:getZ()
    for dx = -1, 1 do
        for dy = -1, 1 do
            local neighbour = getSquare(x + dx, y + dy, z)
            if neighbour then
                local objects = neighbour:getObjects()
                for i = 0, objects:size() - 1 do
                    local object = objects:get(i)
                    if instanceof(object, "IsoDoor") then return true end
                    -- Player-built and some map doors are thumpables, which are
                    -- only doors at runtime, so ask rather than assume.
                    local isDoor = false
                    pcall(function() isDoor = object:isDoor() end)
                    if isDoor then return true end
                end
            end
        end
    end
    return false
end

--- Every square within margin tiles is open ground.
local function hasClearance(square, margin)
    if margin <= 0 then return true end
    local x, y, z = square:getX(), square:getY(), square:getZ()
    for dx = -margin, margin do
        for dy = -margin, margin do
            local neighbour = getSquare(x + dx, y + dy, z)
            if not neighbour or not isOpenGround(neighbour) then return false end
        end
    end
    return true
end

local function isObjectSpot(square)
    return isOpenGround(square) and not blocksDoorway(square)
end

local function isVehicleSpot(square)
    return isOpenGround(square)
        and hasClearance(square, VEHICLE_CLEARANCE)
        and not blocksDoorway(square)
end

local function isTightVehicleSpot(square)
    return isOpenGround(square)
        and hasClearance(square, VEHICLE_FALLBACK_CLEARANCE)
        and not blocksDoorway(square)
end

--- The first object within radius matching predicate, or nil. Returns the
--- object rather than a boolean so callers can act on what they found; the
--- cabin's own generator is worth starting, not just counting.
local function findObjectNearby(centre, radius, matches)
    if not centre then return nil end
    local cx, cy, cz = centre:getX(), centre:getY(), centre:getZ()
    for dx = -radius, radius do
        for dy = -radius, radius do
            local square = getSquare(cx + dx, cy + dy, cz)
            if square then
                local objects = square:getObjects()
                for i = 0, objects:size() - 1 do
                    local object = objects:get(i)
                    if matches(object) then
                        return object
                    end
                end
            end
        end
    end
    return nil
end

-- ------------------------------------------------------------------ season ---

local function applySeason(opts)
    local month = SEASON_START_MONTH[opts.Season]
    if not month then return end

    -- StartMonth is consumed when the world is created, which has already
    -- happened by the time OnNewGame fires. Measured: writing it here set the
    -- var to January and left the clock sitting in July. So write it anyway,
    -- for anything that reads it later, then move the clock for real.
    -- GameTime months are zero-based, StartMonth is one-based, hence the -1.
    SandboxVars.StartMonth = month
    pcall(function() getGameTime():setMonth(month - 1) end)
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

    local centre = playerObj:getCurrentSquare()
    -- Prefer real elbow room. Fall back once to a tighter spot, then give up
    -- entirely: a car spawned into geometry does not just look wrong, it comes
    -- back chunk-orphaned and vanishes on reload, which is worse for the player
    -- than starting on foot.
    local square = findSquare(centre, VEHICLE_MIN_RADIUS, VEHICLE_SEARCH_RADIUS, isVehicleSpot)
    if not square then
        square = findSquare(centre, VEHICLE_MIN_RADIUS, VEHICLE_SEARCH_RADIUS, isTightVehicleSpot)
        if square then
            print("[HeadForTheHills] no roomy parking spot; using a tight one at "
                  .. square:getX() .. "," .. square:getY())
        end
    end
    if not square then
        print("[HeadForTheHills] no safe ground for the starting vehicle; skipping it")
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

local function findGeneratorNearby(centre)
    return findObjectNearby(centre, EXISTING_OBJECT_SCAN_RADIUS, function(object)
        return instanceof(object, "IsoGenerator")
    end)
end

--- Fill and start a generator.
--- Fuel is capped at getMaxFuel(), which measured 10 on B42.20, so passing 100
--- silently clamps *down* to the cap. Ask for the cap instead. setActivated is
--- gated on having fuel, so fuel has to go in first.
local function fuelAndStart(generator)
    pcall(function() generator:setFuel(generator:getMaxFuel()) end)
    generator:setConnected(true)
    generator:setActivated(true)
end

--- Detect an existing well or other standing water source.
--- Wells are B42 entities with no dedicated Lua class to test with instanceof,
--- so this checks two things: the exact sprite the Base.Well entity declares,
--- and whether the object carries a FluidContainer at all. The component test is
--- what catches modded wells and pumps, which are free to use their own sprite.
local function isWaterSource(object)
    local sprite = object:getSprite()
    local name = sprite and sprite:getName()
    if name and WELL_SPRITES[name] then return true end

    -- Not every IsoObject subclass exposes getFluidContainer, so probe it safely
    -- rather than assuming the method is present on whatever the map placed.
    local ok, container = pcall(function() return object:getFluidContainer() end)
    return ok and container ~= nil
end

local function hasWellNearby(centre)
    return findObjectNearby(centre, EXISTING_OBJECT_SCAN_RADIUS, isWaterSource) ~= nil
end

local function spawnGenerator(playerObj, opts)
    if not opts.SpawnGenerator then return end

    local centre = playerObj:getCurrentSquare()
    local running = opts.GeneratorFueledAndRunning and true or false

    -- The cabin may already have come with one. Vanilla map generators are
    -- created at condition 100 with no fuel (see MOGenerator.lua), so leaving
    -- it alone hands the player a dead generator while the option they ticked
    -- promised a running one. Start theirs rather than adding a second.
    local existing = findGeneratorNearby(centre)
    if existing then
        if running then fuelAndStart(existing) end
        return
    end

    -- Open ground only, so the generator lands beside the cabin and never
    -- inside it, and clear of doorways so it cannot seal the player in.
    local square = findSquare(centre, OBJECT_MIN_RADIUS, OBJECT_SEARCH_RADIUS, isObjectSpot)
    if not square then
        print("[HeadForTheHills] no open ground found for the generator")
        return
    end

    local item = instanceItem(GENERATOR_ITEM)
    if not item then return end

    -- Fuel goes on afterwards via fuelAndStart, which respects getMaxFuel().
    -- The constructor does carry modData fuel across, but it does not clamp it,
    -- so seeding 100 here leaves the generator holding ten times its own cap.
    item:setCondition(100)
    item:getModData().fuel = 0

    local generator = IsoGenerator.new(item, getWorld():getCell(), square)
    if not generator then return end

    if running then fuelAndStart(generator) end

    pcall(function() generator:transmitCompleteItemToClients() end)
end

local function spawnWell(playerObj, opts)
    if not opts.SpawnWell then return end

    local centre = playerObj:getCurrentSquare()
    if hasWellNearby(centre) then return end

    local square = findSquare(centre, OBJECT_MIN_RADIUS, OBJECT_SEARCH_RADIUS, isObjectSpot)
    if not square then
        print("[HeadForTheHills] no open ground found for the well")
        return
    end

    -- Build the real Base.Well entity rather than a look-alike prop. This is the
    -- shape vanilla uses in server/Map/MapObjects/MORainCollectorBarrel.lua: make
    -- the carrier object, look the entity script up from its sprite, then let
    -- GameEntityFactory attach the script's own components. Going through the
    -- script is what gives us vanilla's declared FluidContainer (capacity 10000,
    -- fills with clean water, 20-100% initial) instead of numbers we invented,
    -- and it keeps working if those values are ever retuned.
    local ok, err = pcall(function()
        local info = SpriteConfigManager.getObjectInfoFromSprite(WELL_SPRITE)
        local script = info and info:getScript() and info:getScript():getParent()
        if not script then
            error("no entity script for sprite " .. WELL_SPRITE, 0)
        end

        local well = IsoThumpable.new(getWorld():getCell(), square, WELL_SPRITE, false)
        well:setName("Well")
        well:setCanPassThrough(false)
        well:setBlockAllTheSquare(true)
        well:setCanBarricade(false)
        well:setIsContainer(false)
        well:setIsDoor(false)
        well:setIsDoorFrame(false)
        well:setIsHoppable(false)
        -- A stone well is not a player build, so it should not offer dismantling.
        well:setIsDismantable(false)

        GameEntityFactory.CreateIsoObjectEntity(well, script, true)
        square:AddSpecialObject(well)
        well:transmitCompleteItemToClients()
    end)

    if not ok then
        -- Guarded because the script lookup is the one step not yet exercised
        -- outside vanilla's own map-object handlers. The message names the
        -- failing step so a live run tells us which half needs revisiting.
        print("[HeadForTheHills] well placement failed: " .. tostring(err))
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
