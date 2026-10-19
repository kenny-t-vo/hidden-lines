HL 0.1.0, the first public release: one command for Rhino 8 on Mac and Windows that draws a model's visible lines, as Make2D does, with line weights by what each edge is, sections closed for poché, and the drawing added to the model as layered curves.

Install it from Rhino 8's Package Manager: type `PackageManager`, search for **HiddenLines**, click Install, and restart Rhino. Or download the package for your computer from the assets below:

- `hiddenlines-0.1.0-rh8_0-mac.yak`: a Mac, Apple silicon or Intel
- `hiddenlines-0.1.0-rh8_0-win.yak`: Windows 10 or 11

**Mac.** Double-click the file. Rhino 8 opens and installs it without showing a window; its command line says "Successfully installed HiddenLines". Quit Rhino and open it again.

**Windows.** In Rhino 8, type `-PackageManager`, choose Install, then Browse, and pick the file. Quit Rhino and open it again.

The first time you type `HL`, it asks to download Python 3.12 and the packages the drawing runs on, about 700 MB, once. The [README](https://github.com/kenny-t-vo/hidden-lines#readme) is the full guide: drawing, the layer roles and line weights, the drawing's layers in Rhino, and what to do when something goes wrong.

Known issues:

- HL draws only what the model holds: an open solid, a face crossing itself or two objects overlapping come out as broken, doubled or missing lines. The results window lists those objects so you can fix them.
- Large models are slow. A model of about 3,300 objects and 6.8 million triangles takes 15 to 20 minutes to export the first time and about 2 minutes to draw; exporting the same objects again takes about 6.
- The same export drawn on a Mac and on Windows matches to within 0.1 pt, not byte for byte, and a sliver of edge where two objects' cuts meet can take the neighbouring object's weight.
- Intel Macs have not been tested.

Report a problem from the link at the bottom of HL's dialog, with the log attached.
