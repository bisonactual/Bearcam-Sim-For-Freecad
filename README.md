# FreeCAD G-code simulator, by BearCAM

Welcome to the freecad simulator by moi. I know simulation has been a pain point for ages for freecad, so thought I'd contribute mine.

I've been working on this for ages, along with the rest of BearCAM (as yet unreleased!) - The FreeCAD crew, community, and source have been invaluable to my learning experience, so this is part of giving back!

The source code is not currently available, though if a FreeCAD of OCCT maintainer has a genuine use case for inspection, that is not impossible. 

If you are one of a hundred people making CAD software currently, I wish you good luck, but have no interest in collaboration or contribution.

## Why no pull request? This should be on core.

A few reasons. Firstly, I'd need to port to metal on mac, and I do not own a macbook. Secondly this simulator is 15k lines or so of pretty non trivial code, which would be a nightmare to verify. I'm not complaining about this; it's just one of those things! 
If the sim is popular, I will port it to metal. I may need a macbook donated though :D 

I'm open to adding collision checking; however if I do, it will run FreeCAD's checks, not my own. Don't expect it to be identical in output to vericut or bearcam. 

Note that I made the clanker write the docs - they should help but appear incomplete. For example, F3 gives diag data. If you have a potato gpu, you may have to give your bricks more memory than the default.

I suggest heightfields for 3 axis and sparse voxel bricks for 5/4 axis. (you can switch with E)

Enjoy! (below is clanker output.)


Clanker didnt think to link the docs, so here we are: https://github.com/bisonactual/Bearcam-Sim-For-Freecad/blob/main/docs/use.md

## Quick start

1. Install the add-on and restart FreeCAD ([installing](docs/install.md)).
2. In the CAM workbench, select a job and click **Simulate in BearCAM** (Project Setup toolbar, or
   the CAM menu).
3. The first time, let it download the simulator; it is checked against a pinned SHA-256 before
   it is used.

Windows and Linux (x86-64) with an OpenGL 4.5 / 4.6 driver; macOS is not supported for now. 



## Licences

This repository has two parts, licensed differently:

- **The add-on**: everything in this repository except the files named below. MIT licence:
  [`LICENSE`](LICENSE).
- **The BearCAM simulator program**: `stockviewer`, its shaders and the files in its release
  archives. It is not in this repository; it is published as release files. It is free of charge
  under its own end-user licence: [`LICENSE-SIMULATOR.txt`](LICENSE-SIMULATOR.txt), also inside
  each archive. In short:
  - binary only;
  - use it as the add-on starts it, or to simulate programs made in FreeCAD;
  - get it only from the official download;
  - no warranty.

Third-party files in the simulator's archives (the Microsoft Visual C++ runtime on Windows) and
the software the add-on relies on are listed in [`CREDITS.md`](CREDITS.md). Neither licence covers
the BearCAM name or bear logo.

The simulation is a visual aid, not a guarantee: prove every program on the machine. 
