#! python3
# venv: hl
# r: numpy==2.0.2
"""HL: the kit's hidden-line drawing of the open model (rhino/hidden_lines.py), run from the copy of the kit the
plug-in carries (shared/hl-kit.zip, unpacked once a version), the drawing through the uv it carries for this platform
(shared/uv-*), or on Rhino's own Python where it carries none"""
import os, platform, shutil, stat, time, zipfile
import System
import Rhino

PLUGIN_ID = '634a087f-cde2-425d-ac7b-76119ec43302'    # the plug-in's id for its whole life (build.py's rhproj)
UV = {('Darwin', 'arm64'): 'uv-mac-arm64', ('Darwin', 'x86_64'): 'uv-mac-x64', ('Windows', 'AMD64'): 'uv-win-x64.exe'}


def unpacked():
    """(the plug-in's kit, unpacked into ~/.rhinocode/kit-hl/kit/VERSION the first time this version runs; the uv it
    carries for this machine, or None; the plug-in's version)"""
    shared = os.path.join(os.path.dirname(Rhino.PlugIns.PlugIn.PathFromId(System.Guid(PLUGIN_ID))), 'shared')
    version = str(Rhino.PlugIns.PlugIn.Find(System.Guid(PLUGIN_ID)).Version)
    out = os.path.join(os.path.expanduser('~'), '.rhinocode', 'kit-hl', 'kit', version)
    kits = os.path.dirname(out)
    for old in (os.listdir(kits) if os.path.isdir(kits) else []):     # an unpack cut short, over ten minutes ago
        p = os.path.join(kits, old)
        if '.part-' in old and os.path.getmtime(p) < time.time() - 600:
            shutil.rmtree(p, ignore_errors=True)
    if not os.path.isdir(out):                         # unpacked whole beside it, then renamed: an unpack cut short
        part = '%s.part-%d' % (out, os.getpid())       # (Rhino quit) leaves no half kit to run from
        with zipfile.ZipFile(os.path.join(shared, 'hl-kit.zip')) as z:
            z.extractall(part)
        try:
            os.rename(part, out)
        except OSError:                                # another Rhino unpacked it first
            shutil.rmtree(part, ignore_errors=True)
        for old in os.listdir(kits):                   # the kits of earlier versions; one is unpacked again if needed
            if '.part-' not in old and old != version:
                shutil.rmtree(os.path.join(kits, old), ignore_errors=True)
    uv = os.path.join(shared, UV.get((platform.system(), platform.machine()), 'none'))
    if not os.path.isfile(uv):
        return out, None, version
    if os.name != 'nt' and not os.access(uv, os.X_OK):     # a zip keeps no execute bit
        os.chmod(uv, os.stat(uv).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return out, uv, version


def RunCommand():
    kit, uv, version = unpacked()
    script = os.path.join(kit, 'rhino', 'hidden_lines.py')
    ns = dict(__file__=script, __name__='hl_plugin', KIT_RUNTIME='uv' if uv else 'rhino', KIT_UV_BIN=uv,
              KIT_VERSION=version)
    exec(compile(open(script, encoding='utf-8').read(), script, 'exec'), ns)
    ns['alias']()
    return 0


if __name__ == '__main__':
    RunCommand()
