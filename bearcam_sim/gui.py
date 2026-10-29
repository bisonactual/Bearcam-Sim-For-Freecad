# "Simulate in BearCAM": a command in the CAM workbench (its Project Setup toolbar and the CAM menu,
# by the post commands). It takes the active job (the selected one, the only one, or the one the
# user picks), posts it with the job's post processor (or one the user picks for a job that names
# none), writes the job file and opens the viewer; run again, it re-posts and the open viewer
# reads the job again. The first time for a job it asks which machine to show it on (none, the
# Makera Carvera Air, the PrintNC V4), remembered; "BearCAM simulator machine..." changes that. The
# machine models are a download of their own, offered the first time a job is shown on a machine.
import os
import traceback

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui

from . import jobmap, prefs, viewer
from .jobmap import SimError

COMMAND = "BearCAM_Simulate"
MACHINE_COMMAND = "BearCAM_SimulatorMachine"
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
    """The machine's post, else the job's legacy post, a remembered choice or the user's pick."""
    configured = jobmap.machine_post(job) or getattr(job, "PostProcessor", "")
    if configured:
        return configured
    remembered = prefs.post_choice(doc, job)
    if remembered:
        return remembered
    import Path

    # FreeCAD 1.2 keeps the script posts apart from its machine posts; 1.0 and 1.1 have only those.
    enabled = getattr(Path.Preferences, "allEnabledLegacyPostProcessors", None) or Path.Preferences.allEnabledPostProcessors
    posts = enabled()
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


def choose_machine(doc, job, ask=False):
    """The machine to show the job on (an id, "" for none): the one chosen for it before, else (or
    when asked) the user's pick, preselected from the job's own machine and remembered for the
    job. None if the user cancels."""
    remembered = prefs.machine_choice(doc, job)
    if remembered is not None and not ask:
        return remembered
    ids = [m for m, _ in jobmap.MACHINES]
    labels = [label for _, label in jobmap.MACHINES]
    current = remembered if remembered is not None else jobmap.machine_guess(job)
    item, ok = QtGui.QInputDialog.getItem(
        main_window(), TITLE,
        f'Show the job "{job.Label}" on a machine in the simulator?\n'
        "Its frame, gantry and spindle move with the tool round the stock (3-axis jobs).\n"
        "(Remembered for this job; CAM > BearCAM simulator machine... changes it.)",
        labels, ids.index(current) if current in ids else 0, False)
    if not ok:
        return None
    choice = ids[labels.index(item)]
    prefs.set_machine_choice(doc, job, choice)
    return choice


def progress_bar(text):
    """A download's progress bar, shown, and the callback that moves it."""
    bar = QtGui.QProgressDialog(text, "", 0, 100, main_window())
    bar.setCancelButton(None)
    bar.setWindowTitle(TITLE)
    bar.setWindowModality(QtCore.Qt.WindowModal)
    bar.show()

    def progress(done, total):
        if total:
            bar.setValue(int(100 * done / total))
        QtGui.QApplication.processEvents()

    return bar, progress


def ensure_machine(doc, job, exe, machine):
    """The machine to show the job on, with its models beside the viewer: downloaded now (asked)
    when it has none, else "" when the user goes on without the machine (remembered for the job).
    None if the user cancels."""
    if not machine or viewer.machine_installed(exe, machine):
        return machine
    info = viewer.machines_info()
    label = jobmap.machine_label(machine)
    later = "(The job's machine is then set to None; CAM > BearCAM simulator machine... changes it.)"
    box = QtGui.QMessageBox(main_window())
    box.setWindowTitle(TITLE)
    box.setIcon(QtGui.QMessageBox.Question)
    if info:
        url, name, size = info
        mb = f", {size / 1e6:.1f} MB" if size else ""
        box.setText(f"The {label} is drawn from the simulator's machine models, which are not downloaded yet.\n\n"
                    f"Download {name}{mb} from\n{url}?\n\n"
                    "Its SHA-256 is checked against the one this add-on pins before it is used. Or show the job "
                    f"without the machine. {later}")
        download = box.addButton("Download", QtGui.QMessageBox.AcceptRole)
    else:
        box.setText(f"The simulator has no model of the {label}, and none has been published for download.\n\n"
                    f"Show the job without the machine? {later}")
        download = None
    without = box.addButton("Without the machine", QtGui.QMessageBox.ActionRole)
    box.addButton(QtGui.QMessageBox.Cancel)
    box.exec_()
    clicked = box.clickedButton()
    if download is not None and clicked == download:
        bar, progress = progress_bar("Downloading the BearCAM simulator's machine models...")
        try:
            viewer.download_machines(exe, progress)
        finally:
            bar.close()
        if not viewer.machine_installed(exe, machine):
            raise SimError(f"The downloaded machine models have no {label}.")
        return machine
    if clicked == without:
        prefs.set_machine_choice(doc, job, "")
        return ""
    return None


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
        bar, progress = progress_bar("Downloading the BearCAM simulator...")
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
            machine = choose_machine(doc, job)
            if machine is None:
                return
            exe = ensure_viewer()
            if exe is None:
                return
            machine = ensure_machine(doc, job, exe, machine)
            if machine is None:
                return
            QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            try:
                job_path, summary = jobmap.prepare(job, post, prefs.rapid_rate(), machine=machine)
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


class MachineCommand:
    """Chooses again the machine the simulator shows the active job on."""

    def GetResources(self):
        return {
            "Pixmap": ICON,
            "MenuText": "BearCAM simulator machine...",
            "ToolTip": "Choose the machine the BearCAM simulator shows the active job on (the Makera Carvera Air, "
                       "the PrintNC V4, or none). Simulate in BearCAM then uses it.",
        }

    def IsActive(self):
        return bool(jobmap.jobs_in(FreeCAD.ActiveDocument))

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        try:
            job = choose_job(doc)
            if job is None:
                return
            machine = choose_machine(doc, job, ask=True)
            if machine is not None:
                FreeCAD.Console.PrintMessage(f'{doc.Label}: {job.Label} is shown on: {jobmap.machine_label(machine)} '
                                             "(from the next Simulate in BearCAM)\n")
        except SimError as e:
            QtGui.QMessageBox.warning(main_window(), TITLE, str(e))


class Manipulator:
    """Puts the commands by the CAM workbench's post commands: its menu (simulate, then the
    machine) and the Project Setup toolbar (simulate)."""

    def modifyMenuBar(self):
        # After Post Process Selected, or after Post Process where there is none (FreeCAD 1.0, 1.1).
        after = "CAM_PostSelected" if "CAM_PostSelected" in FreeCADGui.listCommands() else "CAM_Post"
        return [{"insert": MACHINE_COMMAND, "menuItem": after, "after": ""},
                {"insert": COMMAND, "menuItem": after, "after": ""}]

    def modifyToolBars(self):
        # The workbench being set up, by its class (its name() is not ready while it activates).
        if type(FreeCADGui.activeWorkbench()).__name__ == "CAMWorkbench":
            return [{"append": COMMAND, "toolBar": "Project Setup"}]
        return []


def register():
    FreeCADGui.addCommand(COMMAND, SimulateCommand())
    FreeCADGui.addCommand(MACHINE_COMMAND, MachineCommand())
    if hasattr(FreeCADGui, "addWorkbenchManipulator") and not getattr(FreeCADGui, "BearCAMSimManipulator", None):
        FreeCADGui.BearCAMSimManipulator = Manipulator()
        FreeCADGui.addWorkbenchManipulator(FreeCADGui.BearCAMSimManipulator)
