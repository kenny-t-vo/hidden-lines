"""The HL plug-in for Rhino 8: stages a Script Editor project (HL.rhproj) holding the HL command (HL.py) and, as its
one shared file, hl-kit.zip, the part of the kit the drawing runs on (a project's shared files lose their folders in
the Yak package, so the kit goes in whole and HL.py unpacks it), builds it into a .rhp with rhinocode, which needs
Rhino 8 running, then packs one Yak package a platform with the uv binaries given for it, so the drawing runs on uv's
Python 3.12 outside Rhino. Nothing is published by this script.

  python3 rhino/plugin/build.py OUT [--version 0.1.0] [--url URL] [--uv NAME=PATH ...] [--no-build]

NAME is uv-mac-arm64, uv-mac-x64 or uv-win-x64.exe (HL.py's UV), PATH a uv binary from Astral's releases for it.
The uv-mac binaries go into OUT/yak/hiddenlines-VERSION-rh8-mac.yak, the Windows one into -win.yak; with none, an
-any.yak whose drawing runs on Rhino's own Python. OUT keeps only yak/: the project (stage/) and rhinocode's build/
are removed once the packages are packed, each .yak holding the .rhp; --no-build leaves stage/ to look at. The
publisher is git's user.name and user.email; URL is the page the Package Manager links to."""
import json, shutil, subprocess, sys, uuid, zipfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
ID = '634a087f-cde2-425d-ac7b-76119ec43302'           # HL.py's PLUGIN_ID; a plug-in keeps its id for life
COMMAND_ID = 'e2821ea1-8569-4b8e-b939-56ff40092154'
SHARED = ['LICENSE', 'kit.py', 'kit.json', 'tokens.json', 'archkit', 'hiddenlines', 'adobe/illustrator/template',
          'rhino/hidden_lines.py', 'rhino/hl.py', 'rhino/plugin/compat']     # what kit.py hidden-lines and lint read
UV_NAMES = {'uv-mac-arm64': 'mac', 'uv-mac-x64': 'mac', 'uv-win-x64.exe': 'win'}
KEYWORDS = ['make2d', 'hidden-line', 'section', 'elevation', 'plan', 'axonometric', 'line-weight', 'architecture',
            'drawing', 'svg', 'dxf', 'illustrator']    # what people search the Package Manager for
DESCRIPTION = ('HL draws the visible and hidden lines of a Rhino model, as Make2D does, with line weights set by what '
               'each edge is, and adds the drawing to the model as layered curves. It also writes SVG, DXF and '
               'Illustrator files. It aims to be a better Make2D, not a finished drawing: faulty geometry draws as '
               'broken or doubled lines, which HL lists so you can fix the model, and some cleanup remains. The '
               'first run downloads Python 3.12 and its packages, about 700 MB.')
BIN = Path('/Applications/Rhino 8.app/Contents/Resources/bin')


def hl_repo():
    """HL's public repository, as rhino/hl.py names it"""
    import importlib.util
    spec = importlib.util.spec_from_file_location('hl_for_build', Path(__file__).resolve().parents[1] / 'hl.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.REPO


def files(rel):
    p = KIT / rel
    out = [p] if p.is_file() else sorted(q for q in p.rglob('*') if q.is_file())
    return [q for q in out if not q.name.startswith('.') and '__pycache__' not in q.parts]


def git(key):
    return subprocess.run(['git', '-C', str(KIT), 'config', key], capture_output=True, text=True).stdout.strip()


def arg(argv, flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


def main(argv):
    if not argv or argv[0].startswith('-'):
        sys.exit(__doc__)
    out = Path(argv[0]).expanduser().resolve()
    version = arg(argv, '--version', '0.1.0')
    uvs = dict(argv[i + 1].split('=', 1) for i, x in enumerate(argv) if x == '--uv')
    bad = [n for n, p in uvs.items() if n not in UV_NAMES or not Path(p).is_file()]
    if bad:
        sys.exit(f'--uv: {", ".join(bad)}: a name of {", ".join(UV_NAMES)} and a file')
    stage = out / 'stage'
    if stage.exists():
        shutil.rmtree(stage)
    (stage / 'commands').mkdir(parents=True)
    shutil.copy(KIT / 'rhino' / 'plugin' / 'HL.py', stage / 'commands' / 'HL.py')
    (stage / 'shared').mkdir()
    n = 0
    with zipfile.ZipFile(stage / 'shared' / 'hl-kit.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        for rel in SHARED:
            for f in files(rel):
                z.write(f, f.relative_to(KIT).as_posix())
                n += 1
    proj = dict(
        host=dict(name='Rhino3D', version='8', os='macOS', arch='arm64'),
        id=ID,
        identity=dict(name='HiddenLines', version=version,
                      publisher=dict(name=git('user.name'), email=git('user.email')),
                      description=DESCRIPTION, url=arg(argv, '--url', hl_repo())),
        settings=dict(buildPath='../build/',
                      buildTarget=dict(host=dict(name='Rhino3D', version='8'), title='Rhino3D (8.*)', slug='rh8'),
                      publishTarget=dict(title='McNeel Yak Server')),
        codes=[dict(id=COMMAND_ID, language={'id': '*.*.python', 'version': '3.*.*'}, title='HL', uri='commands/HL.py')],
        resources=[dict(id=str(uuid.uuid5(uuid.UUID(ID), 'shared/hl-kit.zip')), uri='shared/hl-kit.zip')])
    (stage / 'HL.rhproj').write_text(json.dumps(proj, indent=2))
    print(f'staged {n} files of the kit in {stage}/shared/hl-kit.zip')
    if '--no-build' in argv:
        return
    r = subprocess.run([str(BIN / 'rhinocode'), 'project', 'build', str(stage / 'HL.rhproj'), '--buildversion', version],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stdout[-2000:] + r.stderr[-2000:])
    built = out / 'build' / 'rh8'
    yaks = out / 'yak'
    if yaks.exists():
        shutil.rmtree(yaks)
    yaks.mkdir()
    for plat in sorted(set(UV_NAMES[n_] for n_ in uvs)) or ['any']:
        pkg = out / f'pkg-{plat}'
        if pkg.exists():
            shutil.rmtree(pkg)
        shutil.copytree(built, pkg, ignore=shutil.ignore_patterns('src', '*.yak'))
        man = (pkg / 'manifest.yml').read_text()
        man = man.replace('keywords:\n', 'keywords:\n' + ''.join(f'- {k}\n' for k in KEYWORDS), 1)
        (pkg / 'manifest.yml').write_text(man)
        for name, path in uvs.items():
            if UV_NAMES[name] == plat:
                shutil.copy(path, pkg / 'shared' / name)
        if plat != 'any':                              # uv's MIT and Apache notices go with the binary
            for lic in (KIT / 'rhino' / 'plugin' / 'uv-licenses').glob('LICENSE-*'):
                shutil.copy(lic, pkg / 'shared' / f'uv-{lic.name}')
        r = subprocess.run([str(BIN / 'yak'), 'build', '--platform', plat], cwd=pkg, capture_output=True, text=True)
        if r.returncode:
            sys.exit(r.stdout[-2000:] + r.stderr[-2000:])
        for y in pkg.glob('*.yak'):
            dst = yaks / y.name
            shutil.move(str(y), dst)
            print(f'{dst}: {dst.stat().st_size:,} bytes')
        shutil.rmtree(pkg)
    shutil.rmtree(stage)
    shutil.rmtree(out / 'build')


if __name__ == '__main__':
    main(sys.argv[1:])
