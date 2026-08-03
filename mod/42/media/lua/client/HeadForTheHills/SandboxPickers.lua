-- Head for the Hills! - live sandbox pickers
--
-- HeadForTheHills.StartingVehicle and HeadForTheHills.StartingEquipmentList are
-- declared as plain `string` options in sandbox-options.txt. That matters: the
-- vanilla screen moves string settings in and out of the save by calling
-- control:getText() / control:setText() on whatever control object happens to
-- sit in self.controls[optionName] (SandboxOptions.lua settingsToUI /
-- settingsFromUI). So a control that speaks getText/setText is a drop-in, and
-- the choice rides the normal per-save Sandbox Vars system with no extra
-- persistence layer and no second settings screen.
--
-- This file swaps the default text-entry control for those two settings with
-- pickers built live from whatever is loaded right now (vanilla + any installed
-- mods), via getScriptManager():getAllVehicleScripts() / :getAllItems().

-- Guarantees SandboxOptionsScreen exists before we wrap it, regardless of the
-- order mod client Lua happens to load in. Already-loaded files return cached.
require "OptionScreens/SandboxOptions"
require "ISUI/ISCollapsableWindowJoypad"

-- Wrapping an already-wrapped method would build a self-referential chain, so
-- bail if this file gets executed twice.
if HFTH_SandboxPickersInstalled then return end
HFTH_SandboxPickersInstalled = true

local VEHICLE_SETTING = "HeadForTheHills.StartingVehicle"
local EQUIPMENT_SETTING = "HeadForTheHills.StartingEquipmentList"
local FALLBACK_VEHICLE = "Base.PickUpTruck"

local function controlWidth()
	return 150 + ((getCore():getOptionFontSizeReal() - 1) * 50)
end

local function controlHeight()
	return getTextManager():getFontFromEnum(UIFont.Medium):getLineHeight() + 6
end

local function parseDelimitedSet(text)
	local set = {}
	for value in string.gmatch(text or "", "([^;]+)") do
		set[value] = true
	end
	return set
end

-- ---------------------------------------------------------------- vehicle ---

local function buildVehicleComboBox(screen, setting, tooltip)
	local control = ISComboBox:new(0, 0, controlWidth(), controlHeight(), screen, nil, setting.name)
	if tooltip then
		control.tooltip = { defaultTooltip = tooltip }
	end
	control:initialise()

	-- VehicleScript in B42 has getName()/getFullName() but no getDisplayName()
	-- or getSeatNumber(); calling those throws out of the Kahlua binding.
	local vehicles = {}
	local scripts = getScriptManager():getAllVehicleScripts()
	for i = 0, scripts:size() - 1 do
		local script = scripts:get(i)
		table.insert(vehicles, { label = script:getName(), fullName = script:getFullName() })
	end
	table.sort(vehicles, function(a, b) return a.label < b.label end)

	for _, vehicle in ipairs(vehicles) do
		control:addOptionWithData(vehicle.label, vehicle.fullName)
	end

	function control:indexOfFullName(fullName)
		for i, option in ipairs(self.options) do
			if type(option) == "table" and option.data == fullName then
				return i
			end
		end
		return nil
	end

	function control:getText()
		local option = self.options[self.selected]
		if type(option) == "table" and option.data then
			return option.data
		end
		return ""
	end

	-- A saved vehicle can go missing between sessions if the mod that supplied
	-- it was removed, so fall back rather than leaving an arbitrary selection.
	function control:setText(value)
		local index = self:indexOfFullName(value) or self:indexOfFullName(FALLBACK_VEHICLE)
		if index then
			self.selected = index
		end
	end

	control:setText(setting.text)
	return control
end

-- -------------------------------------------------------------- equipment ---

local function drawEquipmentRow(listbox, y, item, alt)
	if item.height <= 0 then return y + item.height end

	local entry = item.item
	local boxSize = 14
	local boxY = y + (item.height - boxSize) / 2
	listbox:drawRectBorder(6, boxY, boxSize, boxSize, 1, 1, 1, 1)
	if entry.selected then
		listbox:drawRect(8, boxY + 2, boxSize - 4, boxSize - 4, 1, 0.55, 0.8, 1)
	end

	local color = listbox.textColor
	listbox:drawText(item.text, 6 + boxSize + 8, y + (item.height - listbox.fontHgt) / 2,
		color.r, color.g, color.b, color.a, listbox.font)
	return y + item.height
end

HFTH_EquipmentModal = ISCollapsableWindowJoypad:derive("HFTH_EquipmentModal")

function HFTH_EquipmentModal:new(control)
	local width = 460
	local height = 520
	local o = ISCollapsableWindowJoypad.new(self,
		(getCore():getScreenWidth() - width) / 2,
		(getCore():getScreenHeight() - height) / 2,
		width, height)
	o.control = control
	o.title = getText("Sandbox_HeadForTheHills_StartingEquipmentList")
	o.backgroundColor = { r = 0, g = 0, b = 0, a = 0.95 }
	o:setResizable(false)
	return o
end

function HFTH_EquipmentModal:refreshList()
	local filter = string.lower(self.searchEntry:getInternalText() or "")
	self.listbox:clear()
	for _, entry in ipairs(self.allItems) do
		if filter == "" or string.find(string.lower(entry.label), filter, 1, true) then
			self.listbox:addItem(entry.label, entry)
		end
	end
end

-- Written back on every toggle rather than on a confirm button, so closing the
-- window by any route (button, titlebar X) keeps the selection.
function HFTH_EquipmentModal:commit()
	if not self.allItems then return end
	local chosen = {}
	for _, entry in ipairs(self.allItems) do
		if entry.selected then
			table.insert(chosen, entry.fullName)
		end
	end
	self.control:setText(table.concat(chosen, ";"))
end

function HFTH_EquipmentModal:onRowClicked(entry)
	if not entry then return end
	entry.selected = not entry.selected
	self:commit()
end

-- Overrides close() rather than adding a separate handler: the inherited
-- titlebar X routes through close(), and the base implementation only hides the
-- window, which would leave a stale invisible modal in the UI manager.
function HFTH_EquipmentModal:close()
	self:commit()
	self:removeFromUIManager()
end

function HFTH_EquipmentModal:createChildren()
	ISCollapsableWindowJoypad.createChildren(self)

	local pad = 8
	local titleBarHeight = self:titleBarHeight()
	local buttonHeight = 25
	local searchHeight = 25

	self.searchEntry = ISTextEntryBox:new("", pad, titleBarHeight + pad, self.width - pad * 2, searchHeight)
	self.searchEntry.font = UIFont.Medium
	self.searchEntry.onTextChange = function() self:refreshList() end
	self.searchEntry:initialise()
	self.searchEntry:instantiate()
	self.searchEntry:setClearButton(true)
	self:addChild(self.searchEntry)

	local listY = self.searchEntry:getBottom() + pad
	local listHeight = self.height - listY - buttonHeight - pad * 2
	self.listbox = ISScrollingListBox:new(pad, listY, self.width - pad * 2, listHeight)
	self.listbox:initialise()
	self.listbox:instantiate()
	self.listbox.itemheight = 22
	self.listbox.font = UIFont.Small
	self.listbox.drawBorder = true
	self.listbox.target = self
	self.listbox.onmousedown = function(target, entry) target:onRowClicked(entry) end
	self.listbox.doDrawItem = drawEquipmentRow
	self:addChild(self.listbox)

	-- Not named closeButton: the parent class already owns a field by that name
	-- for its titlebar X, and shadowing it breaks that button's layout/visibility.
	self.doneButton = ISButton:new(self.width - pad - 90, self.height - pad - buttonHeight,
		90, buttonHeight, getText("UI_btn_close"), self, HFTH_EquipmentModal.close)
	self.doneButton:initialise()
	self.doneButton:instantiate()
	self:addChild(self.doneButton)

	-- getAllItems() is the item-side parallel of getAllVehicleScripts(); unlike
	-- VehicleScript, Item:getDisplayName() is safe (it falls back to full name).
	local selected = parseDelimitedSet(self.control:getText())
	self.allItems = {}
	local items = getScriptManager():getAllItems()
	for i = 0, items:size() - 1 do
		local item = items:get(i)
		local fullName = item:getFullName()
		table.insert(self.allItems, {
			fullName = fullName,
			label = item:getDisplayName() .. "  (" .. fullName .. ")",
			selected = selected[fullName] or false,
		})
	end
	table.sort(self.allItems, function(a, b) return a.label < b.label end)

	self:refreshList()
end

local function buildEquipmentButton(screen, setting, tooltip)
	local control = ISButton:new(0, 0, controlWidth(), controlHeight(), "Choose Items...", screen, nil)
	control.tooltip = tooltip
	control:initialise()
	control:instantiate()

	-- The screen persists this control through getText/setText like any string
	-- setting; the visible button label is separate (ISButton uses self.title).
	control.storedValue = setting.text or ""

	function control:getText()
		return self.storedValue or ""
	end

	function control:setText(value)
		self.storedValue = value or ""
		local count = 0
		for _ in string.gmatch(self.storedValue, "([^;]+)") do
			count = count + 1
		end
		self:setTitle(count == 0 and "Choose Items..." or (count .. " item(s) selected"))
	end

	control:setText(control.storedValue)

	control.onclick = function()
		local modal = HFTH_EquipmentModal:new(control)
		modal:initialise()
		modal:addToUIManager()
	end

	return control
end

-- ------------------------------------------------------------------- hook ---

-- createControlForSetting is called per setting from createPanel and returns the
-- control the screen then stores in self.controls, so it is the narrowest hook
-- that still lets a replacement control participate in save/load and presets.
local originalCreateControlForSetting = SandboxOptionsScreen.createControlForSetting

function SandboxOptionsScreen:createControlForSetting(setting, tooltip)
	if setting.name == VEHICLE_SETTING then
		return buildVehicleComboBox(self, setting, tooltip)
	elseif setting.name == EQUIPMENT_SETTING then
		return buildEquipmentButton(self, setting, tooltip)
	end
	return originalCreateControlForSetting(self, setting, tooltip)
end
