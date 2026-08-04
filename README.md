# Head for the Hills!

A start-scenario mod for Project Zomboid Build 42. Your survivor saw it coming and got out ahead of the outbreak, up to a remote cabin. You start there, stocked with basic supplies and a vehicle nearby. The nearest town is still a drive away if you want to push your luck.

Pick Remote Cabin as your starting location on the new-game screen.

## What you get

- One of seventeen hand-picked cabins, drawn at random and not shown on the map beforehand. They run from a one-room shack to a 20x11 farmhouse, and the haul to the nearest town runs from about 600 tiles to about 2,400, so the draw decides how hard your start is.
- **A vehicle** outside, with the key in your pocket. Choose which one, and its condition and fuel.
- **The key to the cabin**, so you are not locked out of the place you have supposedly been living in.
- **A well** in the yard if the property has none, six to ten tiles from the house and clear of standing water.
- **A generator** against the wall if the property has none. You choose whether it starts fuelled and whether it starts wired in. It is never running when you arrive.
- **Your starting season**, which is the middle month of the one you pick rather than the first.

Anything the cabin already has is left alone. The mod does not dig a second well beside an existing one or drop a spare generator next to a working one.

## Sandbox options

Everything above is a setting, on the **Head for the Hills!** sandbox page.

Two of them are pickers rather than text fields: the starting vehicle is a dropdown built from every vehicle currently loaded, and the starting equipment is a searchable multi-select over every item currently loaded. Both include content from whatever mods you have installed, because they read the game rather than a fixed list.

**Custom Start Coordinate** overrides the cabin draw. Type a map coordinate from [map.projectzomboid.com](https://map.projectzomboid.com/) as `X,Y` or in the site's own `12462x8938` form. A spot you pick yourself gets none of the vetting the cabins had, so things may land oddly or not fit. If it is in water you are moved to the nearest real ground.

## Requirements

- Project Zomboid Build 42.20.0 or later
- No other mods. Everything the mod places is base-game content.

## Multiplayer

The world objects are created once by the host or dedicated server, and the starting inventory is granted per player, which is how vanilla does both.

The sandbox options appear on a server's settings screen automatically, but the two pickers do not: that screen builds its controls differently, so the starting vehicle and equipment show as plain text boxes there. Type a vehicle id such as `Base.PickUpTruck`, and item ids separated by semicolons.

**Multiplayer is untested.** It is written to vanilla's own patterns and it is not verified, because the author has no server to try it on. Reports welcome.

## Install

Subscribe on the Steam Workshop, or copy `mod/` to `Zomboid/mods/HeadForTheHills`.

## License

MIT
