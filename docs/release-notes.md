HL 0.1.2: a sheet too big for Illustrator is drawn at a working scale instead of refused, and the dialog has two new options, Colours from the model and Only within. Models with long slanted lines, many separate lines or stacked faces draw faster, and a model 0.1.1 drew comes out the same, file for file, unless a new option is ticked.

- A sheet wider than the 5.8 m Illustrator takes, such as a large model at 1:1, is drawn as at the largest standard scale whose sheet fits A0, and the dialog says which. The drawing in Rhino and the DXF are at true size whatever the scale; no Illustrator or SVG file is saved for it. HL still refuses when one object lying far from the rest makes the sheet that big, and selects that object.
- **Colours from the model**, under Layers in the model: each line HL adds to Rhino takes the display and print colour of the object it came from. Print widths, linetypes, layers and fills stay HL's, and the saved files are unchanged.
- **Only within**, under Objects: objects lying wholly further than the distance you set are left out, neither drawn nor hiding anything. In perspective the distance is measured from the camera; in a parallel view, from the section or from the front of what is drawn. A standard or section view's sheet fits round the objects kept.
- The too-big message says the drawing in Rhino and the DXF are at true size whatever the scale, and suggests a print scale whose sheet fits A0.
- A face with no outer loop, which makes its object an invalid brep, no longer stops the export; the results window lists the object with the other invalid ones.
- The memory question before a large drawing counts the sheet's area, and HL builds its visibility buffer a tile at a time: for two triangles on a sheet 2.8 by 1.7 m, the buffer took 7.5 GB and now takes 0.14 GB.
- Drawing is faster in four places, with the same drawings. The visibility buffer runs on all the processor's cores, so a perspective section of 6.8 million triangles draws in 57 s instead of 67. 1,000 long slanted lines draw in 46 s instead of 773. 300,000 separate short lines take 8 s instead of 52 to find where lines meet, and 6,000 triangles stacked in one place draw in about 1.3 s instead of 10 to 13.

To update from 0.1.0 or 0.1.1, click Update for HiddenLines in the Package Manager and restart Rhino; HL keeps the Python and packages it downloaded and does not ask again. To install it, type `PackageManager` in Rhino 8, search for **HiddenLines**, click Install, and restart Rhino. Or download the package for your computer from the assets below:

- `hiddenlines-0.1.2-rh8_0-mac.yak`: a Mac, Apple silicon or Intel
- `hiddenlines-0.1.2-rh8_0-win.yak`: Windows 10 or 11

**Mac.** Double-click the file. Rhino 8 opens and installs it without showing a window; its command line says "Successfully installed HiddenLines". Quit Rhino and open it again.

**Windows.** In Rhino 8, type `-PackageManager`, choose Install, then Browse, and pick the file. Quit Rhino and open it again.

Then type `HL`: that is the command, and HiddenLines the package's name. The first time, it asks to download Python 3.12 and the packages the drawing runs on, about 700 MB, once. The [README](https://github.com/kenny-t-vo/hidden-lines#readme) is the full guide: drawing, the layer roles and line weights, the drawing's layers in Rhino, and what to do when something goes wrong.

Known issues:

- HL draws only what the model holds: an open solid, a face crossing itself or two objects overlapping come out as broken, doubled or missing lines. The results window lists those objects so you can fix them.
- Large models are slow to export. A model of about 3,300 objects and 6.8 million triangles takes 15 to 20 minutes to export the first time, less when the same objects are exported again, and about a minute to draw.
- The same export drawn on a Mac and on Windows matches to within 0.1 pt, not byte for byte, and a sliver of edge where two objects' cuts meet can take the neighbouring object's weight.
- Intel Macs have not been tested.

Report a problem from the link at the bottom of HL's dialog, with the log attached.
