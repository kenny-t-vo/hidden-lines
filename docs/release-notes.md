HL 0.1.3: the dialog fits a laptop's screen. It opens no taller than the screen, its options scroll when the window is too short for them, and the line saying where the drawing goes, Cancel and Draw, and the Help, Report a problem and About links stay in view at the bottom. The grey notes under the options are a point smaller. Drawings are the same as 0.1.2's.

To update from an earlier version, click Update for HiddenLines in the Package Manager and restart Rhino; HL keeps the Python and packages it downloaded and does not ask again. To install it, type `PackageManager` in Rhino 8, search for **HiddenLines**, click Install, and restart Rhino. Or download the package for your computer from the assets below:

- `hiddenlines-0.1.3-rh8_0-mac.yak`: a Mac, Apple silicon or Intel
- `hiddenlines-0.1.3-rh8_0-win.yak`: Windows 10 or 11

**Mac.** Double-click the file. Rhino 8 opens and installs it without showing a window; its command line says "Successfully installed HiddenLines". Quit Rhino and open it again.

**Windows.** In Rhino 8, type `-PackageManager`, choose Install, then Browse, and pick the file. Quit Rhino and open it again.

Then type `HL`: that is the command, and HiddenLines the package's name. The first time, it asks to download Python 3.12 and the packages the drawing runs on, about 700 MB, once. The [README](https://github.com/kenny-t-vo/hidden-lines#readme) is the full guide: drawing, the layer roles and line weights, the drawing's layers in Rhino, and what to do when something goes wrong.

Known issues:

- HL draws only what the model holds: an open solid, a face crossing itself or two objects overlapping come out as broken, doubled or missing lines. The results window lists those objects so you can fix them.
- Large models are slow to export. A model of about 3,300 objects and 6.8 million triangles takes 15 to 20 minutes to export the first time, less when the same objects are exported again, and about a minute to draw.
- The same export drawn on a Mac and on Windows matches to within 0.1 pt, not byte for byte, and a sliver of edge where two objects' cuts meet can take the neighbouring object's weight.
- Intel Macs have not been tested.

Report a problem from the link at the bottom of HL's dialog, with the log attached.
