"""Drives the BearCAM Simulator add-on in FreeCAD's GUI as a user would: the add-on loads, its two
commands sit in the CAM menu (and Simulate on the Project Setup toolbar), Simulate in BearCAM asks
for the post and the machine, writes the job and opens the viewer, the machine command changes the
machine, a second Simulate re-posts to the open viewer, a drag-knife job on no machine. Dialogs are
answered and message boxes recorded through the add-on's own QtGui (a stand-in), so nothing waits.
Run: FreeCAD.exe -u TEMP_USER_CFG gui_test.py, with BEARCAM_GUITEST_OUT, BEARCAM_GUITEST_DOC and
BEARCAM_GUITEST_VIEWER set."""
import json
import os
import traceback

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui

OUT = os.environ["BEARCAM_GUITEST_OUT"]
DOC = os.environ["BEARCAM_GUITEST_DOC"]
VIEWER = os.environ["BEARCAM_GUITEST_VIEWER"]  # the folder holding stockviewer
log = {"version": ".".join(FreeCAD.Version()[:3]), "steps": [], "dialogs": [], "messages": [], "launched": []}


def step(name, ok, detail=""):
    log["steps"].append({"step": name, "ok": bool(ok), "detail": detail if isinstance(detail, (list, dict)) else str(detail)})


def menu_texts(title):
    for m in FreeCADGui.getMainWindow().menuBar().actions():
        if m.text().replace("&", "") == title and m.menu():
            return [a.text().replace("&", "") for a in m.menu().actions() if a.text()]
    return None


def toolbar_texts(name):
    for tb in FreeCADGui.getMainWindow().findChildren(QtGui.QToolBar):
        if name in (tb.objectName(), tb.windowTitle()):
            return [a.text() for a in tb.actions() if a.text()]
    return None


answers = {}


class Dialogs:
    @staticmethod
    def getItem(parent, title, label, items, current=0, editable=True, *a, **k):
        items = list(items)
        kind = "post" if "post processor" in label else "machine" if "machine" in label else "job"
        log["dialogs"].append({"kind": kind, "items": items, "preselected": items[current] if items else None})
        answer = answers.pop(kind, None)
        return (answer or "", answer is not None)


class Boxes:
    Ok = QtGui.QMessageBox.Ok

    @staticmethod
    def _record(kind, args):
        log["messages"].append([kind, str(args[2]) if len(args) > 2 else ""])
        return QtGui.QMessageBox.Ok

    warning = staticmethod(lambda *a, **k: Boxes._record("warning", a))
    critical = staticmethod(lambda *a, **k: Boxes._record("critical", a))
    information = staticmethod(lambda *a, **k: Boxes._record("information", a))
    question = staticmethod(lambda *a, **k: Boxes._record("question", a))


class StandIn:
    """The add-on's QtGui with its dialogs answered: everything else is the real module."""

    def __getattr__(self, name):
        return {"QInputDialog": Dialogs, "QMessageBox": Boxes}.get(name) or getattr(QtGui, name)


def simulate(doc, job, label):
    import bearcam_sim.jobmap as jobmap
    import bearcam_sim.viewer as viewer

    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(job)
    n_dialogs, n_messages = len(log["dialogs"]), len(log["messages"])
    FreeCADGui.runCommand("BearCAM_Simulate")
    QtGui.QApplication.processEvents()
    folder = jobmap.job_folder(doc, job)
    path = os.path.join(folder, "job.json")
    data = json.load(open(path, encoding="utf-8")) if os.path.isfile(path) else None
    pid = viewer.running_pid(folder)
    if pid and pid not in log["launched"]:
        log["launched"].append(pid)
    result = {"dialogs": [d["kind"] for d in log["dialogs"][n_dialogs:]], "messages": log["messages"][n_messages:],
              "job_file": path if data else None, "viewer_pid": pid}
    if data:
        result.update({"router": data.get("router"), "stock": data["stock"]["kind"],
                       "tools": [t["kind"] for t in data["tools"]], "mtime": os.path.getmtime(path)})
    step(label, data is not None and pid != 0 and not result["messages"], result)
    return result


def run():
    try:
        import bearcam_sim
        import bearcam_sim.gui as gui
        import bearcam_sim.prefs as prefs

        step("add-on loaded", True, os.path.dirname(bearcam_sim.__file__))
        cmds = FreeCADGui.listCommands()
        step("both commands registered", "BearCAM_Simulate" in cmds and "BearCAM_SimulatorMachine" in cmds)
        prefs.set_local_folder(VIEWER)  # in the temporary user.cfg
        gui.QtGui = StandIn()
        doc = FreeCAD.openDocument(DOC)
        FreeCADGui.activateWorkbench("CAMWorkbench")
        for _ in range(20):
            QtGui.QApplication.processEvents()
        cam = menu_texts("CAM") or []
        at = cam.index("Simulate in BearCAM") if "Simulate in BearCAM" in cam else -1
        step("CAM menu has both commands", at >= 0 and "BearCAM simulator machine..." in cam,
             cam[max(0, at - 2):at + 3] if at >= 0 else cam)
        tb = toolbar_texts("Project Setup")
        step("Project Setup toolbar has Simulate", bool(tb) and "Simulate in BearCAM" in tb, tb)

        job, job1 = doc.getObject("Job"), doc.getObject("Job001")
        answers.update({"post": "linuxcnc", "machine": "Makera Carvera Air"})
        first = simulate(doc, job, "Job: first Simulate (asks post and machine; Carvera Air)")
        machine_dialog = [d for d in log["dialogs"] if d["kind"] == "machine"]
        step("machine dialog offers None, Carvera Air, PrintNC", bool(machine_dialog) and machine_dialog[-1]["items"] ==
             ["None (the stock alone)", "Makera Carvera Air", "PrintNC V4"], machine_dialog[-1] if machine_dialog else None)
        step("Job file on the Carvera Air", first.get("router") == "carvera-air" and first.get("stock") == "mesh" and
             first.get("tools") == ["dovetail"], first)

        answers.update({"machine": "PrintNC V4"})
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(job)
        FreeCADGui.runCommand("BearCAM_SimulatorMachine")
        QtGui.QApplication.processEvents()
        last = log["dialogs"][-1]
        step("machine command asks, the current choice preselected", last["kind"] == "machine" and
             last["preselected"] == "Makera Carvera Air", last)
        second = simulate(doc, job, "Job: second Simulate (no dialogs; re-posts to the open viewer)")
        step("re-post: no dialogs, the PrintNC, the same viewer", second["dialogs"] == [] and
             second.get("router") == "printnc-v4" and second["viewer_pid"] == first["viewer_pid"] and
             second.get("mtime", 0) > first.get("mtime", 0), second)

        answers.update({"post": "linuxcnc", "machine": "None (the stock alone)"})
        third = simulate(doc, job1, "Job001: drag knife dressup, no machine")
        step("Job001 file: a drag knife, no machine", third.get("router") is None and third.get("tools") == ["dragknife"],
             third)
    except Exception:
        step("exception", False, traceback.format_exc())
    finally:
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(log, f, indent=1)
        for name in list(FreeCAD.listDocuments()):
            FreeCAD.closeDocument(name)
        QtCore.QTimer.singleShot(500, QtGui.QApplication.instance().quit)


QtCore.QTimer.singleShot(4000, run)
