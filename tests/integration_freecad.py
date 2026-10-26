"""Real FreeCAD + released simulator check, using a disposable document.

Run with FreeCAD's bundled Python (no GUI needed):
  python -B tests/integration_freecad.py --posts PATH --viewer PATH --out PATH
--posts contains the official Makera_Air.fcm and makera_*_post.py files.
"""
import FreeCAD as App

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path as FilePath

root = FilePath(App.getHomePath())
sys.path.extend(str(p) for p in (root / "Mod").iterdir() if p.is_dir())
sys.path.insert(0, str(FilePath(__file__).resolve().parents[1]))

import Part
import Path
import Path.Main.Job as Job
import Path.Op.Profile as Profile
from Machine.models.machine import MachineFactory
from bearcam_sim import jobmap


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--posts", required=True)
    parser.add_argument("--viewer", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    Path.Preferences.addAddonPostPath(args.posts)
    MachineFactory.register_addon_machine_dir(args.posts, "BearCAM test")
    out = FilePath(args.out)
    out.mkdir(parents=True, exist_ok=True)
    doc = App.newDocument("BearCAMPostingTest")
    results = []
    try:
        box = doc.addObject("Part::Box", "Block")
        box.Length, box.Width, box.Height = 20, 20, 5
        doc.recompute()
        job = Job.Create("Job", [box], None)
        tc = job.Tools.Group[0]
        tc.SpindleSpeed = 12000
        tc.HorizFeed, tc.VertFeed = "600 mm/min", "200 mm/min"
        tc.ToolNumber = 1
        tc.Label = 'TC Mill: 1/8"3.175mm) Short, 1/4" shank'
        tc.touch()
        op = Profile.Create("Profile", parentJob=job)
        op.ToolController = tc
        op.CoolantMode = "Mist"
        doc.recompute()
        assert len(op.Path.Commands) > 0 and "Invalid" not in op.State

        for case, machine, chosen, pwm in (
                ("machine", "Makera Air", "stale_remembered_post", 100),
                ("machine_override", "Makera Air", "linuxcnc_legacy", 35),
                ("makera_legacy", "", "makera_legacy", None),
                ("linuxcnc_legacy", "", "linuxcnc_legacy", None)):
            job.Machine = machine
            job.PostProcessorArgs = "--no-show-editor" if not machine else ""
            # No minimum-speed workaround in the test job: the add-on must retain the
            # Makera post's own configured minimum when the machine has no toolhead limit.
            job.PostProcessorPropertyOverrides = json.dumps(
                {"ext_for_air": True, "ext_port_percent": pwm}) if machine else "{}"
            before = (job.Machine, job.PostProcessorArgs, job.PostProcessorPropertyOverrides,
                      tc.Label, tc.Path.toGCode(), op.Path.toGCode(), App.GuiUp)
            jobfile, summary = jobmap.prepare(job, chosen, folder=str(out / case))
            after = (job.Machine, job.PostProcessorArgs, job.PostProcessorPropertyOverrides,
                     tc.Label, tc.Path.toGCode(), op.Path.toGCode(), App.GuiUp)
            assert before == after, "Posting changed the document or GUI state"
            data = json.loads(FilePath(jobfile).read_text(encoding="utf-8"))
            raw = (out / case / "posted.nc").read_text(encoding="utf-8")
            sim = (out / case / "program.nc").read_text(encoding="utf-8")
            assert len(raw.splitlines()) == len(sim.splitlines())
            assert data["operations"][0]["first_line"] > 0
            if machine:
                assert data["source"]["post_processor"] == "makera_26_MCH"
                assert re.search(r"M851 S" + str(pwm) + r"(?:\.0)?\b", raw)
                assert "M852" in raw and "G43" not in raw
                assert "M851" not in "\n".join(jobmap.code_lines(sim))
            run = subprocess.run([args.viewer, jobfile, "--read-dump"],
                                 capture_output=True, text=True, timeout=20)
            assert run.returncode == 0, run.stdout + run.stderr
            speeds = re.findall(r"\bS ([0-9.]+)", run.stdout)
            assert speeds and all(float(s) == 12000 for s in speeds), run.stdout
            result = {"case": case, "lines": len(sim.splitlines()), "summary": summary,
                      "exit_code": run.returncode, "readback": run.stdout}
            results.append(result)
            print("PASS", case, len(speeds), "moves, spindle stays at 12000 RPM", flush=True)
    finally:
        App.closeDocument(doc.Name)
    (out / "results.json").write_text(json.dumps({"freecad": App.Version(), "results": results},
                                               indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
