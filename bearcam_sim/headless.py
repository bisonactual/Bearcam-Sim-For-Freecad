# The hand-off without the GUI, for testing (FreeCAD's command-line program):
#   set BEARCAM_DOC=path\to\cam.FCStd           the document
#   set BEARCAM_JOB=Job                         a job's name or label; "*" (default) for every job
#   set BEARCAM_POST=linuxcnc                   the post for jobs that name none (else they are refused)
#   set BEARCAM_POST_FORCE=linuxcnc             a post for every job, instead of the job's own
#   set BEARCAM_OUT=folder                      where each job's folder goes (default: FreeCAD's cache folder)
#   set BEARCAM_VIEWER=folder                   with BEARCAM_LAUNCH=1, the viewer to open each job in
#   freecadcmd path\to\bearcam_sim\headless.py
# Prints one line per job: what was written, or why it was refused.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import FreeCAD  # noqa: E402

from bearcam_sim import jobmap, viewer  # noqa: E402


def main():
    doc = FreeCAD.openDocument(os.environ["BEARCAM_DOC"])
    want = os.environ.get("BEARCAM_JOB", "*")
    out = os.environ.get("BEARCAM_OUT") or None
    fallback = os.environ.get("BEARCAM_POST", "")
    lines = []
    for job in jobmap.jobs_in(doc):
        if want != "*" and want not in (job.Name, job.Label):
            continue
        post = os.environ.get("BEARCAM_POST_FORCE") or job.PostProcessor or fallback
        try:
            if not post:
                raise jobmap.SimError(f'The job "{job.Label}" names no post processor (set BEARCAM_POST).')
            folder = jobmap.job_folder(doc, job, out) if out else None
            path, summary = jobmap.prepare(job, post, float(os.environ.get("BEARCAM_RAPID", "5000")), folder)
            lines.append("OK " + summary)
            if os.environ.get("BEARCAM_LAUNCH") == "1":
                exe = viewer.find(os.environ.get("BEARCAM_VIEWER", ""), FreeCAD.getUserAppDataDir())
                pid, started = viewer.launch(exe, path)
                lines.append(f"   viewer pid {pid} ({'started' if started else 'already open'})")
        except jobmap.SimError as e:
            lines.append(f"REFUSED {doc.Label}: {job.Label}: {e}")
    text = "\n".join(lines) + "\n"
    sys.stdout.write(text)
    report = os.environ.get("BEARCAM_REPORT")
    if report:
        with open(report, "a", encoding="utf-8") as f:
            f.write(text)


main()
