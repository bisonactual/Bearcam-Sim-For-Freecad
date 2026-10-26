# Posting regression checks

With ordinary Python, from the add-on root:

```sh
python -B -m unittest discover -s tests -v
```

For the integration check, run `integration_freecad.py` with FreeCAD's bundled Python:

```sh
python -B tests/integration_freecad.py --posts /path/to/makera-files --viewer /path/to/stockviewer --out /path/to/test-output
```

The posts folder must contain the official `Makera_Air.fcm`, `makera_26_MCH_post.py` and
`makera_legacy_post.py` from Makera's CarveraProfiles repository. No installation of those
files is needed. The test creates and closes a disposable document, writes its outputs to
`--out`, and invokes the viewer's headless `--read-dump`. It does not connect to a CNC machine.

The integration cases cover a machine configured for external-output PWM at 100 and 35 percent,
the Makera legacy post, and FreeCAD's LinuxCNC legacy post. All use the reported malformed
tool-controller label. The test verifies post selection, settings, document preservation,
line correspondence, operation markers and a constant 12000 RPM in the released viewer's
readback. The minimum-spindle-speed compatibility case uses the supplied machine definition
without a minimum-speed override in the job.

The add-on is version 0.5.1; `release.json` intentionally keeps the existing 0.5.0 simulator
download and checksum. These fixes require no new executable.
