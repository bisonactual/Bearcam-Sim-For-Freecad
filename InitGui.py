# FreeCAD loads this when its GUI starts: the "Simulate in BearCAM" command and its place in the
# CAM workbench.


def _bearcam_simulator_gui():
    import bearcam_sim.gui

    bearcam_sim.gui.register()


_bearcam_simulator_gui()
