# Using it

## Simulate in BearCAM

In the CAM workbench, select a job (or anything in it) and click **Simulate in BearCAM**: it is on
the *Project Setup* toolbar and in the *CAM* menu, after *Post Process Selected*. With one job in
the document there is nothing to select; with several, it asks which.

1. **Post.** A job with a machine uses that machine's post processor, settings and the job's
   property overrides, through FreeCAD's machine-post export. This takes precedence over a
   legacy or remembered post choice. A job without a machine uses its legacy post; if it names
   none, the command asks which legacy post to use and remembers it. No G-code editor or remote
   upload runs for machine posts. A job posted as several files is played as one program, in order.
2. **Machine.** The first time for a job, the command asks which machine to show it on: *None*,
   the *Makera Carvera Air* or the *PrintNC V4* (see [Machine](#machine)), and remembers it for that
   job.
3. **Describe.** The stock, the tools, the work offset, the operations and the machine go into a
   job file next to the program ([the job file](../schema/job-v1.md)).
4. **Play.** The simulator opens in its own window. Change the job and click the command again: the
   open simulator reads the job again and keeps its view.

The command refuses, with the reason, a job it cannot show yet: several work offsets, a bit that
does not cut (a probe) or whose solid gives no outline, or G-code it does not read
([G-code](gcode.md), [limits](limits.md)).

The hand-off folder keeps the unmodified export as `posted.nc` and the simulator's input as
`program.nc`. The simulation copy replaces parentheses inside known tool/operation label
comments with brackets. For the official Makera posts, standalone `M851 S…` and `M852` blocks
become annotated comments, so external-output PWM does not change simulated spindle RPM.
Line counts stay the same. Motion and unknown commands are not removed. This does not repair
files exported separately with FreeCAD's Post Process command; correct malformed labels there.

The current Makera machine post also needs a numeric minimum spindle speed where FreeCAD 26.3
uses `None` for an unspecified toolhead limit. The add-on retains Makera's configured post minimum
in that case, without changing the machine file, job settings or a specified toolhead limit.

### Stock

From the Job's Stock settings:

- **Create Box** and **From Base**: a box.
- **Create Cylinder**: a cylinder about Z, or a bar along X (for 4-axis work).
- **Any other stock**: an existing solid (a casting, a part from an earlier setup, a hexagon or a
  tube), a box turned off the axes, a cylinder along Y: its solid goes to the simulator as a mesh
  (`stock.stl` beside the job file, its faces within 0.05 mm of the solid's).

### Machine

A 3-axis job can be shown on a machine: the simulator draws it round the stock, its moving parts
following the tool, with the stock in the middle of its bed. **M** shows or hides the machine (F
fits the whole machine while it shows), **D** shows or hides its dust shoe, and **V** sees through
its moving parts; the simulator remembers them. Nothing on the screen names these keys: **?** lists
them. Display only: the machine never cuts and is never checked for collisions.

- **Makera Carvera Air:** its table moves in Y and its spindle in X and Z (on the screen the stock
  stays still, so the frame moves with the tool in Y). A reference model from Makera's published
  sizes and photographs, not a factory model. Its dust shoe is drawn see-through; its hose, cable
  chain and tablet cradle are left out.
- **PrintNC V4:** the gantry moves in Y, the X carriage on it, the spindle in Z.

To change a job's machine, use **CAM > BearCAM simulator machine...**, then simulate again. A job
whose FreeCAD machine (the job's *Machine*, FreeCAD 1.2) names a Carvera or a PrintNC is offered
that machine first. Headless: `BEARCAM_MACHINE=carvera-air` (or `printnc-v4`).

### Tools

From each operation's tool controller, by the bit's shape:

| FreeCAD bit | Drawn as |
|---|---|
| endmill | flat end mill |
| ballend | ball end mill |
| bullnose | bull-nose end mill, with its corner radius |
| v-bit, chamfer | cone point with its angle and flat tip |
| drill (and spot drill) | cone point at its tip angle |
| reamer | flat end mill of its diameter |
| taperedballnose | tapered ball nose: the ball, the taper's angle up to its taper diameter |
| dovetail | dovetail cutter: its flank at the cutting edge angle, its neck and shank |
| tslotmill | T-slot cutter, with its neck and shank |
| thread-mill | single-tooth thread mill, with its neck and shank |
| a custom shape named *lollipop* | a ball on a narrower neck (Diameter, NeckDiameter, NeckLength, ShankDiameter) |
| a custom shape named *countersink* | a cone at its CuttingEdgeAngle (or TipAngle) |
| any other bit (radius, slitting saw, tap, custom shapes) | its own outline, measured from its solid |
| probe | refused: it does not cut |

A bit whose operation has a **Dragknife dressup** is a drag knife: the simulator cuts a 0.25 mm
kerf along the blade's path, which trails the holder's axis by the dressup's offset and swings
round as the path turns, so you can see whether the corner actions square the corners. A custom
shape named *dragknife* is one too (its BladeOffset).

Two different bits under one tool number are refused. When a program never changes tool itself
(GRBL's posts leave tool changes as comments, for a change by hand), each operation is drawn with
its own tool controller's bit.

## The simulator

**Start screen:** *Minimal mode* uses half the graphics memory and work, for cards with 2-4 GB
(ticked already when less than 3 GB is free). Then *Start* (or Enter).

**On screen:**

- The status line: the job, the engine, the move and its G-code line, and the speed.
- The **DRO** (left): the position in work coordinates (plus A and C on rotary programs), the
  tool, the feed, the spindle speed and direction, the G-code line, and the time so far out of
  the total.
- The **G-code pane** (left, under the DRO): the program, with the line being cut under a bar.
  Click a line to play from it; its moves light up yellow on the toolpath.
- The **timeline** (bottom): the job's operations as bands, as long as each takes. Click a band
  to go to that operation. Orange ticks mark tool changes.
- The **speed steps** (above the timeline): 0.1x, 0.5x, 1x, 2x, 4x, 8x, 16x and 32x. 1x is real
  time: the program's feeds, with rapids at the add-on's `RapidRate`.
- The **smoothness slider** (bottom right): how often the stock catches up with the cutter along
  a long move.
- The **Settings** button (top right, or P): see below.
- The **?** button (top right): every key and click.

The DRO and the G-code pane fold to their title bars with their buttons (or D and L).

**Settings** (the Settings button or P), remembered between runs:

- **Graphics memory:**
  - *Auto* (the default) uses up to 60 % of the graphics memory the driver reports free at start,
    at most 4 GB.
  - Or choose 1 to 24 GB, never more than the driver's free memory less 1 GB.
  - The volume's brick pool, which holds the stock near cut surfaces, is part of it.
- **Voxel size**, the volume's sample size:
  - *Auto fit* (the default) picks a size the job's cuts fit in.
  - Or choose 0.02 to 0.5 mm: finer looks better and needs more memory.
- **When the brick pool fills:**
  - *Restart coarser* (the default) starts the volume again at a 1.3x coarser voxel, replays to
    where it was, and says so in the status line.
  - *Stop* stops the volume with a message.

A memory or voxel change starts the engine again, which replays to where it was.

**Engines:** a job opens in the engine that suits it. That is the height field for 3-axis work
on a box, the rotary height field for 4-axis work on a bar, and the volume for the rest: a
cylinder or turned stock, 4-axis work on a box, 5-axis. E switches between the ones that can show
the job. The height field sees the stock from above only, so it cannot show the undercut that a
T-slot cutter, thread mill, dovetail or lollipop cuts: a job with one of those opens in the
volume.

## Keys and mouse

| Key or mouse | Does |
|---|---|
| Space | play / pause |
| Up / Down | the next speed step faster / slower (or click the steps) |
| Left / Right | one move back / on (with Shift: 1 % of the program) |
| Home / End | the start / the end |
| Timeline | click or drag to go anywhere; click a band to go to that operation |
| G-code pane | click a line to play from it; the wheel scrolls it |
| Left drag | turn the view round and tilt it up or down |
| Right drag | pan |
| Wheel | zoom |
| 3D mouse (SpaceMouse) | the view moves as the cap does: push it across, pull it toward you, tilt or twist it; its left button fits the view |
| F | fit the view to the stock (to the whole machine while one shows) |
| E | next engine |
| M | show / hide the machine (a job shown on one); machine view / part view (rotary programs) |
| D | show / hide the machine's dust shoe (a job on a machine with one) |
| T | toolpath on / off |
| G | cutter on / off |
| C | colours: by tool, recent cuts, by move order |
| A | exact surfaces / plain height field (comparison) |
| O | shading |
| S | how often the stock follows the cutter (as the slider) |
| D, L | fold the DRO (but see D above), the G-code pane |
| P | settings (as the Settings button) |
| I | hide all text (the picture and the timeline only) |
| H or ? | the help |
| Esc | close the settings or the help; otherwise quit |

The simulator remembers the speed step, the smoothness slider, minimal mode, the last view, the
folded panels and its settings between runs.

**3D mouse.** A 3Dconnexion SpaceMouse moves the view while the simulator's window is in front:
on Windows the simulator reads the device itself (raw HID input, beside 3DxWare), on Linux it
takes it from spacenavd (the daemon FreeCAD uses there). Two lines in the simulator's settings
file (`%APPDATA%\BearCAM\Simulator\settings.txt`, or `~/.config/bearcam-simulator/settings.txt`)
tune it: `spacemouse_speed=1` (0 turns it off) and `spacemouse_invert=` followed by any of
`x y z rx ry rz` for the axes that move the wrong way for you.
