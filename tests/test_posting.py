"""Posting and simulation-input regressions; run with python -m unittest discover -s tests."""
import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
fc = types.ModuleType("FreeCAD")
fc.GuiUp = 1
sys.modules.setdefault("FreeCAD", fc)
from bearcam_sim import jobmap


def fixture(machine="", label='TC Mill: 1/8"3.175mm) Short, 1/4" shank'):
    tool = types.SimpleNamespace(Label="Endmill")
    tc = types.SimpleNamespace(Label=label, Tool=tool, ToolNumber=1)
    op = types.SimpleNamespace(Label="Profile", ToolController=tc, Path=True, Active=True)
    doc = types.SimpleNamespace(Name="Doc", Label="Test", FileName="")
    return types.SimpleNamespace(Machine=machine, PostProcessor="linuxcnc", Name="Job", Label="Job",
                                 Document=doc, Operations=types.SimpleNamespace(Group=[op]),
                                 Tools=types.SimpleNamespace(Group=[tc]), Stock=True, Fixtures=["G54"])


class PostingTests(unittest.TestCase):
    def setUp(self):
        self.machine = types.SimpleNamespace(postprocessor_file_name="makera_26_MCH")
        self.machine_factory = types.SimpleNamespace(get_machine=Mock(return_value=self.machine))
        self.post = types.SimpleNamespace(values={}, export=Mock(return_value=[("one", "G21\n")]),
                                          export2=Mock(return_value=[("one", "G21\n")]),
                                          remote_post=Mock(), apply_configuration_bundle=Mock())
        self.factory = types.SimpleNamespace(get_post_processor=Mock(return_value=self.post))
        self.modules = patch.dict(sys.modules, {
            "Path": types.ModuleType("Path"), "Path.Post": types.ModuleType("Path.Post"),
            "Path.Post.Processor": types.SimpleNamespace(PostProcessorFactory=self.factory),
            "Machine": types.ModuleType("Machine"), "Machine.models": types.ModuleType("Machine.models"),
            "Machine.models.machine": types.SimpleNamespace(MachineFactory=self.machine_factory),
        })
        self.modules.start()
        self.addCleanup(self.modules.stop)
        jobmap.FreeCAD.GuiUp = 1

    def test_machine_overrides_stale_legacy_choice_and_uses_export2(self):
        self.post.values["MIN_SPINDLE_SPEED"] = 500
        self.assertEqual(jobmap.post_job(fixture("Air"), "old_remembered_post"), "G21\n")
        self.assertEqual(self.factory.get_post_processor.call_args.args[1], "makera_26_MCH")
        self.post.apply_configuration_bundle.assert_called_once_with()
        self.post.export2.assert_called_once_with()
        self.post.export.assert_not_called()
        self.assertTrue(self.post._bundle_applied)
        self.assertTrue(self.post._dialog_handled)
        self.assertFalse(self.post.values["SHOW_EDITOR"])
        self.assertEqual(self.post.values["MIN_SPINDLE_SPEED"], 500)
        self.assertEqual(jobmap.FreeCAD.GuiUp, 1)

    def test_machine_remote_hook_is_suppressed(self):
        self.machine.postprocessor_file_name = "other_machine_post"
        upload = self.post.remote_post
        self.post.export2.side_effect = lambda: (self.post.remote_post([("one", "G21")]) or [("one", "G21")])
        jobmap.post_job(fixture("Other"), "ignored")
        upload.assert_not_called()

    def test_makera_unspecified_limit_uses_post_configuration(self):
        self.post._machine = types.SimpleNamespace(postprocessor_properties={"min_spindle_speed": 7.0})
        self.post.values["MIN_SPINDLE_SPEED"] = None
        jobmap.post_job(fixture("Air"), "ignored")
        self.assertEqual(self.post.values["MIN_SPINDLE_SPEED"], 7.0)

    def test_legacy_export_and_split_output_are_preserved(self):
        self.post.export.return_value = [("a", "G21\n"), ("b", "G1 X2\n"), ("empty", "")]
        self.assertEqual(jobmap.post_job(fixture(), "linuxcnc"), "G21\nG1 X2\n")
        self.post.export.assert_called_once_with()
        self.post.export2.assert_not_called()
        self.post.apply_configuration_bundle.assert_not_called()

    def test_missing_machine_does_not_fall_back(self):
        self.machine_factory.get_machine.side_effect = FileNotFoundError("missing")
        with self.assertRaisesRegex(jobmap.SimError, 'machine "Air" could not be loaded'):
            jobmap.post_job(fixture("Air"), "linuxcnc")
        self.factory.get_post_processor.assert_not_called()

    def test_machine_without_post_is_explained(self):
        self.machine.postprocessor_file_name = ""
        with self.assertRaisesRegex(jobmap.SimError, "names no post processor"):
            jobmap.machine_post(fixture("Air"))

    def test_export_failure_restores_gui(self):
        self.post.export.side_effect = ValueError("bad post")
        with self.assertRaisesRegex(jobmap.SimError, "bad post"):
            jobmap.post_job(fixture(), "linuxcnc")
        self.assertEqual(jobmap.FreeCAD.GuiUp, 1)

    def test_missing_and_empty_posts_are_explained(self):
        for result in (None, types.SimpleNamespace(message="not found")):
            self.factory.get_post_processor.return_value = result
            with self.assertRaisesRegex(jobmap.SimError, "was not found"):
                jobmap.post_job(fixture(), "missing")
        self.factory.get_post_processor.return_value = self.post
        for result in (None, [], [("empty", "")]):
            self.post.export.return_value = result
            with self.assertRaisesRegex(jobmap.SimError, "gave no G-code"):
                jobmap.post_job(fixture(), "empty")

    def test_gui_machine_precedes_remembered_choice(self):
        with patch.dict(sys.modules, {"FreeCADGui": types.ModuleType("FreeCADGui"),
                                      "PySide": types.SimpleNamespace(QtCore=Mock(), QtGui=Mock())}):
            gui = importlib.import_module("bearcam_sim.gui")
            with patch.object(gui.prefs, "post_choice", side_effect=AssertionError("stale choice used")):
                self.assertEqual(gui.choose_post(None, fixture("Air")), "makera_26_MCH")

    def test_machine_only_job_is_recognised(self):
        job = fixture("Air")
        del job.PostProcessor
        self.assertTrue(jobmap.is_job(job))


class SimulationInputTests(unittest.TestCase):
    def test_reported_line14_repaired_without_changing_label_or_line_count(self):
        job = fixture()
        label = job.Tools.Group[0].Label
        nc = "\n" * 13 + "(" + label + ")\nM3 S12000\n"
        result = jobmap.simulation_gcode(job, nc, "linuxcnc")
        self.assertEqual(result.splitlines()[13], '(' + label.replace(')', ']') + ')')
        self.assertEqual(len(result.splitlines()), len(nc.splitlines()))
        self.assertEqual(job.Tools.Group[0].Label, label)
        self.assertTrue(result.endswith("M3 S12000\n"))

    def test_numbered_label_and_line_endings(self):
        job = fixture(label="Tool (short)")
        text = '  N140 (Tool (short))  \r\nG1 X2\r\n'
        self.assertEqual(jobmap.simulation_gcode(job, text, "linuxcnc"),
                         '  N140 (Tool [short])  \r\nG1 X2\r\n')

    def test_unknown_comments_and_real_trailing_code_are_not_repaired(self):
        job = fixture(label="Tool) Short")
        for line in ('(Unknown) Short)', '(Tool) Short) G1 X99', '(Tool) G1 X99', '(Tool (nested))'):
            self.assertEqual(jobmap.simulation_gcode(job, line, "linuxcnc"), line)

    def test_makera_auxiliary_only_variants_preserve_spindle_words_elsewhere(self):
        job = fixture()
        for aux in ('M851S100', 'M851 S25.5', 'N20 M851 S100 (external)', 'S50 M851',
                    'M851', 'M852', 'm851 s0 ;external'):
            nc = 'M3 S12000\n' + aux + '\nG1 X1 F100\nS6000\n'
            result = jobmap.simulation_gcode(job, nc, "makera_26_MCH")
            self.assertEqual(jobmap.code_lines(result), ['M3 S12000', '', 'G1 X1 F100', 'S6000'])
            self.assertIn(aux, result)
            self.assertEqual(len(nc.splitlines()), len(result.splitlines()))

    def test_other_posts_and_unknown_m_codes_are_not_rewritten(self):
        nc = 'M851 S100\nM999 S50\n'
        self.assertEqual(jobmap.simulation_gcode(fixture(), nc, "marlin"), nc)
        self.assertIn('M999 S50\n', jobmap.simulation_gcode(fixture(), nc, "makera_legacy"))

    def test_mixed_or_invalid_makera_auxiliary_blocks_are_refused(self):
        for line in ('M851 S100 G1 X2', 'M851 S100 M3', 'M851 S101', 'M851 S-1',
                     'M852 S100', 'M851 Q5', 'M851 S1 S2', 'M851 S#1', 'M851 garbage'):
            with self.subTest(line=line), self.assertRaisesRegex(jobmap.SimError, 'Line 2: Makera'):
                jobmap.simulation_gcode(fixture(), 'G21\n' + line, 'makera_26_MCH')

    def test_nested_comments_do_not_change_units_or_rotary_detection(self):
        nc = '(Tool (short) A90 G20; description)\nG21\nG1 X1 (nested (A50))\n'
        self.assertEqual(jobmap.units_of(nc), 'mm')
        self.assertFalse(jobmap.has_a_axis(nc))
        self.assertTrue(jobmap.has_a_axis(nc + 'G0 A90\n'))

    def test_operation_markers_support_machine_labels_and_repaired_names(self):
        job = fixture()
        op = job.Operations.Group[0]
        op.Label = 'Profile (outside)'
        ops = [(op, op.ToolController)]
        for nc in ('N10 (Profile [outside])\nG1 X1\n',
                   '(Begin operation: Profile [outside])\nG1 X1\n'):
            self.assertEqual(jobmap.operation_lines(nc, ops)[0]['first_line'], 1)

    def test_prepare_preserves_raw_export_and_correct_provenance(self):
        job = fixture('Air')
        raw = '(' + job.Tools.Group[0].Label + ')\nM3 S12000\nM851S100\n(Profile)\nG1 X1\n'
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(jobmap, 'machine_post', return_value='makera_26_MCH'), \
                patch.object(jobmap, 'post_job', return_value=raw), \
                patch.object(jobmap, 'stock_of', return_value=({'kind': 'box'}, None)), \
                patch.object(jobmap, 'tools_of', return_value=[{'number': 1}]):
            path, summary = jobmap.prepare(job, 'stale_legacy', folder=folder)
            with open(os.path.join(folder, 'posted.nc'), encoding='utf-8') as f:
                self.assertEqual(f.read(), raw)
            with open(os.path.join(folder, 'program.nc'), encoding='utf-8') as f:
                sim = f.read()
            self.assertEqual(len(sim.splitlines()), len(raw.splitlines()))
            self.assertNotIn('M851', '\n'.join(jobmap.code_lines(sim)))
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
            self.assertEqual(data['source']['post_processor'], 'makera_26_MCH')
            self.assertEqual(data['operations'][0]['first_line'], 4)
            self.assertIn('makera_26_MCH', summary)


if __name__ == '__main__':
    unittest.main()
