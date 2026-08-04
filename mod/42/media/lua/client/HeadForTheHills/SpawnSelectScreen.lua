-- Head for the Hills! - the Remote Cabin row on the Starting Location screen
--
-- Vanilla builds that screen around getMapInfo(), which is Java-side and keyed
-- on media/maps/<name>/. This mod adds its region through OnSpawnRegionsLoaded
-- and ships no map directory, so getMapInfo("Remote Cabin") returns nil and the
-- row falls down every else branch on the screen. Two of those are visible:
--
-- 1. BLANK DESCRIPTION. MapSpawnSelect:fillList takes the no-info branch and
--    sets item.desc = "" (MapSpawnSelect.lua:494-502). render paints the panel
--    straight from that field at line 717, so it comes out empty while every
--    vanilla location has copy in it.
--
-- 2. THE CAMERA LIES. The same branch leaves item.zoomX nil, so render skips
--    the transitionTo at line 728 and falls to the elseif at 729-734, which
--    flies to region.points.unemployed[1]. That is always CABINS[1] at
--    12473,8919. The player gets a random one of the list, so picking Remote
--    Cabin can show a spot near Louisville and then drop them in the 3x3 shed
--    at 14050,5195, about 4,000 tiles away.
--
-- The description is fixable because we have real copy to put there. The camera
-- is not: the cabin is drawn at spawn, so no single point on that map is the
-- truth, and any point we fly to is a guess presented as an answer. So the
-- camera is left alone and the description says outright that the map cannot
-- show it. If the region ever gains map markers, showing all of them would be
-- the better answer.
--
-- WRAPPING create() IS NOT NEEDED. Neither fix adds a control, and both target
-- methods hang off the class table (MapSpawnSelect.lua:3 derives it from
-- ISPanelJoypad), so they can be wrapped directly at load. Note for anyone
-- extending this later: createChildren does not exist on this class, and
-- wrapping a method that is not there loads clean and silently does nothing.
--
-- The dead branch at MapSpawnSelect.lua:740-746 is genuinely dead on B42 -
-- WORLD_MAP is set to nil at line 467 and nothing else in the vanilla tree ever
-- assigns it - so the mapPanel path at 724-738 is the only camera code that
-- runs, and it is the only one this file has to account for.

-- Guarantees the class exists before we wrap it, whatever order mod client Lua
-- happens to load in. An already-loaded file returns cached.
require "OptionScreens/MapSpawnSelect"

-- Wrapping an already-wrapped method would build a self-referential chain, so
-- bail if this file gets executed twice.
if HFTH_SpawnSelectScreenInstalled then return end
HFTH_SpawnSelectScreenInstalled = true

local DESC_KEY = "UI_HeadForTheHills_RemoteCabin_desc"

--- The item behind the highlighted row, or nil.
--- Vanilla reads this without a guard at MapSpawnSelect.lua:707, but the render
--- wrapper below runs before that line, so it cannot borrow the assumption that
--- a row is always selected.
local function selectedItem(screen)
	local listbox = screen and screen.listbox
	if not listbox or not listbox.items then return nil end
	local row = listbox.items[listbox.selected]
	return row and row.item
end

--- True when this row is our region.
--- Matched on region.name rather than the displayed name, which belongs to
--- whatever getMapInfo returned and is not ours to rely on. HFTH_SpawnRegion is
--- read here rather than at load so shared/client order cannot matter.
local function isRemoteCabin(item)
	local region = item and item.region
	if not region or not HFTH_SpawnRegion then return false end
	return region.name == HFTH_SpawnRegion.NAME
end

local originalFillList = MapSpawnSelect.fillList
function MapSpawnSelect:fillList()
	originalFillList(self)

	-- Runs after the original rather than replacing it, so the row is built by
	-- vanilla exactly as before and only the empty field is filled in. fillList
	-- is called again whenever the screen rebuilds its list, and re-running this
	-- is harmless.
	local items = self.listbox and self.listbox.items
	if not items then return end
	for _, row in ipairs(items) do
		if isRemoteCabin(row.item) then
			row.item.desc = getText(DESC_KEY)
		end
	end
end

local originalRender = MapSpawnSelect.render
function MapSpawnSelect:render()
	-- Vanilla only moves the camera when the selection changed since the last
	-- frame (MapSpawnSelect.lua:725). Marking our row as already handled leaves
	-- the map wherever it was instead of flying to a cabin the player most
	-- likely will not get. Selecting any other row afterwards still differs from
	-- selectedMapIndex, so every real location keeps its camera move.
	if isRemoteCabin(selectedItem(self)) then
		self.selectedMapIndex = self.listbox.selected
	end

	originalRender(self)
end

-- Set last, so it means "this file ran to the end and both wraps are on the
-- class", not merely "the file started". The install guard above cannot say
-- that: it is set before the wrapping so that it can prevent it.
-- tests/verify_spawn_screen.py reads this.
MapSpawnSelect.HFTH_wrapped = true
