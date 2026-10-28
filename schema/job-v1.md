# The simulator's job file, version 1

The add-on writes a job file next to the simulation program and opens it in the viewer:
`stockviewer job.json`. The viewer reads the job file again whenever it or its program changes
(a re-post), keeping the camera. The machine-readable form is `job-v1.schema.json`.
`posted.nc` retains the unmodified export; `program.nc` contains the documented simulation-only
adaptations, with the same physical line numbers. `source.posted_nc` names the original export.

All lengths are millimetres and all angles degrees, whatever the program's units. Coordinates are
the program's: FreeCAD's posts write the document's coordinates, so the stock comes from the
document as it is.

```json
{
  "format": "bearcam-sim-job",
  "version": 1,
  "name": "Bracket: Job",
  "nc": "program.nc",
  "units": "mm",
  "rapid_mm_min": 5000,
  "stock": {"kind": "cylinder", "axis": "z", "center": [0, 0], "z": [-30, 0], "radius": 15},
  "tools": [
    {"number": 1, "kind": "flat", "diameter": 6, "flute_length": 20, "name": "6 mm end mill"},
    {"number": 2, "kind": "tslot", "diameter": 8, "height": 2, "neck_diameter": 3, "neck_length": 10,
     "shank_diameter": 6, "cone": 5, "name": "T-slot 8 x 2"}
  ],
  "work_offset": {"name": "G54", "origin": [0, 0, 0]},
  "rotary": null,
  "operations": [{"name": "Profile", "first_line": 22, "tool": 1}, {"name": "Groove", "first_line": 140, "tool": 2}],
  "source": {"document": "C:/.../Bracket.FCStd", "job": "Job", "post_processor": "linuxcnc"}
}
```

| Field | Meaning |
|---|---|
| `format`, `version` | `"bearcam-sim-job"` and `1`. The viewer refuses anything else. |
| `name` | Shown in the window title and the status line. |
| `nc` | The posted program, absolute or relative to the job file. |
| `units` | `"mm"` or `"inch"`: the units the program starts in (its own G20 / G21 still count) and the DRO's units. |
| `rapid_mm_min` | Rapids play at this rate at 1x (default 5000); feed moves play at the program's F. |
| `stock` | One of the shapes below. |
| `tools` | Every tool the program calls, by T number (the viewer refuses a T word that is not here). |
| `work_offset` | `name`: the work offset the job uses (for the DRO). `origin`: the work zero in the stock's coordinates (default 0, as FreeCAD posts). |
| `rotary` | `null`, or `{"axis": "A", "a_sign": -1}` for a 4-axis program on a bar: the part turns by `a_sign` x A about +X (an ISO table: -1). |
| `machine` | Optional: rotary tables in the viewer's machine format (`{"name": ..., "rotary": [{"axis": "A", "about": "X", "sign": 1, "pivot": [x, y, z]}, ...]}`), for A/C programs. |
| `operations` | In program order: `name`, `first_line` (the program's line, from 1, where it starts; 0 if unknown) and `tool` (T number). They label the timeline. When the program never changes tool itself (GRBL's posts leave M6 in a comment), each operation is cut with its `tool`. |
| `engine` | Optional: `"hf"`, `"rhf"` or `"vol"` to open in that engine when it can show the job. |
| `router` | Optional: a machine to draw round a 3-axis job, by id: `"carvera-air"` (Makera Carvera Air) or `"printnc-v4"` (PrintNC V4), from the viewer's own `machines/ID.json`. Its frame, gantry or table and spindle move with the tool; the stock sits on its bed. Display only: never cut, never checked. Ignored for 4- and 5-axis jobs. |
| `voxel` | Optional: the volume's sample size (mm); by default from the stock's size. |
| `source` | Where the job came from (for people; the viewer ignores it). |

## Stock

| `kind` | Fields |
|---|---|
| `box` | `min`, `max`: corners `[x, y, z]`. |
| `cylinder` | About Z: `axis: "z"`, `center: [x, y]`, `z: [bottom, top]`, `radius`. |
| `bar` | Along X, for 4-axis work: `axis: "x"`, `x: [left, right]`, `center: [y, z]`, `radius`. In a program with A motion its axis must be the A axis (`center` 0, 0). |
| `revolved` | A turned blank about Z: `axis: "z"`, `profile: [[r, z], ...]` (3 to 32 points, in order), `center: [x, y]`. |
| `mesh` | Any other shape: `file`, a closed STL (binary or ASCII, at most 4 million triangles) relative to the job file, in the program's coordinates as a box's corners are. The add-on writes the stock solid as `stock.stl`. The viewer refuses a mesh that is not closed, that encloses nothing, or that would take too long to sample (copies of its triangles piled up). |

## Tools

Every tool has `number` (its T number), `kind`, `diameter`, and optionally `name` (shown in the
DRO) and `flute_length` (how much of it is drawn as cutting edge).

| `kind` | More fields | FreeCAD's bit (ShapeID) |
|---|---|---|
| `flat` | | endmill |
| `reamer` | (cut as `flat`) | reamer |
| `ball` | | ballend |
| `bull` | `corner_radius` | bullnose |
| `chamfer` (or `vbit`) | `angle` (included), `tip_diameter` | v-bit, chamfer; drill (its tip angle, no flat) |
| `taper`, `countersink` | as `chamfer`: `diameter` at the top, `angle` (included), `tip_diameter` | a custom *countersink* |
| `taperball` | `angle` (included), `tip_diameter` (the ball's); `diameter` at the top of the taper | taperedballnose |
| `tslot` | `height` (cutting), `neck_diameter`, `neck_length`, `shank_diameter`, `cone` (the neck widening to the shank) | tslotmill |
| `threadmill` | `angle` (the tooth's), `crest`, `neck_diameter`, `neck_length`, `shank_diameter` | thread-mill |
| `dovetail` | `diameter` at the tip, `angle` (the flank's to the bottom face), `height` (cutting), `neck_diameter`, `neck_length` (from the top of the cutting height), `shank_diameter` | dovetail |
| `lollipop` | `diameter` (the ball's), `neck_diameter`, `neck_length` (its reach, from the tip), `shank_diameter` | a custom *lollipop* |
| `profile` | `profile`: the outline from the tip, `[[r, z], ...]` (2 to 64 points, z never falling; the last radius goes on up); `diameter` is ignored | any other bit, measured from its solid |
| `dragknife` | `diameter` (the kerf drawn), `blade_offset` (how far the blade's tip trails the holder's axis) | a bit whose operation has a Dragknife dressup; a custom *dragknife* |

A drag knife's blade swings to follow the path while its tip is in the stock (below its top): its
tip is pulled straight toward the axis, as a trailer follows its car, so uncompensated corners
come out rounded. The simulator cuts along the blade tip's path.

## Engines

The viewer opens a job in the height field for 3-axis work on a box or a mesh, the rotary height
field on a bar, and the volume for the rest (a cylinder or turned stock, 4-axis on a box, A/C
machines). A job with an undercut cutter (T-slot, thread mill, dovetail, lollipop, or a profile
that narrows going up) opens in the volume, which shows the undercut. E switches between the ones
that can show it.
