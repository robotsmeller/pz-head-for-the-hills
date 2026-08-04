-- Head for the Hills! - start at a coordinate you picked yourself (#12)
--
-- WHY THIS IS A SANDBOX OPTION AND NOT A CONTROL ON THE MAP SCREEN:
-- an earlier design note in this project claimed a sandbox option could not
-- reach the spawn, because starting location is chosen before the sandbox
-- screen ever opens. That is true and it is also beside the point. Nothing
-- builds the point list from the option. The list is read much later:
--
--   1. MapSpawnSelect:clickNext:644 stores a live reference to the region table
--      SpawnRegion.lua inserted. Line 645 hands the engine only a name string.
--   2. SandboxOptions.lua:972, the PLAY branch, calls setSandboxVars, which runs
--      settingsFromUI then options:toLua(). This is where SandboxVars is filled.
--   3. CharacterCreationProfession.initWorld:1086 reads that same region object
--      back, takes .points[profession] at 1097 and picks from it at 1105.
--
-- Step 2 happens before step 3, so overwriting the region's points here lands.
--
-- WHY setSandboxVars AND NOT THE OBVIOUS ALTERNATIVES:
-- * CharacterCreationProfession.initWorld is registered with
--   Events.OnInitWorld.Add(CharacterCreationProfession.initWorld) at
--   CharacterCreationProfession.lua:1562, which captures the function value at
--   load. Reassigning the field afterwards changes nothing the event calls.
-- * SandboxOptionsScreen:onOptionMouseDown is captured by value into the PLAY
--   button when the button is built (SandboxOptions.lua:422), so wrapping it
--   only works if the wrap beats that screen's create().
-- Neither hazard applies to setSandboxVars: it is called as self:setSandboxVars()
-- at line 972, looked up at call time, so a class-level wrap always wins.
--
-- Same family as createChildren: a wrap on a name nothing dispatches through
-- loads clean and silently does nothing.

require "OptionScreens/SandboxOptions"
require "OptionScreens/MapSpawnSelect"

-- Wrapping an already-wrapped method would build a self-referential chain, so
-- bail if this file gets executed twice.
if HFTH_CustomSpawnPointInstalled then return end
HFTH_CustomSpawnPointInstalled = true

local OPTION = "CustomSpawnPoint"

--- The region the player picked on the Starting Location screen, or nil.
--- nil is normal: loading an existing save can reach character creation without
--- MapSpawnSelect ever being shown (see the comment at initWorld:1088).
local function chosenRegion()
	local screen = MapSpawnSelect and MapSpawnSelect.instance
	return screen and screen.selectedRegion or nil
end

local originalSetSandboxVars = SandboxOptionsScreen.setSandboxVars
function SandboxOptionsScreen:setSandboxVars()
	-- Delegate first. Until this returns, SandboxVars holds the previous world's
	-- values or nothing at all, so reading our option before it is the exact
	-- mistake that made a sandbox option look impossible in the first place.
	originalSetSandboxVars(self)

	local region = chosenRegion()
	if not region or not HFTH_SpawnRegion then return end

	-- Only ever touch our own region. Someone starting in Muldraugh has a
	-- vanilla region table in that same field and it is not ours to rewrite.
	if region.name ~= HFTH_SpawnRegion.NAME then return end

	local settings = SandboxVars and SandboxVars.HeadForTheHills
	local typed = settings and settings[OPTION] or ""
	local point, reason = HFTH_SpawnRegion.parsePoint(typed)

	-- Applied on every pass, including when nothing was typed. The region table
	-- outlives this screen, so a coordinate entered once and later cleared would
	-- otherwise stay live and override the twelve cabins on a following
	-- character. setCustomPoint(nil) puts the twelve back.
	HFTH_SpawnRegion.setCustomPoint(region, point)

	if point then
		print(string.format(
			"[HeadForTheHills] starting at custom point %d,%d instead of the twelve cabins",
			point.posX, point.posY))
	elseif reason ~= "empty" then
		print(string.format(
			"[HeadForTheHills] could not read custom start coordinate %q (%s); using the twelve cabins",
			tostring(typed), tostring(reason)))
	end
end

-- Set last, so it means "this file ran to the end and the wrap is on the class".
-- tests/verify_custom_spawn.py reads this.
SandboxOptionsScreen.HFTH_customSpawnWrapped = true
