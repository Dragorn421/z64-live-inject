# z64-live-inject

This allows to automatically export and object and load it into an instance of the game running inside the [Project64 emulator](https://www.pj64-emu.com/).

[Demonstration video](https://cdn.discordapp.com/attachments/647987279461089282/739130332560883768/showcase_live_zobj_loading_anim_and_blender.webm)

## Requirements

A Project64 version that supports scripts. Use [dev builds](https://www.pj64-emu.com/nightly-builds) if the public version doesn't

[Blender 2.79](https://download.blender.org/release/Blender2.79/), other 2.7x versions may work too

[zzconvert](http://www.z64.me/tools/zzconvert)

### Optional dependencies

 - the `obj_export_so` Blender addon
 - the `io_export_objex` Blender addon
 - the `io_export_objex2` Blender addon

## Known issues

The script running in Project64 can act weird, show errors or crash Project64. It is probably more of a Project64 issue than the script's fault. "Workaround": restart Project64 if needed and use savestates

## Limitations

Currently only displays one `SKEL_`/`ANIM_` or one `DL_` line from zzconvert's output (ie a single Blender object).

## Setup

### ROM

Compile and inject the actor from its source `in_game_viewer.c` with actor id 5 into a MQ debug rom (other roms likely won't work due to different struct offsets in memory).

Add the actor to a test map and inject the map into the rom.

If successful, the actor should print `A>P 0x... / P>A 0x...` debug text on screen in-game.

### Project64

##### Enable the debugger

Go to settings `Options > Settings` and uncheck "Hide advanced settings" in the "Options" tab.

In the "Options > Advanced" tab, check "Enable debugger".

##### Install the script

Where the Project64.exe is located, create the `Scripts` folder if it doesn't exist (alongside `Config`, `Plugin`, ...).

Copy `feedback_loop.js` into the `Scripts` folder.

If successful, you can open the Scripts window in `Debugger > Scripts...` and `feedback_loop.js` should be in the list.

### Blender

Open the Blender console for useful info about any error.

Install and enable the addon in Blender 2.79 (the `oot64_in_game_viewer` folder in this repository).

Open the addon preferences:

![blender addon default preferences](https://421.es/doyu/1l4c36)

Set the `zzconvert location` to the path to `zzconvert.exe` (the command-line-interface one, not the `zzconvert-gui.exe` graphical-user-interface one).

Set `Export as` to use the desired export addon. The addon must be installed and enabled already (see [Optional dependencies](#optional-dependencies)).

## Usage

Run Project64 and load the ROM with the `in_game_viewer.c` actor, load the map where it is present.

In Project64, run the `feedback_loop.js` script (double click, or right click > Run, in the Scripts window).

In Blender, run the operator through operator search:
 - hit Space (by default) to bring up operator search
 - search for the operator by typing part or all of `Export the current blend and load it live.`
 - choose the appropriate result

After a few seconds, Blender contents will be displayed in-game.

The operator can be run as many times as wanted.
