# The add-on's settings, in FreeCAD's parameters (Tools > Edit parameters >
# BaseApp/Preferences/Mod/BearCAMSimulator): the local viewer folder (for testing before a release
# is published), the rapid rate the viewer plays rapids at, the post processor chosen for jobs
# that name none, and the machine each job is shown on.
import json

import FreeCAD

GROUP = "User parameter:BaseApp/Preferences/Mod/BearCAMSimulator"


def params():
    return FreeCAD.ParamGet(GROUP)


def local_folder():
    return params().GetString("LocalViewerFolder", "").strip()


def set_local_folder(path):
    params().SetString("LocalViewerFolder", path)


def rapid_rate():
    """Rapids play at this rate (mm/min); the job's feeds give everything else."""
    rate = params().GetFloat("RapidRate", 5000.0)
    return rate if rate > 0 else 5000.0


def _key(doc, job):
    return (doc.FileName or doc.Name) + "::" + job.Name


def _choices():
    try:
        return json.loads(params().GetString("PostChoices", "{}") or "{}")
    except ValueError:
        return {}


def post_choice(doc, job):
    return _choices().get(_key(doc, job), "")


def set_post_choice(doc, job, post):
    c = _choices()
    c[_key(doc, job)] = post
    params().SetString("PostChoices", json.dumps(c))


def _machines():
    try:
        return json.loads(params().GetString("MachineChoices", "{}") or "{}")
    except ValueError:
        return {}


def machine_choice(doc, job):
    """The machine chosen for the job: an id, "" for none, or None when never chosen."""
    return _machines().get(_key(doc, job))


def set_machine_choice(doc, job, machine):
    c = _machines()
    c[_key(doc, job)] = machine
    params().SetString("MachineChoices", json.dumps(c))
