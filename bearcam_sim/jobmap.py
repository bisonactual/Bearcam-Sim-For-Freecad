# The FreeCAD side of the hand-off: posts a CAM job with its post processor and describes it for
# the viewer in a job file (format "bearcam-sim-job", version 1: schema/job-v1.md). Runs with or
# without the GUI; anything the simulator cannot show yet is refused with the reason in words.
import json
import math
import os
import re

import FreeCAD

FORMAT = "bearcam-sim-job"
VERSION = 1


class SimError(Exception):
    """A job the simulator cannot show (yet), or a step that failed, with the reason in words."""


def value(obj, name, default=None):
    """A property as a number (a Quantity's value: mm, degrees), else default."""
    v = getattr(obj, name, None)
    if v is None:
        return default
    try:
        return float(getattr(v, "Value", v))
    except (TypeError, ValueError):
        return default


# ---- Jobs


def is_job(obj):
    return (all(hasattr(obj, p) for p in ("Operations", "Stock", "Tools"))
            and (hasattr(obj, "PostProcessor") or hasattr(obj, "Machine")))


def jobs_in(doc):
    return [o for o in doc.Objects if is_job(o)] if doc else []


def job_of(obj):
    """The job an object (an operation, a tool controller, the stock...) belongs to."""
    for parent in [obj] + list(getattr(obj, "InListRecursive", [])):
        if is_job(parent):
            return parent
    return None


def operations(job):
    """The job's active operations in order, each with its tool controller (a dressup's is its
    base operation's)."""
    out = []
    for op in job.Operations.Group:
        if getattr(op, "Active", True) is False:
            continue
        tc, base, seen = None, op, 0
        while base is not None and tc is None and seen < 20:
            tc = getattr(base, "ToolController", None)
            base = getattr(base, "Base", None)
            base = base if hasattr(base, "Path") else None
            seen += 1
        if not hasattr(op, "Path"):
            continue
        out.append((op, tc))
    return out


# ---- Posting


MAKERA_POSTS = {"makera_26_mch", "makera_legacy"}


def machine_post(job):
    """The configured machine's post takes precedence over legacy and remembered choices."""
    name = getattr(job, "Machine", "")
    if not name:
        return ""
    try:
        from Machine.models.machine import MachineFactory

        machine = MachineFactory.get_machine(name)
        post_name = getattr(machine, "postprocessor_file_name", "")
        if not post_name:
            raise SimError(f'The machine "{name}" names no post processor.')
        return post_name
    except SimError:
        raise
    except Exception as e:
        raise SimError(f'The machine "{name}" could not be loaded: {e}') from e


def post_job(job, post_name):
    """The job's G-code from the named post processor, as one program (split output joined in
    order). No editor or dialog opens: the post runs as if FreeCAD had no GUI."""
    from Path.Post.Processor import PostProcessorFactory

    configured = machine_post(job)
    post_name = configured or post_name
    gui = getattr(FreeCAD, "GuiUp", 0)
    try:
        FreeCAD.GuiUp = 0  # posts open their G-code editor only with the GUI up
        post = PostProcessorFactory.get_post_processor(job, post_name)
        method = "export2" if configured else "export"
        if not callable(getattr(post, method, None)):
            raise SimError(f'The post processor "{post_name}" was not found.')
        # Match FreeCAD's machine-post dialog: apply the stored machine settings and job
        # overrides once, then export without dialogs or the remote-upload hook.
        if configured:
            if callable(getattr(post, "apply_configuration_bundle", None)):
                post.apply_configuration_bundle()
                post._bundle_applied = True
            post._dialog_handled = True
            post.remote_post = lambda sections: None
            # The current Makera post compares RPM with this value without checking for
            # None. FreeCAD 26.3 uses None for an unspecified toolhead limit. Retain the
            # post's configured minimum in that case; never replace a real machine limit.
            if post_name.lower() == "makera_26_mch" and post.values.get("MIN_SPINDLE_SPEED") is None:
                minimum = post._machine.postprocessor_properties.get("min_spindle_speed")
                if minimum is not None:
                    post.values["MIN_SPINDLE_SPEED"] = minimum
        if hasattr(post, "values") and isinstance(post.values, dict):
            post.values["SHOW_EDITOR"] = False
        if hasattr(post, "script_module"):
            setattr(post.script_module, "SHOW_EDITOR", False)
        sections = getattr(post, method)()
    except SimError:
        raise
    except Exception as e:
        raise SimError(f'The post processor "{post_name}" stopped: {e}') from e
    finally:
        FreeCAD.GuiUp = gui
    if not sections:
        raise SimError(f'The post processor "{post_name}" gave no G-code (see the report view).')
    parts = [g for _, g in sections if g]
    if not parts:
        raise SimError(f'The post processor "{post_name}" gave no G-code (see the report view).')
    return "\n".join(p.rstrip("\n") for p in parts) + "\n"


# ---- Stock


def stock_kind(stock):
    """FromBase, CreateBox, CreateCylinder, or "" (an existing solid): the Stock settings' type,
    else the stock object's class (older files have no StockType)."""
    kind = getattr(stock, "StockType", "") or ""
    if kind in ("FromBase", "CreateBox", "CreateCylinder"):
        return kind
    proxy = type(getattr(stock, "Proxy", None)).__name__
    return {"StockFromBase": "FromBase", "StockCreateBox": "CreateBox", "StockCreateCylinder": "CreateCylinder"}.get(proxy, "")


STOCK_MESH = "stock.stl"


def stock_of(job):
    """The job's stock for the viewer, and the solid to send as a mesh (else None): FromBase and
    CreateBox give a box, CreateCylinder a cylinder about Z or a bar along X (by its axis). Any
    other stock (an existing solid, a box turned off the axes, a cylinder along Y or at an angle)
    goes as a mesh of its solid."""
    stock = job.Stock
    kind = stock_kind(stock)
    shape = stock.Shape
    bb = shape.BoundBox
    if kind in ("FromBase", "CreateBox"):
        box_volume = bb.XLength * bb.YLength * bb.ZLength
        if box_volume > 0 and abs(shape.Volume - box_volume) <= 1e-6 * box_volume:
            return {"kind": "box", "min": [bb.XMin, bb.YMin, bb.ZMin], "max": [bb.XMax, bb.YMax, bb.ZMax]}, None
    elif kind == "CreateCylinder":
        faces = [f for f in shape.Faces if type(f.Surface).__name__ == "Cylinder"]
        if len(faces) == 1:
            surf = faces[0].Surface
            axis, centre, radius = surf.Axis, surf.Center, surf.Radius
            if abs(abs(axis.z) - 1) < 1e-6:
                return {"kind": "cylinder", "axis": "z", "center": [centre.x, centre.y], "z": [bb.ZMin, bb.ZMax],
                        "radius": radius}, None
            if abs(abs(axis.x) - 1) < 1e-6:
                return {"kind": "bar", "axis": "x", "x": [bb.XMin, bb.XMax], "center": [centre.y, centre.z],
                        "radius": radius}, None
    if not shape.Solids:
        raise SimError("The stock is not a solid (a closed shape): choose a box, a cylinder or a solid in the Job's "
                       "Stock settings.")
    return {"kind": "mesh", "file": STOCK_MESH}, shape


def write_stock_mesh(shape, path):
    """The stock solid as an STL, its faces within 0.05 mm (finer on small stock) of the solid's."""
    import MeshPart

    deflection = min(0.05, max(0.005, shape.BoundBox.DiagonalLength * 1e-4))
    try:
        mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=deflection, AngularDeflection=0.1, Relative=False)
    except Exception as e:
        raise SimError(f"The stock solid could not be meshed for the simulator: {e}") from e
    if mesh.CountFacets < 4 or mesh.CountFacets > 4000000:
        raise SimError(f"The stock solid meshed to {mesh.CountFacets} triangles: the simulator takes 4 to 4 million.")
    tmp = path[:-4] + ".tmp.stl"  # the extension picks the format
    mesh.write(tmp)
    os.replace(tmp, path)


# ---- Tools


# FreeCAD's bit shapes (ShapeID, with FreeCAD's aliases and drill subtypes) and the viewer's
# cutters. A drill (or spot drill) is the viewer's cone-point cutter at its tip angle (owner,
# 22 Oct). Shapes FreeCAD does not ship (custom shapes) are known by name: lollipop,
# countersink, drag knife. Any other bit that cuts is measured: its solid's outline, from the
# tip up, sent as the viewer's profile cutter.
SHAPES = {
    "endmill": "flat",
    "ballend": "ball",
    "bullnose": "bull",
    "torus": "bull",
    "v-bit": "chamfer",
    "vbit": "chamfer",
    "v_bit": "chamfer",
    "chamfer": "chamfer",
    "drill": "drill",
    "jobber": "drill",
    "stub": "drill",
    "spot": "drill",
    "center": "drill",
    "brad_point": "drill",
    "tslotmill": "tslot",
    "thread-mill": "threadmill",
    "threadmill": "threadmill",
    "thread_mill": "threadmill",
    "dovetail": "dovetail",
    "reamer": "reamer",
    "taperedballnose": "taperball",
    "taperballnose": "taperball",
    "conicalballnose": "taperball",
    "lollipop": "lollipop",
    "countersink": "countersink",
    "dragknife": "dragknife",
    "drag-knife": "dragknife",
    "drag_knife": "dragknife",
}
NOT_CUTTING = ("probe",)
KERF = 0.25  # a drag knife's cut as drawn (mm), unless its bit is narrower
MAX_PROFILE_POINTS = 64  # the viewer's limit


def shape_id(bit):
    sid = getattr(bit, "ShapeID", "") or getattr(bit, "ShapeName", "") or ""
    if not sid:
        sid = os.path.splitext(os.path.basename(getattr(bit, "BitShape", "") or ""))[0]
    return str(sid).strip().lower()


def tslot_cone(bit, cut_top, shank_r):
    """How far up the T-slot cutter's neck widens to its shank, measured on the bit's own shape
    (FreeCAD's tslotmill draws a cone there); 0 when it cannot be measured."""
    try:
        shape = bit.Shape
        z0 = shape.BoundBox.ZMin

        def radius(z):
            wires = shape.slice(FreeCAD.Vector(0, 0, 1), z0 + z)
            return max((w.BoundBox.XLength / 2 for w in wires), default=0.0)

        lo, hi = cut_top, shape.BoundBox.ZLength - 1e-3
        if radius(hi) < shank_r - 0.01 or radius(lo) >= shank_r - 0.01:
            return 0.0
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            if radius(mid) >= shank_r - 0.01:
                hi = mid
            else:
                lo = mid
        return max(0.0, hi - cut_top)
    except Exception:
        return 0.0


def thinned(points, tolerance):
    """The polyline's points that keep it within `tolerance` of itself (Douglas-Peucker)."""
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    todo = [(0, len(points) - 1)]
    while todo:
        i0, i1 = todo.pop()
        (ar, az), (br, bz) = points[i0], points[i1]
        dr, dz = br - ar, bz - az
        length = (dr * dr + dz * dz) ** 0.5
        worst, at = 0.0, 0
        for i in range(i0 + 1, i1):
            r, z = points[i]
            if length > 0:
                t = max(0.0, min(1.0, ((r - ar) * dr + (z - az) * dz) / (length * length)))
                e = ((r - ar - t * dr) ** 2 + (z - az - t * dz) ** 2) ** 0.5
            else:
                e = ((r - ar) ** 2 + (z - az) ** 2) ** 0.5
            if e > worst:
                worst, at = e, i
        if worst > tolerance:
            keep[at] = True
            todo += [(i0, at), (at, i1)]
    return [p for p, k in zip(points, keep) if k]


def measured_profile(bit):
    """The bit's outline from its solid (FreeCAD stands it on its tip at the origin, about Z): the
    section through its axis, from the tip up its right side to the top, as (r, z) points with z
    never falling, within 2 um of the section. None when the solid gives no such outline."""
    try:
        shape = bit.Shape
        if shape is None or shape.isNull() or not shape.Solids:
            return None
        bb = shape.BoundBox
        wires = shape.slice(FreeCAD.Vector(0, 1, 0), 0.0)
        if len(wires) != 1:
            return None
        pts = [(p.x, p.z) for p in wires[0].discretize(Deflection=0.001)]
    except Exception:
        return None
    if len(pts) < 4:
        return None
    if pts[0] == pts[-1]:
        pts.pop()
    n = len(pts)
    # Where the section crosses the axis: the lowest crossing is the tip, the highest the top.
    crossings = []
    for i in range(n):
        (x0, z0), (x1, z1) = pts[i], pts[(i + 1) % n]
        if abs(x0) < 1e-7:
            crossings.append((z0, i))
        elif (x0 > 0) != (x1 > 0) and abs(x1) >= 1e-7:
            crossings.append((z0 + (z1 - z0) * x0 / (x0 - x1), i))
    if len(crossings) < 2:
        return None
    (z_tip, i_tip), (z_top, i_top) = min(crossings), max(crossings)
    if i_tip == i_top:
        return None
    # The two ways round from the tip to the top; the right side is the one at positive x.
    one = [pts[(i_tip + 1 + k) % n] for k in range((i_top - i_tip) % n)]
    other = [pts[(i_top + 1 + k) % n] for k in range((i_tip - i_top) % n)][::-1]
    side = max(one, other, key=lambda c: sum(x for x, _ in c) / max(len(c), 1))
    if not side or min(x for x, _ in side) < -1e-6:
        return None
    out = [(0.0, 0.0)]
    for x, z in side:
        z = max(z - z_tip, out[-1][1])  # z never falls (a hair of rounding aside)
        if x > 1e-7:
            out.append((x, z))
    if len(out) < 2 or z_top - bb.ZMin <= 0:
        return None
    tolerance = 0.002
    prof = thinned(out, tolerance)
    while len(prof) > MAX_PROFILE_POINTS:
        tolerance *= 1.5
        prof = thinned(out, tolerance)
    return [[round(r, 6), round(z, 6)] for r, z in prof]


def tool_of(tc, blade=None):
    """A tool controller's bit as the viewer's tool, or SimError naming the shape. `blade`: the
    blade offset when the operation is dressed as a drag knife's."""
    bit = tc.Tool
    number = int(tc.ToolNumber)
    sid = shape_id(bit)
    label = getattr(bit, "Label", "") or getattr(tc, "Label", "")
    if sid in NOT_CUTTING:
        raise SimError(f'T{number} "{label}" is a "{sid}" bit: it does not cut, so there is nothing to simulate.')
    kind = "dragknife" if blade is not None else SHAPES.get(sid)
    d = value(bit, "Diameter", 0.0)

    def measured(why=""):
        prof = measured_profile(bit)
        if prof is None:
            raise SimError(f'T{number} "{label}" is a "{sid or "unknown"}" bit{why}, and its solid gives no outline to '
                           "simulate (a solid turned about Z, on its tip).")
        t = {"number": number, "kind": "profile", "diameter": 2 * max(r for r, _ in prof), "profile": prof,
             "name": label}
        flute = value(bit, "CuttingEdgeHeight")
        if flute:
            t["flute_length"] = flute
        return t

    if kind is None:
        return measured()
    if kind == "dragknife":
        offset = blade if blade is not None else value(bit, "BladeOffset", value(bit, "Offset", 0.0))
        return {"number": number, "kind": "dragknife", "diameter": d if 0 < d < KERF else KERF,
                "blade_offset": max(0.0, offset or 0.0), "name": label}
    if not d or d <= 0:
        raise SimError(f'T{number} "{label}" has no diameter.')
    t = {"number": number, "kind": kind, "diameter": d, "name": label}
    flute = value(bit, "CuttingEdgeHeight")
    if flute:
        t["flute_length"] = flute
    if kind == "bull":
        corner = value(bit, "CornerRadius")
        if corner is None:
            flat = value(bit, "FlatRadius")
            corner = d / 2 - flat if flat is not None else None
        if corner is None:
            raise SimError(f'T{number} "{label}" (bullnose) has no corner radius.')
        t["corner_radius"] = corner
    elif kind in ("chamfer", "countersink"):
        t["angle"] = value(bit, "CuttingEdgeAngle", value(bit, "TipAngle", 90.0))
        t["tip_diameter"] = value(bit, "TipDiameter", 0.0)
    elif kind == "drill":
        t.update({"kind": "chamfer", "angle": value(bit, "TipAngle", 118.0), "tip_diameter": 0.0})
        t.pop("flute_length", None)
    elif kind == "taperball":
        # FreeCAD's TaperedBallNose: Diameter is the ball's; the taper widens to TaperDiameter.
        top = value(bit, "TaperDiameter", 0.0)
        if not top or top <= d:
            return measured(" without a taper diameter wider than its ball")
        t.update({"diameter": top, "angle": value(bit, "TaperAngle", 0.0), "tip_diameter": d})
    elif kind == "tslot":
        height = value(bit, "CuttingEdgeHeight", 0.0)
        neck_d, neck_len, shank_d = value(bit, "NeckDiameter", 0.0), value(bit, "NeckLength", 0.0), value(bit, "ShankDiameter", 0.0)
        t.update({"height": height, "neck_diameter": neck_d, "neck_length": neck_len, "shank_diameter": shank_d,
                  "cone": tslot_cone(bit, height + neck_len, shank_d / 2) if shank_d > neck_d else 0.0})
        t.pop("flute_length", None)
    elif kind == "threadmill":
        t.update({"angle": value(bit, "cuttingAngle", value(bit, "CuttingAngle", 60.0)), "crest": value(bit, "Crest", 0.0),
                  "neck_diameter": value(bit, "NeckDiameter", 0.0), "neck_length": value(bit, "NeckLength", 0.0),
                  "shank_diameter": value(bit, "ShankDiameter", 0.0)})
        t.pop("flute_length", None)
    elif kind == "dovetail":
        # FreeCAD's dovetail: Diameter at the tip, its flank at CuttingEdgeAngle to the bottom face up
        # to CuttingEdgeHeight, the neck (NeckHeight) measured from there.
        neck_d = value(bit, "NeckDiameter", 0.0)
        height = value(bit, "CuttingEdgeHeight", 0.0)
        if not neck_d or not height:
            return measured(" without a neck diameter and cutting height")
        t.update({"angle": value(bit, "CuttingEdgeAngle", 60.0), "height": height, "neck_diameter": neck_d,
                  "neck_length": value(bit, "NeckHeight", value(bit, "NeckLength", 0.0)),
                  "shank_diameter": value(bit, "ShankDiameter", 0.0)})
        t.pop("flute_length", None)
    elif kind == "lollipop":
        # A ball on a narrower neck; the neck's length is its reach from the tip.
        neck_d = value(bit, "NeckDiameter", 0.0)
        if not neck_d or neck_d >= d:
            return measured(" without a neck diameter narrower than its ball")
        t.update({"neck_diameter": neck_d, "neck_length": value(bit, "NeckLength", value(bit, "NeckHeight", 0.0)),
                  "shank_diameter": value(bit, "ShankDiameter", 0.0)})
        t.pop("flute_length", None)
    return t


def drag_knife_offset(op):
    """The blade offset when the operation is dressed for a drag knife (FreeCAD's Dragknife
    dressup: offset, pivotheight, filterAngle), on it or on a dressup under it; else None."""
    obj, seen = op, 0
    while obj is not None and seen < 20:
        if all(hasattr(obj, p) for p in ("offset", "pivotheight", "filterAngle")):
            return value(obj, "offset", 0.0)
        obj = getattr(obj, "Base", None)
        obj = obj if hasattr(obj, "Path") else None
        seen += 1
    return None


def tools_of(ops):
    """The tools the active operations use, one per T number (two different bits under one
    number are refused)."""
    # A tool controller any operation dresses for a drag knife is a drag knife's, in all its
    # operations (FreeCAD keeps the dressed operation in the job beside its dressup).
    blades = {}
    for op, tc in ops:
        offset = drag_knife_offset(op)
        if tc is not None and offset is not None:
            blades[tc.Name] = offset
    tools = {}
    for op, tc in ops:
        if tc is None:
            continue
        t = tool_of(tc, blades.get(tc.Name))
        old = tools.get(t["number"])
        if old is not None:
            same = {k: v for k, v in old.items() if k != "name"} == {k: v for k, v in t.items() if k != "name"}
            if not same:
                raise SimError(f'T{t["number"]} is two different bits in this job ("{old["name"]}" and "{t["name"]}"): '
                               "give them their own tool numbers.")
            continue
        tools[t["number"]] = t
    if not tools:
        raise SimError("The job has no active operation with a tool controller.")
    return [tools[n] for n in sorted(tools)]


# ---- The posted program


def comment_text(text):
    """Labels inside generated comments must not open or close a G-code comment."""
    return text.replace("(", "[").replace(")", "]")


def uncomment(line):
    """Read code outside balanced, possibly nested, parentheses and semicolon comments."""
    depth, out = 0, []
    for c in line:
        if c == ";" and not depth:
            break
        if c == "(":
            depth += 1
            out.append(" ")
        elif c == ")" and depth:
            depth -= 1
        elif not depth:
            out.append(c)
    return "".join(out)


def simulation_gcode(job, nc, post_name):
    """Adapt only known label comments and Makera auxiliary-only blocks, one line for one
    line. The original export is kept separately; motion and unknown commands stay strict."""
    labels = set()
    for op, tc in operations(job):
        for obj in (op, tc, getattr(tc, "Tool", None)):
            label = getattr(obj, "Label", "")
            if label and "\n" not in label and "\r" not in label:
                labels.add(label)
    comments = {}
    for label in labels:
        for prefix in ("", "Begin operation: ", "Finish operation: "):
            text = prefix + label
            comments[("(" + text + ")").casefold()] = "(" + comment_text(text) + ")"
    makera = post_name.lower() in MAKERA_POSTS
    word = re.compile(r"([A-Z])\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))", re.I)
    out = []
    for line_no, line in enumerate(nc.splitlines(keepends=True), 1):
        body = line.rstrip("\r\n")
        ending = line[len(body):]
        match = re.fullmatch(r"(\s*(?:N\d+\s*)?)(.*?)(\s*)", body, re.I)
        if match:
            before, text, after = match.groups()
            if text.casefold() in comments:
                body = before + comments[text.casefold()] + after
        if makera:
            code = uncomment(body).upper()
            words = [(letter, float(number)) for letter, number in word.findall(code)]
            aux = [v for letter, v in words if letter == "M" and v in (851, 852)]
            if aux:
                letters = [letter for letter, _ in words]
                valid = (not word.sub("", code).strip() and len(aux) == 1
                         and all(letter in "NMS" for letter in letters)
                         and all(letters.count(letter) <= 1 for letter in "NMS")
                         and ("N" not in letters or letters[0] == "N")
                         and all(math.isfinite(v) for _, v in words)
                         and all(0 <= v <= 100 for letter, v in words if letter == "S")
                         and (aux[0] == 851 or "S" not in letters))
                if not valid:
                    raise SimError(f"Line {line_no}: Makera M851/M852 is supported only as a separate "
                                   "auxiliary-control block (M851 with optional S0–100, or M852).")
                body = "; BearCAM simulation: Makera auxiliary output only | " + body
        out.append(body + ending)
    return "".join(out)


def code_lines(nc):
    """The program's lines without comments, upper case."""
    return [uncomment(line).upper() for line in nc.splitlines()]


def units_of(nc):
    for line in code_lines(nc):
        if re.search(r"G0*20(?![0-9.])", line):
            return "inch"
        if re.search(r"G0*21(?![0-9.])", line):
            return "mm"
    return "mm"


def has_a_axis(nc):
    return any(re.search(r"(?<![A-Z])A\s*[-+]?[0-9.]", line) for line in code_lines(nc))


def operation_lines(nc, ops):
    """Each operation's first line: a begin-operation marker, or a machine post's label."""
    lines = [re.sub(r"^\s*N\d+\s*", "", line, flags=re.I).strip().casefold()
             for line in nc.splitlines()]
    out, at = [], 0
    for op, tc in ops:
        first = 0
        label = op.Label.strip()
        for prefix in ("Begin operation: ", ""):
            wants = {("(" + prefix + name + ")").casefold() for name in (label, comment_text(label))}
            for i in range(at, len(lines)):
                if lines[i] in wants:
                    first, at = i + 1, i + 1
                    break
            if first:
                break
        entry = {"name": op.Label, "first_line": first}
        if tc is not None:
            entry["tool"] = int(tc.ToolNumber)
        out.append(entry)
    return out


# ---- The machine round the stock


# The machines the simulator can draw round a 3-axis job (its machines/ID.json), by id; "" for
# none. Shown as the router's frame, gantry and spindle, moving with the tool: display only.
MACHINES = [("", "None (the stock alone)"), ("carvera-air", "Makera Carvera Air"), ("printnc-v4", "PrintNC V4")]


def machine_label(machine_id):
    return dict(MACHINES).get(machine_id, machine_id)


def machine_guess(job):
    """The simulator's machine for a job whose FreeCAD machine (FreeCAD 1.2's Job.Machine) names
    one, else ""."""
    name = str(getattr(job, "Machine", "") or "").lower().replace(" ", "")
    if "carvera" in name:
        return "carvera-air"
    if "printnc" in name:
        return "printnc-v4"
    return ""


# ---- The hand-off


def safe_name(text):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")[:60] or "job"


def jobs_base():
    """The user's own folder for job hand-offs: FreeCAD's cache folder (else its data folder).
    Not the shared temporary folder, where on Linux another user could make bearcam-sim first and
    own what is written in it; on Linux it must be the user's and closed to others."""
    cache = getattr(FreeCAD, "getUserCachePath", None)
    root = cache() if cache else FreeCAD.getUserAppDataDir()
    path = os.path.join(root, "BearCAMSimulator", "jobs")
    os.makedirs(path, mode=0o700, exist_ok=True)
    if os.name == "posix":
        st = os.stat(path)
        if st.st_uid != os.getuid() or st.st_mode & 0o022:
            raise SimError(f"The job folder {path} is not yours alone (another owner, or others may write to it); "
                           "it was not used.")
    return path


def job_folder(doc, job, base=None):
    """Where a job's program and job file go: one folder per document and job, kept between runs
    so a re-post rewrites the files the viewer watches."""
    import hashlib

    base = base or jobs_base()
    tag = hashlib.sha1((doc.FileName or doc.Name).encode("utf-8")).hexdigest()[:6]  # documents may share a label
    return os.path.join(base, safe_name(doc.Label or doc.Name) + "-" + safe_name(job.Label or job.Name) + "-" + tag)


def write_atomic(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def job_text(data):
    """The job file's text: JSON, so no NaN or infinity (json.dumps writes them as NaN and Infinity,
    which JSON does not have); a document value that is one is refused."""
    try:
        return json.dumps(data, indent=2, allow_nan=False) + "\n"
    except ValueError as e:
        raise SimError("A stock or tool size in this job is not a finite number (NaN or infinity): check the "
                       "Job's stock and the tool bits' sizes.") from e


def prepare(job, post_name, rapid_mm_min=5000.0, folder=None, machine=""):
    """Posts the job and writes its program and job file, on `machine` (an id from MACHINES; ""
    for none). Returns (job file, a summary line)."""
    if machine not in dict(MACHINES):
        raise SimError(f'The simulator has no machine "{machine}" (it draws: '
                       f'{", ".join(m for m in dict(MACHINES) if m)}).')
    doc = job.Document
    fixtures = list(getattr(job, "Fixtures", []) or [])
    if len(fixtures) > 1:
        raise SimError(f"This job has several work offsets ({', '.join(fixtures)}): the simulator shows one setup per "
                       "job.")
    ops = operations(job)
    stock, stock_solid = stock_of(job)
    tools = tools_of(ops)
    post_name = machine_post(job) or post_name
    posted = post_job(job, post_name)
    nc = simulation_gcode(job, posted, post_name)
    folder = folder or job_folder(doc, job)
    os.makedirs(folder, exist_ok=True)
    nc_path = os.path.join(folder, "program.nc")
    job_path = os.path.join(folder, "job.json")
    if stock_solid is not None:
        write_stock_mesh(stock_solid, os.path.join(folder, STOCK_MESH))
    data = {
        "format": FORMAT,
        "version": VERSION,
        "name": f"{doc.Label}: {job.Label}",
        "nc": "program.nc",
        "units": units_of(nc),
        "rapid_mm_min": float(rapid_mm_min),
        "stock": stock,
        "tools": tools,
        "work_offset": {"name": fixtures[0] if fixtures else "", "origin": [0, 0, 0]},
        "rotary": {"axis": "A", "a_sign": -1} if has_a_axis(nc) else None,
        "operations": operation_lines(nc, ops),
        "source": {"document": doc.FileName, "job": job.Name, "post_processor": post_name,
                   "posted_nc": "posted.nc"},
    }
    on = ""
    if machine and data["rotary"]:
        on = f", without the {machine_label(machine)} (a machine is drawn round 3-axis jobs only)"
    elif machine:
        data["router"] = machine
        on = f", on the {machine_label(machine)}"
    text = job_text(data)
    # The program first, then the job file: the viewer reads both once they stand still.
    write_atomic(os.path.join(folder, "posted.nc"), posted)
    write_atomic(nc_path, nc)
    write_atomic(job_path, text)
    summary = (f"{doc.Label}: {job.Label} posted with {post_name}: {len(nc.splitlines())} lines, "
               f"{len(tools)} tools, {stock['kind']} stock{on} -> {job_path}")
    return job_path, summary
