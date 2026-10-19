"""Render an SVG or PDF to PNG so it can be looked at.

  kit.py render FILE.svg|FILE.pdf [--out FILE.png] [--dpi 200] [--page N]

PDF: pdftoppm (poppler). SVG: rsvg-convert, then headless Chrome or Chromium, then cairosvg,
whichever is present; the renderer used is printed, since each draws hairlines differently. A
headless Chrome is stopped once its PNG is written, since some versions never exit.
"""
import importlib.util, os, shutil, subprocess, tempfile, time
from pathlib import Path

CHROMES = ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
           '/Applications/Chromium.app/Contents/MacOS/Chromium', 'google-chrome', 'chromium', 'chromium-browser']


def _svg_size(path):
    import re
    head = open(path, encoding='utf-8', errors='ignore').read(4000)
    m = re.search(r'viewBox="[\d.\-]+ [\d.\-]+ ([\d.]+) ([\d.]+)"', head)
    return (float(m.group(1)), float(m.group(2))) if m else (800.0, 600.0)


def svg_renderer():
    """what render uses for an SVG here: 'rsvg-convert', the path of a Chrome, 'cairosvg', or None"""
    if shutil.which('rsvg-convert'):
        return 'rsvg-convert'
    for c in CHROMES:
        exe = c if os.path.isabs(c) and os.path.exists(c) else shutil.which(c)
        if exe:
            return exe
    return 'cairosvg' if importlib.util.find_spec('cairosvg') else None


def static_faces(td):
    """the environment for rsvg-convert writing a PDF: pango on fontconfig, with a fonts.conf written in td that
    leaves out variable fonts (a file named with [wght] or VariableFont), since cairo embeds a variable font at its
    default instance (Source Sans 3's is ExtraLight) whatever weight the text asks for; with the static faces
    installed each weight embeds as its own face. The fonts.conf also reads the system's own"""
    conf = Path(td) / 'fonts.conf'
    conf.write_text('<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd"><fontconfig>'
                    + ''.join(f'<include ignore_missing="yes">{d}/fonts.conf</include>'
                              for d in ('/opt/homebrew/etc/fonts', '/usr/local/etc/fonts', '/etc/fonts'))
                    + '<selectfont><rejectfont><glob>*[wght]*</glob><glob>*VariableFont*</glob></rejectfont></selectfont>'
                    + '</fontconfig>', encoding='utf-8')
    return dict(os.environ, FONTCONFIG_FILE=str(conf), PANGOCAIRO_BACKEND='fc')


def render(src, out=None, dpi=200, page=1):
    src = Path(src).absolute()
    out = Path(out).absolute() if out else src.with_suffix('.png')
    if src.suffix.lower() == '.pdf':
        stem = str(out.with_suffix(''))
        subprocess.run(['pdftoppm', '-r', str(dpi), '-f', str(page), '-l', str(page), '-png', '-singlefile', str(src), stem], check=True)
        return out, 'pdftoppm'
    w, h = _svg_size(src)
    how = svg_renderer()
    if how == 'rsvg-convert':                           # -d and -p are the ppi a pt converts at; -z scales from 96
        subprocess.run(['rsvg-convert', '--unlimited', '-d', str(dpi), '-p', str(dpi), '-o', str(out), str(src)], check=True)
        return out, how
    if how == 'cairosvg':
        import cairosvg
        cairosvg.svg2png(url=str(src), write_to=str(out), dpi=dpi)
        return out, how
    if not how:
        raise SystemExit('no SVG renderer: install librsvg (brew install librsvg) or open the SVG in a browser')
    zoom = dpi / 72.0
    td = tempfile.mkdtemp()
    try:
        html = Path(td) / 'page.html'
        html.write_text(f'<html><body style="margin:0;background:#fff"><img src="{src.as_uri()}" '
                        f'style="width:{w}pt;height:{h}pt;display:block"></body></html>', encoding='utf-8')
        out.unlink(missing_ok=True)
        chrome = subprocess.Popen([how, '--headless', '--disable-gpu', '--hide-scrollbars', f'--force-device-scale-factor={zoom * 0.75:.3f}',
                                   f'--window-size={int(w * 4 / 3) + 1},{int(h * 4 / 3) + 1}', f'--screenshot={out}',
                                   f'--user-data-dir={td}/profile', html.as_uri()], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:                                            # chrome 153 on the mac writes the png and does not exit
            size, t0 = -1, time.time()
            while chrome.poll() is None and time.time() - t0 < 120:
                time.sleep(0.25)
                now = out.stat().st_size if out.exists() else -1
                if 0 < now == size:
                    break
                size = now
        finally:
            chrome.kill()
            chrome.wait()
    finally:
        shutil.rmtree(td, ignore_errors=True)        # chrome's helpers can still be writing its profile once it is killed
    if not out.exists():
        raise SystemExit(f'{os.path.basename(how)} wrote no PNG for {src}')
    return out, os.path.basename(how)


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    out = argv[argv.index('--out') + 1] if '--out' in argv else None
    dpi = int(argv[argv.index('--dpi') + 1]) if '--dpi' in argv else 200
    page = int(argv[argv.index('--page') + 1]) if '--page' in argv else 1
    path, how = render(argv[0], out, dpi, page)
    print(f'wrote {path} ({how})')
    return 0
