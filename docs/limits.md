# Known limits (v0.6 Public Alpha)

## Platforms

- **macOS is not supported for now.** Its OpenGL stops at 4.1; the simulator needs 4.5 or 4.6.
- **Linux is not yet proved on real hardware.** The Linux simulator builds and runs (glibc 2.35 or
  newer, X11 or XWayland), but so far it has only run in a virtual machine's graphics layer, where
  it is slow. Reports from real Linux machines are welcome.
- **FreeCAD from Flatpak or Snap** runs in a sandbox, which may stop the add-on from starting a
  program it downloaded. Point the add-on at a simulator you unpacked yourself (`LocalViewerFolder`)
  if it does, or use FreeCAD's AppImage or distribution package.
- **Windows** may warn about an unknown publisher the first time the simulator starts, until its
  releases are signed.

## Jobs

- One setup per job: a job with several work offsets is refused.
- Stock that is not a box or a cylinder about Z (or a bar along X) goes to the simulator as a
  mesh of its solid: its uncut faces are drawn within about a tenth of a millimetre on a stock up
  to 300 mm across (the simulator samples the mesh on a grid of up to 8 million points), and its
  sharp edges a little rounded.
- 4-axis programs are taken to turn the part by -A about +X (an ISO A table) on a bar whose axis is
  the A axis. 5-axis programs need a machine description in the job file, which the add-on does
  not write yet.
- Rapids play at one rate (`RapidRate`, default 5000 mm/min; rotary rapids at 7200 degrees a
  minute), not at the machine's.

## The simulation

- It is a visual aid, not a guarantee: it does not check the machine's limits, fixtures, clamps,
  tool holders or tool lengths, and it gives no warnings. Prove every program on the machine.
- The height field (the 3-axis engine) sees the stock from above only: undercuts from T-slot
  cutters, thread mills, dovetails and lollipops show in the volume, where such a job opens.
- A drag knife is drawn as a 0.25 mm kerf along its blade's path; the blade swings only while its
  tip is below the stock's top (in the material).
- The 3D mouse is read by the simulator itself and has not yet been tried on every 3Dconnexion
  model: if an axis moves the wrong way, set `spacemouse_invert` (see [using it](use.md)).
- G18 and G19 arcs are drawn as short lines.
- After a re-post the simulator plays from the start again, and its window title keeps the first
  job's name.
