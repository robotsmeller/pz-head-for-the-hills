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
local OBJECT_SEARCH_RADIUS = 12
local EXISTING_OBJECT_SCAN_RADIUS = 12

-- How far from the nearest building wall a placement has to sit. "Not inside
-- the footprint" turned out not to mean "clear of the building": the first
-- live run put the well and the generator on the closest legal square, which
-- was hard against the wall at the foot of the porch steps. Measured in tiles
-- from the square in every direction, so 3 leaves a walkable gap.
local BUILDING_CLEARANCE = 3
local VEHICLE_BUILDING_CLEARANCE = 2

-- Keep the well and the generator from landing on top of each other. They are
-- placed by the same search from the same centre, so without this the second
-- one takes the square next to the first.
local GENERATOR_WELL_GAP = 1

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

local function startsWith(text, prefix)
    return string.sub(text, 1, string.len(prefix)) == prefix
end

--- Standing water, including the river and pond squares that carry the tainted
--- flag rather than the plain one. Vanilla reads this off the floor sprite's
--- own properties in ISWoodenStairs.lua and buildRecipeCode.lua, so this does
--- the same rather than matching sprite names by hand.
local function isWaterSquare(square)
    local floor = square:getFloor()
    if not floor then return false end
    local sprite = floor:getSprite()
    local properties = sprite and sprite:getProperties()
    if properties and properties:has(IsoFlagType.water) then return true end
    local squareProperties = square:getProperties()
    return squareProperties ~= nil and squareProperties:has(IsoFlagType.taintedWater)
end

--- Bare dirt or grass, rather than pavement, gravel, sand or clay.
--- Vanilla classifies ground by floor sprite name in
--- server/BuildingObjects/ISShovelGroundCursor.lua (GetDirtGravelSand): the two
--- natural prefixes below are its "dirt" case, and NOT_SOFT_GROUND is the exact
--- set it peels off first as gravel, sand and clay. Grass needs no separate
--- test because PZ draws it as the natural blend itself, not as an overlay.
local SOFT_GROUND_PREFIXES = { "blends_natural_01_", "floors_exterior_natural" }
local NOT_SOFT_GROUND = {
    -- gravel
    ["floors_exterior_natural_01_13"] = true, ["blends_street_01_55"] = true,
    ["blends_street_01_54"] = true, ["blends_street_01_53"] = true,
    ["blends_street_01_48"] = true,
    -- sand
    ["blends_natural_01_0"] = true, ["blends_natural_01_5"] = true,
    ["blends_natural_01_6"] = true, ["blends_natural_01_7"] = true,
    ["floors_exterior_natural_01_24"] = true,
    -- clay
    ["blends_natural_01_96"] = true, ["blends_natural_01_101"] = true,
    ["blends_natural_01_102"] = true, ["blends_natural_01_103"] = true,
}

local function isSoftGround(square)
    local floor = square:getFloor()
    if not floor then return false end
    local sprite = floor:getSprite()
    local name = sprite and sprite:getName()
    if not name or NOT_SOFT_GROUND[name] then return false end
    for _, prefix in ipairs(SOFT_GROUND_PREFIXES) do
        if startsWith(name, prefix) then return true end
    end
    return false
end

--- No building within margin tiles in any direction. getBuilding() on the
--- square alone only answers "am I standing in one", which is how the first
--- live run ended up with the well and the generator flat against the wall.
local function isClearOfBuildings(square, margin)
    local x, y, z = square:getX(), square:getY(), square:getZ()
    for dx = -margin, margin do
        for dy = -margin, margin do
            local neighbour = getSquare(x + dx, y + dy, z)
            if neighbour and neighbour:getBuilding() ~= nil then return false end
        end
    end
    return true
end

--- Outdoors, not part of a building's footprint, dry, and clear enough to place
--- on. getBuilding() is what keeps wells and generators off the cabin's interior
--- tiles; isOutside() alone would still allow a porch or enclosed shed. The
--- water test lives here so it covers the vehicle's whole clearance ring too,
--- not just the square its wheels land on.
local function isOpenGround(square)
    return square:isOutside()
        and square:getBuilding() == nil
        and square:isFree(false)
        and not isWaterSquare(square)
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
                    -- only doors at runtime, so ask rather than assume. Test for
                    -- the method before calling it: most IsoObjects do not have
                    -- one, and calling it anyway throws. pcall catches that, but
                    -- PZ still dumps a full Java stack trace to console.txt for
                    -- every throw - measured at 234 of them in one world start.
                    if object.isDoor and object:isDoor() then return true end
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

-- Where the well went this spawn, so the generator does not end up leaning on
-- it. Both are placed by the same search from the same centre, so without this
-- the second one takes the square next to the first. Cleared per spawn rather
-- than left over from a previous character.
local wellSquare = nil

--- Somewhere a well or a generator can stand and still look deliberate: bare
--- dirt or grass, out in the open, a walkable gap from the building, and not
--- sealing a door.
local function isObjectSpot(square)
    return isOpenGround(square)
        and isSoftGround(square)
        and isClearOfBuildings(square, BUILDING_CLEARANCE)
        and not blocksDoorway(square)
end

--- The same, minus the ground-type and full building-clearance rules. A cabin
--- ringed by gravel or hard against a treeline would otherwise get nothing at
--- all, and a well on the wrong ground beats no water source.
local function isFallbackObjectSpot(square)
    return isOpenGround(square)
        and isClearOfBuildings(square, 1)
        and not blocksDoorway(square)
end

local function isAwayFromWell(square)
    if not wellSquare then return true end
    local gap = math.max(math.abs(square:getX() - wellSquare.x),
                         math.abs(square:getY() - wellSquare.y))
    return gap > GENERATOR_WELL_GAP
end

local function isGeneratorSpot(square)
    return isAwayFromWell(square) and isObjectSpot(square)
end

local function isFallbackGeneratorSpot(square)
    return isAwayFromWell(square) and isFallbackObjectSpot(square)
end

local function isVehicleSpot(square)
    return isOpenGround(square)
        and isClearOfBuildings(square, VEHICLE_BUILDING_CLEARANCE)
        and hasClearance(square, VEHICLE_CLEARANCE)
        and not blocksDoorway(square)
end

local function isTightVehicleSpot(square)
    return isOpenGround(square)
        and isClearOfBuildings(square, VEHICLE_BUILDING_CLEARANCE)
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

--- Is the player already carrying one of these, anywhere on them?
--- Recursive, so an item inside a starting bag counts: the question is whether
--- they already have one, not whether it is in the main inventory.
--- containsTypeRecurse compares the *full* type, verified live on B42.20 - a
--- carried Base.IDcard answers false to "NotAMod.IDcard" - so the equipment
--- list's full names can go straight in without splitting off the module.
--- Field-tested rather than pcall'd, because a missing method on B42 throws and
--- dumps a Java stack trace even when the pcall catches it.
local function alreadyCarrying(inventory, fullName)
    if not inventory.containsTypeRecurse then return false end
    return inventory:containsTypeRecurse(fullName) == true
end

local function giveStartingEquipment(playerObj, opts)
    if not opts.SpawnStartingEquipment then return end
    local list = opts.StartingEquipmentList
    if not list or list == "" then return end

    local inventory = playerObj:getInventory()
    local issued = {}
    for fullName in string.gmatch(list, "([^;]+)") do
        -- One entry, one item. The picker keys its selection by full name so it
        -- cannot emit a duplicate, but the option is a plain string that a
        -- server admin or a hand-edited save can repeat, and handing the player
        -- the same thing twice reads as a bug either way.
        if not issued[fullName] then
            issued[fullName] = true
            -- Something else may have granted it already. Vanilla's own
            -- OnNewGame handler gives every character an ID card
            -- unconditionally (shared/Items/SpawnItems.lua), plus a badge to a
            -- ranger, police officer or firefighter and a pager to a doctor,
            -- and vanilla Lua loads before mod Lua so it always runs first.
            -- Another mod's loadout collides the same way. Skipping is general
            -- rather than ID-card specific for exactly that reason.
            if alreadyCarrying(inventory, fullName) then
                print("[HeadForTheHills] already carrying " .. tostring(fullName)
                      .. "; not issuing a second one")
            else
                -- A chosen item can vanish if the mod that supplied it was
                -- removed between world creation and this spawn, so never let
                -- one bad entry abort the rest of the loadout.
                local ok = pcall(function() inventory:AddItem(fullName) end)
                if not ok then
                    print("[HeadForTheHills] could not add starting item: " .. tostring(fullName))
                end
            end
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
    -- Vanilla's ISActivateGenerator:complete() syncs after flipping the switch.
    -- transmitCompleteItemToClients, which the callers below use, is the shape
    -- MOGenerator.lua uses for a generator it just *created*; sync is the one
    -- for a generator whose state changed.
    pcall(function() generator:sync() end)
end

-- Starting a generator from inside OnNewGame does not stick. Measured live
-- (session 4): a generator created and started there came back fuel 0,
-- disconnected and off, with no error raised - and at condition 100 on sprite
-- appliances_misc_01_0, which is exactly what MOGenerator.lua's
-- ReplaceExistingObject builds. That file registers handlers on that very
-- sprite, so a map-object pass over the chunk after our write is the likely
-- culprit. The identical call sequence works a moment later, so rather than
-- race whatever runs during world init, re-apply once the world is running.
-- Ticks do not run during IsoWorld.init, so the first one is already past it.
local REASSERT_TICKS = 30
local pendingStart = nil
local reassertGenerator

--- Re-find the generator we started and start it again if something undid it.
reassertGenerator = function()
    if not pendingStart then
        Events.OnTick.Remove(reassertGenerator)
        return
    end

    pendingStart.ticks = pendingStart.ticks - 1
    if pendingStart.ticks > 0 then return end

    local target = pendingStart
    pendingStart = nil
    Events.OnTick.Remove(reassertGenerator)

    local square = getSquare(target.x, target.y, target.z)
    if not square then
        print("[HeadForTheHills] generator square never loaded; cannot start it")
        return
    end

    -- Radius 1, not the wider scan: if the object was replaced it is on the
    -- same square, and a wider search could adopt an unrelated generator.
    local generator = findObjectNearby(square, 1, function(object)
        return instanceof(object, "IsoGenerator")
    end)
    if not generator then
        print("[HeadForTheHills] generator went missing before it could be started")
        return
    end

    if generator:isActivated() and generator:getFuel() > 0 then return end

    print("[HeadForTheHills] generator was not running after world init; starting it")
    fuelAndStart(generator)
    pcall(function() generator:transmitCompleteItemToClients() end)
end

local function startWhenSettled(generator)
    local square = generator:getSquare()
    if not square then return end
    if pendingStart then Events.OnTick.Remove(reassertGenerator) end
    pendingStart = {
        x = square:getX(), y = square:getY(), z = square:getZ(),
        ticks = REASSERT_TICKS,
    }
    Events.OnTick.Add(reassertGenerator)
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
        if running then
            fuelAndStart(existing)
            -- MP: clients already know this generator exists, but its fuel and
            -- running state just changed under them and nothing else will push
            -- that across. The freshly spawned path below transmits for the
            -- same reason.
            pcall(function() existing:transmitCompleteItemToClients() end)
            -- A map generator is built by the same world-init pass that eats
            -- our write, so this branch needs the re-check too.
            startWhenSettled(existing)
        end
        return
    end

    -- Bare ground a walkable gap from the building, clear of doorways so it
    -- cannot seal the player in, and not right up against the well.
    local square = findSquare(centre, OBJECT_MIN_RADIUS, OBJECT_SEARCH_RADIUS, isGeneratorSpot)
    if not square then
        square = findSquare(centre, OBJECT_MIN_RADIUS, OBJECT_SEARCH_RADIUS,
                            isFallbackGeneratorSpot)
        if square then
            print("[HeadForTheHills] no bare ground clear of the building for the "
                  .. "generator; using " .. square:getX() .. "," .. square:getY())
        end
    end
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

    if running then
        fuelAndStart(generator)
        startWhenSettled(generator)
    end

    pcall(function() generator:transmitCompleteItemToClients() end)
end

local function spawnWell(playerObj, opts)
    if not opts.SpawnWell then return end

    local centre = playerObj:getCurrentSquare()
    if hasWellNearby(centre) then return end

    local square = findSquare(centre, OBJECT_MIN_RADIUS, OBJECT_SEARCH_RADIUS, isObjectSpot)
    if not square then
        square = findSquare(centre, OBJECT_MIN_RADIUS, OBJECT_SEARCH_RADIUS,
                            isFallbackObjectSpot)
        if square then
            print("[HeadForTheHills] no bare ground clear of the building for the "
                  .. "well; using " .. square:getX() .. "," .. square:getY())
        end
    end
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

    if ok then
        -- Remembered so the generator, which searches the same rings from the
        -- same centre, does not take the square right beside it.
        wellSquare = { x = square:getX(), y = square:getY() }
    end

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

    -- Per-spawn state, cleared rather than inherited from a previous character
    -- in the same session.
    wellSquare = nil

    applySeason(opts)
    giveStartingEquipment(playerObj, opts)
    spawnStartingVehicle(playerObj, opts)
    spawnWell(playerObj, opts)
    spawnGenerator(playerObj, opts)
    clearZombies(playerObj, opts)
end

Events.OnNewGame.Add(onNewGame)
