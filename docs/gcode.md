# G-code the simulator reads

The simulator reads RS274 / LinuxCNC-style G-code, as FreeCAD's posts write it. It stops at any
code it does not know and says which: for example,

    program.nc, line 812: G84 (a tapping cycle) is not simulated (unusual codes are added on request)

It never skips a code silently. Ask for a code you need and it can be added.

## Read

| Codes | Notes |
|---|---|
| G0, G1 | rapid and feed moves |
| G2, G3 | arcs and helices, with I J K or R. In G17 they are exact; in G18 and G19 they are drawn as short lines |
| G4 P | dwell (counted in the play time) |
| G17, G18, G19 | planes |
| G20, G21 | inch, mm |
| G28, G28.1, G30, G30.1, G53 | read, but the simulation does not move on their lines |
| G40, G43 H, G49 | cutter compensation off, tool length offset (programs are to the tool tip) |
| G54 - G59.3 | work offsets: one per job (a program that switches to another is refused) |
| G61, G61.1, G64 | path control |
| G73, G81, G82, G83 | drilling cycles, with G98 / G99 and G80, made into their moves as LinuxCNC makes them: in G90 and G17, without L repeats |
| G80 | ends a run of cycles |
| G90, G91, G90.1, G91.1 | distance modes |
| G93, G94 | inverse-time and per-minute feeds |
| G97 | spindle in rpm |
| G98, G99 | cycle retract to the start height / to R |
| M0, M1, M2, M30 | stops and ends (reading goes on, as posts may join programs) |
| M3, M4, M5 | spindle forward, reverse, stop (shown in the DRO) |
| M6 T | tool change (T before or after M6); a T alone selects the tool |
| M7, M8, M9, M48 - M53 | coolant, overrides |
| M428, M429 | LinuxCNC tool-tip control on / off (5-axis machines) |
| M851, M852 | read and ignored (Makera's posts write them) |
| X Y Z, A (and C on a machine with a C table), I J K R, F S T, P Q, H D N | words |
| ( ), ; | comments; FreeCAD's `(Begin operation: NAME)` comments label the timeline |

## Refused

Among others: G84 and G74 (tapping), G85-G89 (boring cycles), G76 and G33 (threading cycles and
spindle-synchronised motion), G38.x (probing), G41 and G42 (cutter radius compensation), G10
(setting offsets or the tool table), G92 (coordinate offsets), G68 (rotation), G51 (scaling), G5
(splines), G7 / G8, G15 / G16, G95, G96; B, U, V, W and E words; O words (subprograms) and M98 /
M99; parameters and expressions (`#`, `[ ]`); a T number the job does not list.

A drilling cycle in G91, outside G17 or with L repeats is refused too.
