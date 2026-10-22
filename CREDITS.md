# Credits and third-party notices

## In the simulator's release archives

- **Microsoft Visual C++ runtime libraries** (Windows archive only): `msvcp140.dll`, `msvcp140_1.dll`,
  `msvcp140_2.dll`, `vcruntime140.dll`, `vcruntime140_1.dll`. Copyright Microsoft Corporation;
  redistributed unmodified as "distributable code" under the Microsoft Visual Studio licence
  terms. They are not covered by this project's licences.

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
