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
2. **Describe.** The stock, the tools, the work offset and the operations go into a job file next
   to the program ([the job file](../schema/job-v1.md)).
3. **Play.** The simulator opens in its own window. Change the job and click the command again: the
   open simulator reads the job again and keeps its view.

The command refuses, with the reason, a job it cannot show yet: several work offsets, stock from
an existing solid, a tool shape it does not draw, or G-code it does not read
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
- **An existing solid**: not supported yet.

### Tools

From each operation's tool controller, by the bit's shape:

| FreeCAD bit | Drawn as |
|---|---|
| endmill | flat end mill |
| ballend | ball end mill |
| bullnose | bull-nose end mill, with its corner radius |
| v-bit, chamfer | cone point with its angle and flat tip |
| drill (and spot drill) | cone point at its tip angle |
| tslotmill | T-slot cutter, with its neck and shank |
| thread-mill | single-tooth thread mill, with its neck and shank |

Other shapes are refused by name. Two different bits under one tool number are refused. When a
program never changes tool itself (GRBL's posts leave tool changes as comments, for a change by
hand), each operation is drawn with its own tool controller's bit.

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
T-slot cutter or thread mill cuts: switch to the volume (E) to see them.

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
| F | fit the view to the stock |
| E | next engine |
| M | machine view / part view (rotary programs) |
| T | toolpath on / off |
| G | cutter on / off |
| C | colours: by tool, recent cuts, by move order |
| A | exact surfaces / plain height field (comparison) |
| O | shading |
| S | how often the stock follows the cutter (as the slider) |
| D, L | fold the DRO, the G-code pane |
| P | settings (as the Settings button) |
| I | hide all text (the picture and the timeline only) |
| H or ? | the help |
| Esc | close the settings or the help; otherwise quit |

The simulator remembers the speed step, the smoothness slider, minimal mode, the last view, the
folded panels and its settings between runs.
