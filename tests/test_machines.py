"""The machine models' download: found beside the viewer, fetched and checked against the pinned
SHA-256, refused when anything is off. Run with python -m unittest discover -s tests."""
import hashlib
import io
import json
import os
import sys
import tempfile
import types
import unittest
import zipfile
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.modules.setdefault("FreeCAD", types.ModuleType("FreeCAD"))
from bearcam_sim import jobmap, viewer

BASE = "https://example.invalid/releases/download/v0/"


def pack(files):
    """A zip of name: bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


MODELS = pack({
    "machines/carvera-air.json": json.dumps({"id": "carvera-air", "body": "carvera-air.glb"}),
    "machines/carvera-air.glb": b"glTF model",
    "machines/printnc-v4.json": json.dumps({"id": "printnc-v4", "body": "printnc-clean.glb"}),
    "machines/printnc-clean.glb": b"glTF model",
    "LICENSE-SIMULATOR.txt": "licence",
})


class Served:
    """urllib's opener, serving one archive from memory."""

    def __init__(self, data):
        self.data, self.urls = data, []

    def open(self, url, timeout=0):
        self.urls.append(url)
        r = io.BytesIO(self.data)
        r.headers = {"Content-Length": str(len(self.data))}
        return r


class MachineModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.exe = os.path.join(self.tmp.name, "sim", viewer.exe_name())
        os.makedirs(os.path.dirname(self.exe))
        open(self.exe, "wb").close()

    def release(self, data, sha=None, name="bearcam-machines-0.zip", base=BASE):
        rel = {"version": "0", "base_url": base, "files": {},
               "machines": {"name": name, "sha256": sha or hashlib.sha256(data).hexdigest(), "size": len(data)}}
        return patch.object(viewer, "release", return_value=rel)

    def serve(self, data):
        served = Served(data)
        return served, patch.object(viewer.urllib.request, "build_opener", return_value=served)

    def test_every_offered_machine_is_in_the_models(self):
        for machine_id in (m for m, _ in jobmap.MACHINES if m):
            self.assertIn(f"machines/{machine_id}.json", zipfile.ZipFile(io.BytesIO(MODELS)).namelist())

    def test_download_puts_the_models_beside_the_viewer(self):
        self.assertFalse(viewer.machine_installed(self.exe, "carvera-air"))
        served, opener = self.serve(MODELS)
        with self.release(MODELS), opener:
            dest = viewer.download_machines(self.exe)
        self.assertEqual(served.urls, [BASE + "bearcam-machines-0.zip"])
        self.assertEqual(dest, os.path.join(os.path.dirname(self.exe), "machines"))
        self.assertTrue(viewer.machine_installed(self.exe, "carvera-air"))
        self.assertTrue(viewer.machine_installed(self.exe, "printnc-v4"))
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(self.exe), "LICENSE-SIMULATOR.txt")))

    def test_a_model_missing_its_body_is_not_installed(self):
        machines = os.path.join(os.path.dirname(self.exe), "machines")
        os.makedirs(machines)
        with open(os.path.join(machines, "carvera-air.json"), "w") as f:
            json.dump({"body": "carvera-air.glb"}, f)
        self.assertFalse(viewer.machine_installed(self.exe, "carvera-air"))

    def test_a_build_finds_the_source_trees_models(self):
        build = os.path.join(self.tmp.name, "tree", "build", "Release")
        os.makedirs(build)
        exe = os.path.join(build, viewer.exe_name())
        open(exe, "wb").close()
        machines = os.path.join(self.tmp.name, "tree", "machines")
        os.makedirs(machines)
        with open(os.path.join(machines, "printnc-v4.json"), "w") as f:
            json.dump({"body": "printnc-clean.glb"}, f)
        open(os.path.join(machines, "printnc-clean.glb"), "wb").close()
        self.assertTrue(viewer.machine_installed(exe, "printnc-v4"))

    def test_a_download_not_matching_its_pin_is_not_used(self):
        served, opener = self.serve(MODELS)
        with self.release(MODELS, sha="0" * 64), opener, self.assertRaisesRegex(viewer.SimError, "pinned SHA-256"):
            viewer.download_machines(self.exe)
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(self.exe), "machines")))

    def test_a_larger_download_is_stopped(self):
        served, opener = self.serve(MODELS + b"more")
        with self.release(MODELS), opener, self.assertRaisesRegex(viewer.SimError, "larger than the pinned"):
            viewer.download_machines(self.exe)

    def test_only_https(self):
        served, opener = self.serve(MODELS)
        with self.release(MODELS, base="http://example.invalid/"), opener, \
                self.assertRaisesRegex(viewer.SimError, "not HTTPS"):
            viewer.download_machines(self.exe)
        self.assertEqual(served.urls, [])

    def test_a_file_outside_the_folder_is_refused(self):
        bad = pack({"machines/carvera-air.json": "{}", "../escaped.txt": "x"})
        served, opener = self.serve(bad)
        with self.release(bad), opener, self.assertRaisesRegex(viewer.SimError, "outside its folder"):
            viewer.download_machines(self.exe)
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "escaped.txt")))

    def test_nothing_pinned(self):
        with patch.object(viewer, "release", return_value={"version": "0", "base_url": BASE, "files": {}}):
            self.assertIsNone(viewer.machines_info())
            with self.assertRaisesRegex(viewer.SimError, "No machine models"):
                viewer.download_machines(self.exe)

    def test_the_shipped_pins(self):
        rel = viewer.release()
        self.assertTrue(rel["base_url"].startswith("https://"))
        self.assertTrue(rel["machines"]["name"].startswith("bearcam-machines-"))
        self.assertEqual(len(rel["machines"]["sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
