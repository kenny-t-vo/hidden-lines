HL 0.1.5: HL now runs on Rhino 8 before 8.6, where it stopped with a TypeError once the model was read, before anything was drawn ([issue 1](https://github.com/kenny-t-vo/hidden-lines/issues/1)). Remove HL's settings also works before 8.9. This was tested on Rhino 8.35 with the older Rhino's missing call simulated, not on a real 8.5, so please say on that issue how it goes on an older Rhino.

Two other changes alter what some models draw. Every other drawing is the same as 0.1.4's.

- Blocks placed by a mirror are no longer reported as inside out: HL turns the faces of each mirrored copy to face as the block's definition does.
- Under a layer you set to Context, Ground, See-through, Lines on the ground or Hides, a sublayer's name can no longer make it Building, Building detail, Furniture or Texture, so a site model's existing walls and garden beds take their parent's role. And `reference` in a layer's name now leaves it out, `lot` no longer makes it Lines on the ground, and "ground floor" reads as Building.

To update from an earlier version, click Update for HiddenLines in the Package Manager and restart Rhino; HL keeps the Python and packages it downloaded and does not ask again. To install it, type `PackageManager` in Rhino 8, search for **HiddenLines**, click Install, and restart Rhino. Or download the package for your computer from the assets below:

- `hiddenlines-0.1.5-rh8_0-mac.yak`: a Mac, Apple silicon or Intel
- `hiddenlines-0.1.5-rh8_0-win.yak`: Windows 10 or 11

**Mac.** Double-click the file. Rhino 8 opens and installs it without showing a window; its command line says "Successfully installed HiddenLines". Quit Rhino and open it again.

**Windows.** In Rhino 8, type `-PackageManager`, choose Install, then Browse, and pick the file. Quit Rhino and open it again.

Then type `HL`: that is the command, and HiddenLines the package's name. The first time, it asks to download Python 3.12 and the packages the drawing runs on, once: about 120 MB, which take up to 700 MB of disk. The [README](https://github.com/kenny-t-vo/hidden-lines#readme) is the full guide: drawing, the layer roles and line weights, the drawing's layers in Rhino, and what to do when something goes wrong.

Known issues:

- HL draws only what the model holds: an open solid, a face crossing itself or two objects overlapping come out as broken, doubled or missing lines. The results window lists those objects so you can fix them.
- Large models are slow to export. A model of about 3,300 objects and 6.8 million triangles takes 15 to 20 minutes to export the first time, less when the same objects are exported again, and about a minute to draw.
- The same export drawn on a Mac and on Windows matches to within 0.1 pt, not byte for byte, and a sliver of edge where two objects' cuts meet can take the neighbouring object's weight.
- Intel Macs have not been tested.

Report a problem from the link at the bottom of HL's dialog, with the log attached.
