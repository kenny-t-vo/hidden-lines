HL 0.1.1: the Package Manager shows HL's icon and says which command to type, and models of many objects draw faster. The drawings are the same as 0.1.0's.

- Rhino's Package Manager shows HL's icon beside HiddenLines.
- Its description says to type `HL` to run it.
- Placing each object on the page for the results window looked through every point of the drawing once for each object; it now sorts the points by object once. A test scene of 100,000 curves drew in 49 s instead of 90 s.

To update from 0.1.0, click Update for HiddenLines in the Package Manager and restart Rhino; HL keeps the Python and packages it downloaded and does not ask again. To install it, type `PackageManager` in Rhino 8, search for **HiddenLines**, click Install, and restart Rhino. Or download the package for your computer from the assets below:

- `hiddenlines-0.1.1-rh8_0-mac.yak`: a Mac, Apple silicon or Intel
- `hiddenlines-0.1.1-rh8_0-win.yak`: Windows 10 or 11

**Mac.** Double-click the file. Rhino 8 opens and installs it without showing a window; its command line says "Successfully installed HiddenLines". Quit Rhino and open it again.

**Windows.** In Rhino 8, type `-PackageManager`, choose Install, then Browse, and pick the file. Quit Rhino and open it again.

Then type `HL`: that is the command, and HiddenLines the package's name. The first time, it asks to download Python 3.12 and the packages the drawing runs on, about 700 MB, once. The [README](https://github.com/kenny-t-vo/hidden-lines#readme) is the full guide: drawing, the layer roles and line weights, the drawing's layers in Rhino, and what to do when something goes wrong.

Known issues:

- HL draws only what the model holds: an open solid, a face crossing itself or two objects overlapping come out as broken, doubled or missing lines. The results window lists those objects so you can fix them.
- Large models are slow. A model of about 3,300 objects and 6.8 million triangles takes 15 to 20 minutes to export the first time and about 2 minutes to draw; exporting the same objects again takes about 6.
- The same export drawn on a Mac and on Windows matches to within 0.1 pt, not byte for byte, and a sliver of edge where two objects' cuts meet can take the neighbouring object's weight.
- Intel Macs have not been tested.

Report a problem from the link at the bottom of HL's dialog, with the log attached.
