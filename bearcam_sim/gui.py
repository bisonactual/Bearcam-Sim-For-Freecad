# "Simulate in BearCAM": a command in the CAM workbench (its Project Setup toolbar and the CAM menu,
# by the post commands). It takes the active job (the selected one, the only one, or the one the
# user picks), posts it with the job's post processor (or one the user picks for a job that names
# none), writes the job file and opens the viewer; run again, it re-posts and the open viewer
# reads the job again.
import os
import traceback

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui

from . import jobmap, prefs, viewer
from .jobmap import SimError

COMMAND = "BearCAM_Simulate"
TITLE = "Simulate in BearCAM"
ICON = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Resources", "icons",
                    "BearCAMSimulate.png")


def main_window():
    return FreeCADGui.getMainWindow()


def choose_job(doc):
    jobs = jobmap.jobs_in(doc)
    if not jobs:
        raise SimError("This document has no CAM job.")
    for obj in FreeCADGui.Selection.getSelection():
        job = jobmap.job_of(obj)
        if job is not None:
            return job
    if len(jobs) == 1:
        return jobs[0]
    labels = [j.Label for j in jobs]
    item, ok = QtGui.QInputDialog.getItem(main_window(), TITLE, "This document has several jobs (one setup each). "
                                          "Which one?", labels, 0, False)
    return jobs[labels.index(item)] if ok else None


def choose_post(doc, job):
    """The job's post processor; for a job that names none, the one chosen for it before, else
    the user's pick (remembered for this job)."""
    if job.PostProcessor:
        return job.PostProcessor
    remembered = prefs.post_choice(doc, job)
    if remembered:
        return remembered
    import Path

    posts = Path.Preferences.allEnabledLegacyPostProcessors()
    if not posts:
        raise SimError("No post processor is enabled (Edit > Preferences > CAM).")
    default = Path.Preferences.defaultPostProcessor() or ""
    item, ok = QtGui.QInputDialog.getItem(
        main_window(), TITLE,
        f'The job "{job.Label}" names no post processor. Post it with\n'
        "(remembered for this job; a post processor set on the job is used instead):",
        posts, posts.index(default) if default in posts else 0, False)
    if not ok:
        return None
    prefs.set_post_choice(doc, job, item)
    return item


def ensure_viewer():
    """The viewer's path: the local folder's, the downloaded one, or downloaded now (asked), or a
    folder the user chooses. None if the user cancels."""
    user_dir = FreeCAD.getUserAppDataDir()
    exe = viewer.find(prefs.local_folder(), user_dir)
    if exe:
        return exe
    info = viewer.download_info()
    box = QtGui.QMessageBox(main_window())
    box.setWindowTitle(TITLE)
    box.setIcon(QtGui.QMessageBox.Question)
    if info:
        url, name, size = info
        mb = f", {size / 1e6:.1f} MB" if size else ""
        box.setText(f"The BearCAM simulator is not downloaded yet.\n\nDownload {name}{mb} from\n{url}?\n\n"
                    "Its SHA-256 is checked against the one this add-on pins before it is used.")
        download = box.addButton("Download", QtGui.QMessageBox.AcceptRole)
    else:
        box.setText("No BearCAM simulator has been published for download yet.\n\n"
                    "Choose the folder that holds stockviewer (a build or an unpacked release).")
        download = None
    choose = box.addButton("Choose folder...", QtGui.QMessageBox.ActionRole)
    box.addButton(QtGui.QMessageBox.Cancel)
    box.exec_()
    clicked = box.clickedButton()
    if download is not None and clicked == download:
        bar = QtGui.QProgressDialog("Downloading the BearCAM simulator...", "", 0, 100, main_window())
        bar.setCancelButton(None)
        bar.setWindowTitle(TITLE)
        bar.setWindowModality(QtCore.Qt.WindowModal)
        bar.show()

        def progress(done, total):
            if total:
                bar.setValue(int(100 * done / total))
            QtGui.QApplication.processEvents()

        try:
            return viewer.download(user_dir, progress)
        finally:
            bar.close()
    if clicked == choose:
        folder = QtGui.QFileDialog.getExistingDirectory(main_window(), "The folder with stockviewer",
                                                        prefs.local_folder() or os.path.expanduser("~"))
        if not folder:
            return None
        if not viewer.in_folder(folder):
            raise SimError(f"There is no {viewer.exe_name()} in {folder}.")
        prefs.set_local_folder(folder)
        return viewer.in_folder(folder)
    return None


class SimulateCommand:
    def GetResources(self):
        return {
            "Pixmap": ICON,
            "MenuText": TITLE,
            "ToolTip": "Post the active CAM job and play it in the BearCAM simulator, in its own window. "
                       "Run it again after a change: the open simulator reads the job again.",
        }

    def IsActive(self):
        return bool(jobmap.jobs_in(FreeCAD.ActiveDocument))

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        try:
            job = choose_job(doc)
            if job is None:
                return
            post = choose_post(doc, job)
            if post is None:
                return
            exe = ensure_viewer()
            if exe is None:
                return
            QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            try:
                job_path, summary = jobmap.prepare(job, post, prefs.rapid_rate())
                pid, started = viewer.launch(exe, job_path)
            finally:
                QtGui.QApplication.restoreOverrideCursor()
            FreeCAD.Console.PrintMessage(summary + ("; simulator opened\n" if started else
                                                    "; the open simulator reads it again\n"))
        except SimError as e:
            QtGui.QMessageBox.warning(main_window(), TITLE, str(e))
        except Exception as e:
            FreeCAD.Console.PrintError(traceback.format_exc())
            QtGui.QMessageBox.critical(main_window(), TITLE, f"Something went wrong: {e}\n(The report view has the "
                                       "details.)")


class Manipulator:
    """Puts the command by the CAM workbench's post commands: its menu and Project Setup toolbar."""

    def modifyMenuBar(self):
        return [{"insert": COMMAND, "menuItem": "CAM_PostSelected", "after": ""}]

    def modifyToolBars(self):
        # The workbench being set up, by its class (its name() is not ready while it activates).
        if type(FreeCADGui.activeWorkbench()).__name__ == "CAMWorkbench":
            return [{"append": COMMAND, "toolBar": "Project Setup"}]
        return []


def register():
    FreeCADGui.addCommand(COMMAND, SimulateCommand())
    if hasattr(FreeCADGui, "addWorkbenchManipulator") and not getattr(FreeCADGui, "BearCAMSimManipulator", None):
        FreeCADGui.BearCAMSimManipulator = Manipulator()
        FreeCADGui.addWorkbenchManipulator(FreeCADGui.BearCAMSimManipulator)
