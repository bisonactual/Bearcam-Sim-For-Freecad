# Changes

## 0.6.0 (28 October 2026)

### New

- **More cutters.** Dovetail cutters, tapered ball nose and reamers (FreeCAD's own bit shapes);
  lollipop cutters, countersinks and tapered end mills (custom bit shapes named so). Any other bit
  that cuts (a radius mill, a slitting saw, a tap, your own custom shapes) is measured from its
  solid and simulated with its true outline. Undercuts (dovetails, lollipops, T-slots, thread
  mills) show as they are cut.
- **Drag knives.** An operation with a Dragknife dressup is cut with a drag knife: the blade trails
  the holder by the dressup's offset and swings round as the path turns, so you can see whether the
  corners come out square.
- **Stock from any solid.** An existing solid as stock (a casting, a part from an earlier setup, a
  hexagon or a tube), a box turned off the axes or a cylinder along Y now simulates; it goes to the
  simulator as a mesh.
- **SpaceMouse.** A 3Dconnexion SpaceMouse moves the simulator's view as the cap moves (Windows:
  read directly; Linux: through spacenavd). Its speed and axis directions can be set
  ([using it](docs/use.md)).
- **Machines.** A 3-axis job can be shown on a **Makera Carvera Air** or a **PrintNC V4**: the
  machine's frame, gantry or table and spindle move with the tool, with the stock in the middle of
  its bed. The first Simulate in BearCAM for a job asks which (or none) and remembers it; *CAM >
  BearCAM simulator machine...* changes it. In the simulator, **M** shows or hides the machine and
  **D** its dust shoe (the Carvera Air's). Display only: the machine is never cut or checked for
  collisions.

### Fixed

- **FreeCAD 1.0 and 1.1:** the add-on now loads there. In 0.5.0 its commands never appeared; the
  commands now sit after *Post Process* in the CAM menu, and a job without a post processor can
  pick one.

### Changed

- Jobs with a T-slot cutter, thread mill, dovetail or lollipop now open in the volume engine,
  which shows undercuts (the height field cannot); **E** still switches.
- In a job shown on a machine with a dust shoe, **D** shows or hides the dust shoe instead of
  folding the DRO; the DRO's own button still folds it.
- The simulator download is about 11 MB (0.5.0: under 1 MB): it now carries the machine models.
- The simulator's licence (`LICENSE-SIMULATOR.txt`) is final; the PrintNC model in the download is
  under CC BY 4.0, credited in `CREDITS.md`.

## 0.5.0 (22 October 2026)

First public release.
