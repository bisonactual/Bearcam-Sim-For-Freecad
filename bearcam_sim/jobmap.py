# The FreeCAD side of the hand-off: posts a CAM job with its post processor and describes it for
# the viewer in a job file (format "bearcam-sim-job", version 1: schema/job-v1.md). Runs with or
# without the GUI; anything the simulator cannot show yet is refused with the reason in words.
import json
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
    return all(hasattr(obj, p) for p in ("Operations", "Stock", "Tools", "PostProcessor"))


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


def post_job(job, post_name):
    """The job's G-code from the named post processor, as one program (split output joined in
    order). No editor or dialog opens: the post runs as if FreeCAD had no GUI."""
    from Path.Post.Processor import PostProcessorFactory

    gui = getattr(FreeCAD, "GuiUp", 0)
    try:
        FreeCAD.GuiUp = 0  # posts open their G-code editor only with the GUI up
        post = PostProcessorFactory.get_post_processor(job, post_name)
        if post is None:
            raise SimError(f'The post processor "{post_name}" was not found.')
        if hasattr(post, "values") and isinstance(post.values, dict):
            post.values["SHOW_EDITOR"] = False
        if hasattr(post, "script_module"):
            setattr(post.script_module, "SHOW_EDITOR", False)
        sections = post.export()
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


def stock_of(job):
    """The job's stock for the viewer: FromBase and CreateBox give a box, CreateCylinder a
    cylinder about Z or a bar along X (by its axis). An existing solid is not supported yet."""
    stock = job.Stock
    kind = stock_kind(stock)
    shape = stock.Shape
    bb = shape.BoundBox
    if kind in ("FromBase", "CreateBox"):
        box_volume = bb.XLength * bb.YLength * bb.ZLength
        if box_volume <= 0 or abs(shape.Volume - box_volume) > 1e-6 * box_volume:
            raise SimError("The stock box is turned off the X, Y and Z axes: not supported yet.")
        return {"kind": "box", "min": [bb.XMin, bb.YMin, bb.ZMin], "max": [bb.XMax, bb.YMax, bb.ZMax]}
    if kind == "CreateCylinder":
        faces = [f for f in shape.Faces if type(f.Surface).__name__ == "Cylinder"]
        if len(faces) != 1:
            raise SimError("The cylinder stock's shape is not a plain cylinder: not supported yet.")
        surf = faces[0].Surface
        axis, centre, radius = surf.Axis, surf.Center, surf.Radius
        if abs(abs(axis.z) - 1) < 1e-6:
            return {"kind": "cylinder", "axis": "z", "center": [centre.x, centre.y], "z": [bb.ZMin, bb.ZMax],
                    "radius": radius}
        if abs(abs(axis.x) - 1) < 1e-6:
            return {"kind": "bar", "axis": "x", "x": [bb.XMin, bb.XMax], "center": [centre.y, centre.z],
                    "radius": radius}
        raise SimError("The cylinder stock lies along Y or at an angle: only Z (a cylinder) and X (a bar) are "
                       "supported yet.")
    raise SimError("Stock from an existing solid is not supported yet: choose a box or a cylinder in the Job's "
                   "Stock settings.")


# ---- Tools


# FreeCAD's bit shapes (ShapeID) and the viewer's cutters. A drill (or spot drill) is the
# viewer's cone-point cutter at its tip angle (owner, 22 Oct).
SHAPES = {
    "endmill": "flat",
    "ballend": "ball",
    "bullnose": "bull",
    "v-bit": "chamfer",
    "vbit": "chamfer",
    "chamfer": "chamfer",
    "drill": "drill",
    "tslotmill": "tslot",
    "thread-mill": "threadmill",
    "threadmill": "threadmill",
}


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


def tool_of(tc):
    """A tool controller's bit as the viewer's tool, or SimError naming the shape."""
    bit = tc.Tool
    number = int(tc.ToolNumber)
    sid = shape_id(bit)
    kind = SHAPES.get(sid)
    label = getattr(bit, "Label", "") or getattr(tc, "Label", "")
    if kind is None:
        known = "endmill, ballend, bullnose, v-bit, chamfer, drill, tslotmill, thread-mill"
        raise SimError(f'T{number} "{label}" is a "{sid or "unknown"}" bit: the simulator draws {known} so far.')
    d = value(bit, "Diameter", 0.0)
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
    elif kind == "chamfer":
        t["angle"] = value(bit, "CuttingEdgeAngle", 90.0)
        t["tip_diameter"] = value(bit, "TipDiameter", 0.0)
    elif kind == "drill":
        t.update({"kind": "chamfer", "angle": value(bit, "TipAngle", 118.0), "tip_diameter": 0.0})
        t.pop("flute_length", None)
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
    return t


def tools_of(ops):
    """The tools the active operations use, one per T number (two different bits under one
    number are refused)."""
    tools = {}
    for op, tc in ops:
        if tc is None:
            continue
        t = tool_of(tc)
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


def code_lines(nc):
    """The program's lines without comments, upper case."""
    out = []
    for line in nc.splitlines():
        line = re.sub(r"\([^)]*\)", "", line).split(";")[0]
        out.append(line.upper())
    return out


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
    """Each operation's first line: its "(Begin operation: LABEL)" comment, found in order."""
    lines = nc.splitlines()
    out, at = [], 0
    for op, tc in ops:
        want = "(begin operation: " + op.Label.strip().lower() + ")"
        first = 0
        for i in range(at, len(lines)):
            if lines[i].strip().lower().replace("  ", " ") == want:
                first, at = i + 1, i + 1
                break
        entry = {"name": op.Label, "first_line": first}
        if tc is not None:
            entry["tool"] = int(tc.ToolNumber)
        out.append(entry)
    return out


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


def prepare(job, post_name, rapid_mm_min=5000.0, folder=None):
    """Posts the job and writes its program and job file. Returns (job file, a summary line)."""
    doc = job.Document
    fixtures = list(getattr(job, "Fixtures", []) or [])
    if len(fixtures) > 1:
        raise SimError(f"This job has several work offsets ({', '.join(fixtures)}): the simulator shows one setup per "
                       "job.")
    ops = operations(job)
    stock = stock_of(job)
    tools = tools_of(ops)
    nc = post_job(job, post_name)
    folder = folder or job_folder(doc, job)
    os.makedirs(folder, exist_ok=True)
    nc_path = os.path.join(folder, "program.nc")
    job_path = os.path.join(folder, "job.json")
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
        "source": {"document": doc.FileName, "job": job.Name, "post_processor": post_name},
    }
    text = job_text(data)
    # The program first, then the job file: the viewer reads both once they stand still.
    write_atomic(nc_path, nc)
    write_atomic(job_path, text)
    summary = (f"{doc.Label}: {job.Label} posted with {post_name}: {len(nc.splitlines())} lines, "
               f"{len(tools)} tools, {stock['kind']} stock -> {job_path}")
    return job_path, summary
