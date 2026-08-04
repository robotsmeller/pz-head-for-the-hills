-- Head for the Hills! - start scenario spawn logic
--
-- Applies the sandbox settings when a new character is created: starting
-- vehicle, starting equipment, a well and generator on the property if the
-- cabin lacks them, and the starting season.
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
local VEHICLE_BUILDING_CLEARANCE = 2

-- The well belongs out in the yard, not against the house: a band measured
-- from the nearest building tile, near enough to be the cabin's well and far
-- enough that nobody drew water off their own back wall. When nothing in the
-- band qualifies the search widens *outward* only, never inward, because too
-- close is the failure this band exists to prevent.
local WELL_BUILDING_MIN = 6
local WELL_BUILDING_MAX = 10
local WELL_BUILDING_MAX_RELAXED = 16

-- And not on a shoreline. Standing water beside a well is both wrong to look
-- at and the thing a well exists to avoid needing. Four tiles is enough to
-- clear a bank without rejecting a cabin that merely sits near a pond.
local WELL_WATER_GAP = 4

-- The generator belongs against the house, which is the opposite rule. It is
-- measured the same way, so 1 means a square whose neighbour is building.
local GENERATOR_BUILDING_MAX = 1
local GENERATOR_BUILDING_MAX_RELAXED = 2

-- The ring searches measure from the player; the bands above measure from the
-- building. Those are the same number only for a player standing on the wall.
-- Cabin #6 is a 20x11 farmhouse, so someone spawning in the middle of it is
-- already ten tiles from the far side before the band starts counting, and a
-- 12-tile search would never reach a legal well square at all.
local WELL_SEARCH_RADIUS = 24
local GENERATOR_SEARCH_RADIUS = 16

-- How far out to collect building and water tiles before placing anything.
-- Wide enough that a candidate at the far edge of the well's search can still
-- see a building the full relaxed band beyond it, otherwise a square would read
-- as "no building near" purely because the scan stopped early - and that reads
-- as open country, which switches the whole rule over to measuring from the
-- player instead.
local CONTEXT_RADIUS = WELL_SEARCH_RADIUS + WELL_BUILDING_MAX_RELAXED

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

--- Where the buildings and the water are, collected once per spawn.
---
--- The well now has to know its distance to the nearest building tile, and
--- asking that per candidate means re-scanning a 21x21 box for each one: over a
--- full ring search that is several hundred thousand square reads during world
--- init. Scanning once and comparing coordinates afterwards is the same answer
--- for a fraction of the work, and the comparison is plain arithmetic.
local function scanContext(centre)
    local cx, cy, cz = centre:getX(), centre:getY(), centre:getZ()
    local ctx = { cx = cx, cy = cy, buildings = {}, waters = {} }
    for dx = -CONTEXT_RADIUS, CONTEXT_RADIUS do
        for dy = -CONTEXT_RADIUS, CONTEXT_RADIUS do
            local square = getSquare(cx + dx, cy + dy, cz)
            if square then
                if square:getBuilding() ~= nil then
                    ctx.buildings[#ctx.buildings + 1] = { x = cx + dx, y = cy + dy }
                end
                if isWaterSquare(square) then
                    ctx.waters[#ctx.waters + 1] = { x = cx + dx, y = cy + dy }
                end
            end
        end
    end
    return ctx
end

--- Chebyshev distance to the nearest tile in a list, or math.huge if empty.
--- Chebyshev rather than straight-line because every other clearance rule in
--- this file is a box scan, and mixing the two would make "3 tiles" mean two
--- different distances depending on which rule was asking.
local function nearestTile(list, x, y)
    local best = math.huge
    for i = 1, #list do
        local tile = list[i]
        local d = math.max(math.abs(tile.x - x), math.abs(tile.y - y))
        if d < best then best = d end
    end
    return best
end

--- How far this square is from home.
---
--- Normally the nearest building tile. When there is no building in range at
--- all, the spawn square itself: a custom start coordinate can drop someone in
--- open country with no cabin anywhere, and "6 to 10 tiles from a building"
--- would place nothing at all there. With no building, where you stand is
--- where you live.
local function homeDistance(ctx, square)
    if #ctx.buildings == 0 then
        return math.max(math.abs(square:getX() - ctx.cx),
                        math.abs(square:getY() - ctx.cy))
    end
    return nearestTile(ctx.buildings, square:getX(), square:getY())
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

-- The six sprite types a flight of stairs is built from: top, middle and bottom,
-- each facing north or west. Vanilla tests them exactly this way, as a square
-- level question (ISBuildUtil.lua:489) rather than by walking the object list,
-- and assembles the same six into one isStairs flag in ISBuildIsoEntity.lua:617.
-- Built once because IsoObjectType is a Java enum lookup, not a table read.
local STAIR_TYPES = nil
local function stairTypes()
    if STAIR_TYPES then return STAIR_TYPES end
    STAIR_TYPES = {}
    if not IsoObjectType then return STAIR_TYPES end
    for _, name in ipairs({ "stairsTW", "stairsTN", "stairsMW",
                            "stairsMN", "stairsBW", "stairsBN" }) do
        if IsoObjectType[name] then
            STAIR_TYPES[#STAIR_TYPES + 1] = IsoObjectType[name]
        end
    end
    return STAIR_TYPES
end

--- True if the square is a doorway or a stairway, or sits directly beside one.
--- Sealing the cabin door with a well is worse than not placing the well at
--- all, and a generator at the foot of the steps is the same mistake wearing a
--- different hat, so both are hard rejects rather than preferences.
local function blocksAccess(square)
    local x, y, z = square:getX(), square:getY(), square:getZ()
    local stairs = stairTypes()
    for dx = -1, 1 do
        for dy = -1, 1 do
            local neighbour = getSquare(x + dx, y + dy, z)
            if neighbour then
                if neighbour.has then
                    for i = 1, #stairs do
                        if neighbour:has(stairs[i]) then return true end
                    end
                end
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

--- Somewhere a well belongs: out in the yard on bare dirt or grass, a real walk
--- from the house rather than against it, nowhere near standing water, and not
--- sealing a door or a stairway.
---
--- maxFromBuilding is the only part that relaxes. When nothing in the band
--- qualifies the caller widens it outward, never inward, because a well against
--- the wall is the thing the band exists to prevent and a well further out is
--- merely a longer walk.
local function isWellSpot(ctx, maxFromBuilding)
    return function(square)
        if not isOpenGround(square) then return false end
        if not isSoftGround(square) then return false end
        if blocksAccess(square) then return false end

        local home = homeDistance(ctx, square)
        if home < WELL_BUILDING_MIN or home > maxFromBuilding then return false end

        return nearestTile(ctx.waters, square:getX(), square:getY()) > WELL_WATER_GAP
    end
end

--- Somewhere a generator belongs: hard against the house, which is the exact
--- opposite of the well's rule and deliberate. A generator powers the building
--- it is wired to, so beside the wall is where one would actually stand.
---
--- No ground-type test, unlike the well. A generator on a porch slab or on
--- gravel is fine, and often what the cabin already offers.
local function isGeneratorSpot(ctx, maxFromBuilding)
    return function(square)
        if not isOpenGround(square) then return false end
        if blocksAccess(square) then return false end
        return homeDistance(ctx, square) <= maxFromBuilding
    end
end

local function isVehicleSpot(square)
    return isOpenGround(square)
        and isClearOfBuildings(square, VEHICLE_BUILDING_CLEARANCE)
        and hasClearance(square, VEHICLE_CLEARANCE)
        and not blocksAccess(square)
end

local function isTightVehicleSpot(square)
    return isOpenGround(square)
        and isClearOfBuildings(square, VEHICLE_BUILDING_CLEARANCE)
        and hasClearance(square, VEHICLE_FALLBACK_CLEARANCE)
        and not blocksAccess(square)
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

local function spawnStartingVehicle(playerObj, opts, centre)
    if not opts.SpawnVehicle then return end

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

--- What the two generator options add up to.
--- Deliberately never includes running. A generator the player has not switched
--- on themselves is one they will not know the fuel state of, and the noise
--- pulls zombies from the first second of the game.
local function generatorState(opts)
    return {
        fuelled = opts.GeneratorFueled and true or false,
        connected = opts.GeneratorConnected and true or false,
    }
end

--- Put a generator into the state the options asked for, and no further.
---
--- Fuel is capped at getMaxFuel(), which measured 10 on B42.20, so passing 100
--- silently clamps *down* to the cap. Ask for the cap instead.
---
--- setActivated is never called. Connected means wired to the house, not
--- switched on, so a player who ticked both walks out to a generator ready to
--- start with one action and no cable to run.
local function applyGeneratorState(generator, state)
    if state.fuelled then
        pcall(function() generator:setFuel(generator:getMaxFuel()) end)
    end
    generator:setConnected(state.connected)
    -- Vanilla's ISActivateGenerator:complete() syncs after flipping the switch.
    -- transmitCompleteItemToClients, which the callers below use, is the shape
    -- MOGenerator.lua uses for a generator it just *created*; sync is the one
    -- for a generator whose state changed.
    pcall(function() generator:sync() end)
end

-- Setting a generator's state from inside OnNewGame does not stick. Measured
-- live (session 4): a generator created and started there came back fuel 0,
-- disconnected and off, with no error raised - and at condition 100 on sprite
-- appliances_misc_01_0, which is exactly what MOGenerator.lua's
-- ReplaceExistingObject builds. That file registers handlers on that very
-- sprite, so a map-object pass over the chunk after our write is the likely
-- culprit. The identical call sequence works a moment later, so rather than
-- race whatever runs during world init, re-apply once the world is running.
-- Ticks do not run during IsoWorld.init, so the first one is already past it.
local REASSERT_TICKS = 30
local pendingState = nil
local reassertGenerator

--- Re-find the generator and put its fuel and connection back if world init
--- ate them. Never touches the switch, so a generator that starts off stays off.
reassertGenerator = function()
    if not pendingState then
        Events.OnTick.Remove(reassertGenerator)
        return
    end

    pendingState.ticks = pendingState.ticks - 1
    if pendingState.ticks > 0 then return end

    local target = pendingState
    pendingState = nil
    Events.OnTick.Remove(reassertGenerator)

    local square = getSquare(target.x, target.y, target.z)
    if not square then
        print("[HeadForTheHills] generator square never loaded; cannot set it up")
        return
    end

    -- Radius 1, not the wider scan: if the object was replaced it is on the
    -- same square, and a wider search could adopt an unrelated generator.
    local generator = findObjectNearby(square, 1, function(object)
        return instanceof(object, "IsoGenerator")
    end)
    if not generator then
        print("[HeadForTheHills] generator went missing before it could be set up")
        return
    end

    -- Only the parts that were asked for and are not already true. Reading the
    -- fuel back rather than assuming is the whole point of this pass.
    local fuelOk = not target.state.fuelled or generator:getFuel() > 0
    local connOk = generator:isConnected() == target.state.connected
    if fuelOk and connOk then return end

    print(string.format(
        "[HeadForTheHills] generator lost its setup during world init "
        .. "(fuel %d, connected %s); re-applying",
        generator:getFuel(), tostring(generator:isConnected())))
    applyGeneratorState(generator, target.state)
    pcall(function() generator:transmitCompleteItemToClients() end)
end

local function reapplyWhenSettled(generator, state)
    local square = generator:getSquare()
    if not square then return end
    if pendingState then Events.OnTick.Remove(reassertGenerator) end
    pendingState = {
        x = square:getX(), y = square:getY(), z = square:getZ(),
        ticks = REASSERT_TICKS, state = state,
    }
    Events.OnTick.Add(reassertGenerator)
end

-- What a fluid container has to hold to count as a well rather than a barrel.
--
-- Measured live at cabin #8 (session 10), which has both: a Fluid_Container_
-- PumpWell at capacity 20000, and two Rain Collector Barrels at 600, standing
-- empty. Vanilla's own Base.Well is declared at 10000. Any threshold between
-- those separates them, and 2000 sits clear of both, so a modded well with a
-- more modest tank still counts while no rain barrel ever will.
--
-- This matters because either barrel alone used to suppress the well entirely.
-- An empty 600-litre barrel that only fills when it rains is not the water
-- supply the option promises, and "Spawn Well If Missing" says well, not water.
local WELL_MIN_CAPACITY = 2000

--- Detect an existing well, so the mod leaves it alone rather than digging a
--- second one beside it.
---
--- Wells are B42 entities with no dedicated Lua class to test with instanceof,
--- so this checks two things: the exact sprite the Base.Well entity declares,
--- and whether the object carries a FluidContainer big enough to be a well.
--- The component test is what catches modded wells and pumps, which are free to
--- use their own sprite - cabin #8's is on camping_01_64, which appears in no
--- vanilla script at all.
local function isWaterSource(object)
    local sprite = object:getSprite()
    local name = sprite and sprite:getName()
    if name and WELL_SPRITES[name] then return true end

    -- Not every IsoObject subclass exposes getFluidContainer, so probe it safely
    -- rather than assuming the method is present on whatever the map placed.
    local ok, container = pcall(function() return object:getFluidContainer() end)
    if not ok or container == nil then return false end

    -- Capacity is read the same guarded way: a container from a mod is not
    -- obliged to expose the getter, and treating an unreadable one as "not a
    -- well" only risks a second well, which is the cheaper mistake.
    local okCap, capacity = pcall(function() return container:getCapacity() end)
    return okCap and type(capacity) == "number" and capacity >= WELL_MIN_CAPACITY
end

local function findWellNearby(centre)
    return findObjectNearby(centre, EXISTING_OBJECT_SCAN_RADIUS, isWaterSource)
end

local function spawnGenerator(playerObj, opts, centre, ctx)
    if not opts.SpawnGenerator then return end

    local state = generatorState(opts)

    -- The cabin may already have come with one. Vanilla map generators are
    -- created at condition 100 with no fuel (see MOGenerator.lua), so leaving
    -- it alone hands the player a dead generator while the options they ticked
    -- promised a fuelled or wired one. Set theirs rather than adding a second.
    local existing = findGeneratorNearby(centre)
    if existing then
        local where = existing:getSquare()
        print(string.format(
            "[HeadForTheHills] cabin already has a generator at %s; setting it up "
            .. "rather than adding a second",
            where and (where:getX() .. "," .. where:getY()) or "an unreadable square"))
        if state.fuelled or state.connected then
            applyGeneratorState(existing, state)
            -- MP: clients already know this generator exists, but its fuel and
            -- connection just changed under them and nothing else will push
            -- that across. The freshly spawned path below transmits for the
            -- same reason.
            pcall(function() existing:transmitCompleteItemToClients() end)
            -- A map generator is built by the same world-init pass that eats
            -- our write, so this branch needs the re-check too.
            reapplyWhenSettled(existing, state)
        end
        return
    end

    -- Hard against the house, clear of doors and steps so it cannot pen the
    -- player in. Widens by a tile if every wall square is beside an opening.
    local square = findSquare(centre, 1, GENERATOR_SEARCH_RADIUS,
                              isGeneratorSpot(ctx, GENERATOR_BUILDING_MAX))
    if not square then
        square = findSquare(centre, 1, GENERATOR_SEARCH_RADIUS,
                            isGeneratorSpot(ctx, GENERATOR_BUILDING_MAX_RELAXED))
        if square then
            print("[HeadForTheHills] nothing against the wall was clear of doors "
                  .. "or steps for the generator; using "
                  .. square:getX() .. "," .. square:getY())
        end
    end
    if not square then
        print("[HeadForTheHills] no open ground found for the generator")
        return
    end

    local item = instanceItem(GENERATOR_ITEM)
    if not item then return end

    -- Fuel goes on afterwards via applyGeneratorState, which respects
    -- getMaxFuel(). The constructor does carry modData fuel across, but it does
    -- not clamp it, so seeding 100 here leaves it holding ten times its cap.
    item:setCondition(100)
    item:getModData().fuel = 0

    local generator = IsoGenerator.new(item, getWorld():getCell(), square)
    if not generator then return end

    if state.fuelled or state.connected then
        applyGeneratorState(generator, state)
        reapplyWhenSettled(generator, state)
    end

    pcall(function() generator:transmitCompleteItemToClients() end)
end

local function spawnWell(playerObj, opts, centre, ctx)
    if not opts.SpawnWell then return end

    -- Said out loud, because silence here is indistinguishable from silence
    -- after a successful dig, and that cost two live runs to work out: both
    -- landed on a cabin that already had a well, and nothing in the log or the
    -- world said whether the mod had skipped or placed. A check for "did the
    -- mod place X" is worthless unless it can tell it was asked to.
    local existing = findWellNearby(centre)
    if existing then
        local where = existing:getSquare()
        print(string.format(
            "[HeadForTheHills] cabin already has a well at %s; leaving it alone",
            where and (where:getX() .. "," .. where:getY()) or "an unreadable square"))
        return
    end

    -- Out in the yard, six to ten tiles off the house. If nothing in that band
    -- is dry open ground the band stretches outward to sixteen, and if that
    -- still finds nothing the cabin gets no well at all. A missing well is
    -- visible and honest; one built against the back wall is the thing this
    -- rule exists to prevent.
    local square = findSquare(centre, OBJECT_MIN_RADIUS, WELL_SEARCH_RADIUS,
                              isWellSpot(ctx, WELL_BUILDING_MAX))
    if not square then
        square = findSquare(centre, OBJECT_MIN_RADIUS, WELL_SEARCH_RADIUS,
                            isWellSpot(ctx, WELL_BUILDING_MAX_RELAXED))
        if square then
            print("[HeadForTheHills] nothing " .. WELL_BUILDING_MIN .. "-"
                  .. WELL_BUILDING_MAX .. " tiles out suited the well; using "
                  .. square:getX() .. "," .. square:getY())
        end
    end
    if not square then
        print("[HeadForTheHills] no ground clear of the house and the water "
              .. "was found for the well; none placed")
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
        print(string.format(
            "[HeadForTheHills] well dug at %d,%d, %d tiles from the house",
            square:getX(), square:getY(), homeDistance(ctx, square)))
    else
        -- Guarded because the script lookup is the one step not yet exercised
        -- outside vanilla's own map-object handlers. The message names the
        -- failing step so a live run tells us which half needs revisiting.
        print("[HeadForTheHills] well placement failed: " .. tostring(err))
    end
end

-- The mod used to clear its own zombie buffer here, on a ZombieFreeRadius
-- sandbox option. It is gone on purpose, and the reasoning is worth keeping so
-- nobody rebuilds it:
--
-- * The number that justified it was measured at a town coordinate, and this
--   mod starts people at remote cabins. It was solving for somewhere it never
--   sends anyone.
-- * The engine already thins zombies around a spawn, through the vanilla
--   ZombieLore.PlayerSpawnZombieRemoval setting, which is now left at whatever
--   the player chose rather than overridden.
-- * A cabin the survivor has been holed up in for weeks having a quiet treeline
--   is the fiction; vanilla's own removal covers the doorstep, and the twelve
--   cabins are remote enough that little else is nearby to begin with.
--
-- Session 10 measured the ceiling any such buffer could have had: 72 tiles, and
-- nothing at all at OnNewGame. See CLAUDE.md.

-- ------------------------------------------------------------------- entry ---

-- How far to look for dry land when a custom coordinate lands in water. Only
-- squares that have streamed in can answer, and an unstreamed one reads as nil
-- rather than as water, so searching wider than the loaded area buys nothing.
local WATER_RESCUE_RADIUS = 60

-- Ticks to wait before starting over, when the anchor could not be settled on
-- the first pass. Ticks do not run during IsoWorld.init, so the first one is
-- already past world creation.
local RESTART_TICKS = 30

--- Anywhere a person can stand that is not water. Deliberately looser than
--- isOpenGround: this is not choosing a good spot for a well, it is getting
--- someone out of a lake, and any floored square beats standing in one.
---
--- Only ever the last choice. On its own it picked the inside of a boathouse
--- standing out over the river (see anchorSquare): dry, floored, and not land.
local function isDryLand(square)
    return square:getFloor() ~= nil and not isWaterSquare(square)
end

--- Dry land a person would actually choose: floored, outdoors, and outside any
--- building's footprint. isOpenGround already carries the outdoors and
--- footprint tests that keep the well and the generator off cabin tiles, and
--- the same two are what keep a rescued player out of a wall. The floor test is
--- added because isOpenGround is happy with a square that has no floor at all.
local function isStandableGround(square)
    return square:getFloor() ~= nil and isOpenGround(square)
end

--- Actual terrain: dirt or grass, outdoors, outside any building's footprint.
--- This is the one that tells a riverbank from a jetty. isSoftGround is
--- vanilla's own dirt/grass classification by floor sprite, so decking,
--- floorboards and paving all fall out of it without naming any of them.
local function isRealGround(square)
    return isStandableGround(square) and isSoftGround(square)
end

local restartPending = nil
local restartSpawn

--- The square the whole start gets built around.
---
--- Everything downstream takes this as an argument instead of asking the player
--- where they are, because those are two different questions. A player's
--- coordinates update the instant teleportTo is called, but getCurrentSquare()
--- takes about a second to follow (measured session 6). A placement pass that
--- re-reads the player mid-rescue therefore builds around the lake we just
--- pulled them out of. Deciding the anchor once, here, removes that whole class
--- of bug rather than timing around it.
---
--- Returns the square to build on, or nil when the start has to begin again
--- because nothing usable has loaded yet.
local function anchorSquare(playerObj, square)
    local centre = playerObj:getCurrentSquare() or square

    -- Not knowing where the player is is not the same as knowing they are in
    -- water, so this waits rather than rescuing someone who never needed it.
    if not centre then
        print("[HeadForTheHills] spawn square has not streamed in yet; starting over shortly")
        return nil
    end

    if not isWaterSquare(centre) then return centre end

    -- Only reachable through a custom coordinate, since all twelve cabins are
    -- on dry land. There is no "leave them there" branch on purpose.
    -- Three passes, best first. One pass was not enough, and the obvious second
    -- one was not either. Both measured live in session 9, starting at
    -- 11280,6568 in the Ohio:
    --
    -- * "any floor that is not water" picked 11286,6580, the inside of a
    --   boathouse standing out over the river. Dry, and not land: 7 of its 9
    --   neighbours are water. The player spawned clipping the wall and the
    --   engine shoved them indoors.
    -- * "outdoors and outside a building" picked 11287,6586, the open jetty,
    --   still 33 of 49 water. A deck is outdoors and belongs to no building, so
    --   rejecting buildings does not reject decks.
    -- * dirt-or-grass picked 11274,6592 on blends_natural_01_70, real bank, at
    --   the same 12 tiles out, and independently the square the generator was
    --   placed on that run.
    --
    -- What separates a bank from a deck is the ground, and this file already
    -- classifies ground the way vanilla does. Nothing here names a sprite.
    local dry = findSquare(centre, 1, WATER_RESCUE_RADIUS, isRealGround)
    local how = "open ground"

    if not dry then
        -- A bank that is all gravel, sand or paving. Outdoors and clear of any
        -- building, just not ground a well would be allowed to stand on.
        dry = findSquare(centre, 1, WATER_RESCUE_RADIUS, isStandableGround)
        how = "hard standing"
    end

    if not dry then
        -- Last resort, and the reason the promise still holds: any floor at all
        -- beats leaving someone in the water. This is the pass that picks a
        -- boathouse, and it now only runs when 60 tiles hold nothing better.
        dry = findSquare(centre, 1, WATER_RESCUE_RADIUS, isDryLand)
        how = "the only dry floor nearby"
    end

    if dry then
        print(string.format(
            "[HeadForTheHills] start coordinate is water; moved to %s at %d,%d",
            how, dry:getX(), dry:getY()))
        playerObj:teleportTo(dry:getX(), dry:getY(), dry:getZ())
        return dry
    end

    -- No dry square in anything that has loaded, so the coordinate sits deep in
    -- open water. Fall back to a cabin that is known good. Its chunk is not
    -- loaded yet, so nothing can be placed on this pass: teleportTo streams it
    -- in and the start runs again once the square exists.
    local cabins = HFTH_SpawnRegion and HFTH_SpawnRegion.CABINS
    local cabin = cabins and cabins[ZombRand(#cabins) + 1]
    if not cabin then
        print("[HeadForTheHills] start coordinate is water and the cabin list is missing; cannot rescue")
        return centre
    end

    print(string.format(
        "[HeadForTheHills] start coordinate is open water with no dry ground within %d tiles; using a cabin at %d,%d",
        WATER_RESCUE_RADIUS, cabin.posX, cabin.posY))
    playerObj:teleportTo(cabin.posX, cabin.posY, cabin.posZ or 0)
    return nil
end

local function runSpawn(playerObj, opts, centre)
    applySeason(opts)
    giveStartingEquipment(playerObj, opts)
    spawnStartingVehicle(playerObj, opts, centre)

    -- Where the buildings and the water are, read once. The well and the
    -- generator both measure themselves against it, in opposite directions, and
    -- re-deriving it per candidate square is what makes that expensive.
    local ctx = scanContext(centre)
    spawnWell(playerObj, opts, centre, ctx)
    spawnGenerator(playerObj, opts, centre, ctx)
end

local function onNewGame(playerObj, square)
    local opts = options()
    if not opts or not playerObj then return end

    local centre = anchorSquare(playerObj, square)
    if not centre then
        restartPending = {
            playerObj = playerObj, opts = opts, ticks = RESTART_TICKS,
        }
        Events.OnTick.Add(restartSpawn)
        return
    end

    runSpawn(playerObj, opts, centre)
end

--- Second attempt, once the square the player was moved to actually exists.
restartSpawn = function()
    if not restartPending then
        Events.OnTick.Remove(restartSpawn)
        return
    end

    restartPending.ticks = restartPending.ticks - 1
    if restartPending.ticks > 0 then return end

    local job = restartPending
    restartPending = nil
    Events.OnTick.Remove(restartSpawn)

    local centre = job.playerObj:getCurrentSquare()
    if not centre then
        print("[HeadForTheHills] square still not loaded on the second attempt; nothing placed")
        return
    end
    if isWaterSquare(centre) then
        print("[HeadForTheHills] still standing in water on the second attempt; nothing placed")
        return
    end

    runSpawn(job.playerObj, job.opts, centre)
end

Events.OnNewGame.Add(onNewGame)
