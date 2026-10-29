# Changes

## 0.6.1 (29 October 2026)

### Changed

- **A smaller download.** The simulator is about 1 MB again (0.6.0: about 11 MB). The machine
  models, most of 0.6.0's download, are a download of their own (about 10 MB), checked against
  their own pinned SHA-256 and offered only the first time a job is shown on a machine:
  *Download*, or *Without the machine* (the job's machine is then set to None). Jobs on no machine
  never fetch them.

### Fixed

- A job set to a machine whose files are missing (not downloaded, or deleted) now plays without
  the machine, and the simulator says so, instead of not opening.

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

## 0.5.1 (26 October 2026)

### Fixed

- **Machine posts (FreeCAD 26.3):** a job with a machine is posted with that machine's post
  processor, its settings and the job's overrides, through FreeCAD's machine-post export, ahead of
  a legacy or remembered post; no G-code editor or remote upload runs.
- **Makera posts:** standalone `M851 S…` / `M852` auxiliary-output blocks from the official
  `makera_26_MCH` and `makera_legacy` posts become comments in the simulation copy, so their PWM
  no longer changes the simulated spindle speed; Makera's minimum spindle speed is kept where
  FreeCAD 26.3 leaves it unset.
- Tool and operation labels with parentheses no longer break the posted comments. The unmodified
  export is kept beside the simulator's input as `posted.nc`.

## 0.5.0 (22 October 2026)

First public release.
