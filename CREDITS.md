# Credits and third-party notices

## In the simulator's release archives

- **Microsoft Visual C++ runtime libraries** (Windows archive only): `msvcp140.dll`, `msvcp140_1.dll`,
  `msvcp140_2.dll`, `vcruntime140.dll`, `vcruntime140_1.dll`. Copyright Microsoft Corporation;
  redistributed unmodified as "distributable code" under the Microsoft Visual Studio licence
  terms. They are not covered by this project's licences.
- **The PrintNC V4 machine model**: `machines/printnc-clean.glb` and `machines/printnc-v4.json`, a
  model of the PrintNC V4 CNC router, adapted from the PrintNC design by the PrintNC project
  (https://github.com/threedesigns/printNC, https://wiki.printnc.info), which is licensed under the
  Creative Commons Attribution 4.0 International licence (CC BY 4.0,
  https://creativecommons.org/licenses/by/4.0/). Changes made by Bearcam.io: the design's assembly
  simplified for display (fasteners, sensors and cable supports removed), its parts grouped by the
  axis that moves them, coloured, and converted to a glTF mesh. This adapted model is also licensed
  under CC BY 4.0, not under the BearCAM simulator's licence, and is provided as is, without
  warranties (see the licence). The PrintNC project has not endorsed this model or the BearCAM
  simulator.
- **The Makera Carvera Air machine model**: `machines/carvera-air.glb` and
  `machines/carvera-air.json`, an independent reference model of the Makera Carvera Air, drawn by
  Bearcam.io from Makera's published dimensions and product photographs; not factory CAD.
  Independent reference model; not affiliated with or endorsed by Makera. Makera and Carvera are
  trademarks of their owner, used only to say which machine the model depicts.

Nothing else from a third party is compiled into the simulator. It uses the system's OpenGL
driver and, on Linux, the system's X11 libraries, which are not distributed with it.

## Used by the add-on, not distributed with it

- **FreeCAD** (LGPL-2.1-or-later), the program the add-on runs in. The add-on uses FreeCAD's
  Python interface and its CAM workbench's post processors; it contains no FreeCAD code.
- **Qt for Python (PySide)** and **Python**, as FreeCAD provides them.

## Names and logos

- BearCAM and the bear logo (including `Resources/icons/BearCAMSimulate.png`) are trademarks of
  Bearcam.io. Neither licence in this repository grants any right to use them, other
  than to refer to this project.
- FreeCAD is a trademark of the FreeCAD Project Association; it is used here only to say which
  program the add-on works with. This project is not part of, or endorsed by, the FreeCAD
  project.
