# Installing

## What you need

- FreeCAD 1.0 or newer, with the CAM workbench.
- Windows 10 or 11, or Linux, on an x86-64 computer.
- A graphics card and driver with OpenGL 4.5 or 4.6, and 2 GB or more of graphics memory (tick
  *Minimal mode* on the simulator's start screen for cards with 2-4 GB).

macOS is not supported for now: its OpenGL stops at version 4.1. See [limits](limits.md).

## Installing the add-on

**With FreeCAD's Addon Manager:** add this repository as a custom repository (Edit > Preferences >
Addon Manager > Custom repositories, its URL and branch `main`), then install *BearCAM Simulator*
from the Addon Manager and restart FreeCAD.

**By hand:** copy or clone this repository into FreeCAD's `Mod` folder as `BearCAMSimulator`, then
restart FreeCAD. The `Mod` folder is in FreeCAD's user data folder, whose name differs between
FreeCAD versions and systems. To find it, type this in FreeCAD's Python console (View > Panels >
Python console) and use the `Mod` folder inside the folder it prints (make it if it is missing):

    App.getUserAppDataDir()

## The simulator program

The add-on starts the BearCAM simulator, a separate program. The first time you use the command,
it offers to download the simulator for your platform from this project's releases. Before it is
used, the download is checked against the SHA-256 pinned in `bearcam_sim/release.json`; a file
that does not match is not used. The simulator is kept in FreeCAD's user data folder, under
`BearCAMSimulator/<version>/<platform>`.

You can instead point the add-on at a simulator you unpacked yourself: choose *Choose folder...*
when asked, or set the parameter `LocalViewerFolder` (Tools > Edit parameters > BaseApp >
Preferences > Mod > BearCAMSimulator) to the folder that holds `stockviewer` (or
`stockviewer.exe`).

On Linux, an archive you unpack yourself keeps the program executable. On Windows, until the
simulator's releases are signed, Windows may warn about an unknown publisher the first time it
starts.

## Settings and files

- **The add-on**, in FreeCAD's parameters (BaseApp > Preferences > Mod > BearCAMSimulator):
  `LocalViewerFolder`, `RapidRate` (the rate rapids play at, mm/min, default 5000) and
  `PostChoices` (the post processor chosen for each job that names none).
- **Each job's hand-off**, in FreeCAD's cache folder under `BearCAMSimulator/jobs` (your own
  folder, `App.getUserCachePath()`): the posted program, the job file, and the simulator's log.
- **The simulator** remembers its speed step, smoothness slider, minimal mode, last view, folded
  panels and settings in `%APPDATA%\BearCAM\Simulator\settings.txt` on Windows and
  `~/.config/bearcam-simulator/settings.txt` on Linux.

## Removing it

Delete the add-on's folder from FreeCAD's `Mod` folder (or uninstall it in the Addon Manager),
and delete `BearCAMSimulator` from FreeCAD's user data folder to remove the downloaded simulator.
