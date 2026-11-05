HL 0.1.6: HL now runs on Rhino 9, thanks to [Laurenzooo](https://github.com/Laurenzooo) ([pull request 2](https://github.com/kenny-t-vo/hidden-lines/pull/2)). On Rhino 9's Python 3.13, 0.1.5 stopped as soon as it started, while trying to build numpy 2.0.2 from source. This was tested on the Rhino 9 beta for Mac on Apple silicon, 9.0.26293, on a demo model and part of a real one. Rhino 9 on Windows has not been run.

A layer whose name holds a character DXF does not allow, such as `Gypsum/Drywall`, no longer stops the drawing when the line weights come from your layers. The DXF's layer name takes a dash in its place. On Rhino 8, every other drawing is the same as 0.1.5's.

To update from an earlier version, click Update for HiddenLines in the Package Manager and restart Rhino; HL keeps the Python and packages it downloaded and does not ask again. To install it, type `PackageManager` in Rhino, search for **HiddenLines**, click Install, and restart Rhino. Or download the package for your computer from the assets below:

- `hiddenlines-0.1.6-rh8_0-mac.yak`: a Mac, Apple silicon or Intel
- `hiddenlines-0.1.6-rh8_0-win.yak`: Windows 10 or 11

**Mac.** Double-click the file. Rhino opens and installs it without showing a window; its command line says "Successfully installed HiddenLines". Quit Rhino and open it again.

**Windows.** In Rhino, type `-PackageManager`, choose Install, then Browse, and pick the file. Quit Rhino and open it again.

Then type `HL`: that is the command, and HiddenLines the package's name. The first time, it asks to download Python 3.12 and the packages the drawing runs on, once: about 120 MB, which take up to 700 MB of disk. The [README](https://github.com/kenny-t-vo/hidden-lines#readme) is the full guide: drawing, the layer roles and line weights, the drawing's layers in Rhino, and what to do when something goes wrong.

Known issues:

- HL draws only what the model holds: an open solid, a face crossing itself or two objects overlapping come out as broken, doubled or missing lines. The results window lists those objects so you can fix them.
- Large models are slow to export. A model of about 3,300 objects and 6.8 million triangles takes 15 to 20 minutes to export the first time, less when the same objects are exported again, and about a minute to draw.
- The same export drawn on a Mac and on Windows matches to within 0.1 pt, not byte for byte, and a sliver of edge where two objects' cuts meet can take the neighbouring object's weight.
- On Rhino 9 a few lines take a different weight from Rhino 8's, because its hidden-line engine returns some edges differently: under 0.4 percent of the line length on the one real model tried.
- Intel Macs have only been run under Rosetta on an Apple silicon Mac. HL's tests also pass on GitHub's Intel runner.

Report a problem from the link at the bottom of HL's dialog, with the log attached.
