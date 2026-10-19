#!/usr/bin/env python3
"""HL commands: hidden-lines REQUEST.json [--rhino OUT.json], lint FILE.svg|FILE.dxf, test."""
import importlib.util, json, os, shutil, sys
from pathlib import Path

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
KIT = Path(__file__).resolve().parent
sys.path.insert(0, str(KIT))
META = json.loads((KIT / 'kit.json').read_text(encoding='utf-8'))
NEEDS = {'hidden-lines': ['shapely', 'numpy', 'scipy', 'ezdxf', 'PIL', 'numba'],
         'lint': ['ezdxf'], 'test': ['shapely', 'numpy', 'scipy', 'ezdxf', 'PIL', 'numba']}


def ensure(cmd, argv):
    mods = NEEDS.get(cmd, [])
    missing = [m for m in mods if importlib.util.find_spec(m) is None]
    if not missing:
        return
    if os.environ.get('KIT_UV'):
        sys.exit(f'{cmd}: still missing {", ".join(missing)} under uv')
    uv = shutil.which('uv') or next((p for p in ('/opt/homebrew/bin/uv', '/usr/local/bin/uv',
                                                   os.path.expanduser('~/.local/bin/uv')) if os.path.exists(p)), None)
    if not uv:
        sys.exit(f'{cmd} needs {", ".join(missing)}: install uv (brew install uv) and rerun, '
                 f'or pip install {" ".join(missing)}')
    v = sys.version_info                           # shapely 2.1 needs 3.10; wheels lag the newest Pythons
    py = f'{v.major}.{v.minor}' if (3, 10) <= v < (3, 13) else META['python']
    pkgs = META['python_packages']
    args = [uv, 'run', '--quiet', '--no-project', '--python', py]
    for p in pkgs:
        args += ['--with', p]
    os.environ['KIT_UV'] = '1'
    if os.name == 'nt':                            # Windows' execv returns at once and splits arguments at spaces
        import subprocess
        sys.exit(subprocess.run(args + ['python', str(KIT / 'kit.py'), cmd] + argv).returncode)
    os.execv(uv, args + ['python', str(KIT / 'kit.py'), cmd] + argv)


def full_speed():
    if sys.platform != 'win32':
        return
    import ctypes
    try:
        class PowerThrottlingState(ctypes.Structure):
            _fields_ = [('Version', ctypes.c_uint32), ('ControlMask', ctypes.c_uint32),
                        ('StateMask', ctypes.c_uint32)]

        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.argtypes = []
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.SetProcessInformation.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
        kernel.SetProcessInformation.restype = ctypes.c_int
        # processpowerthrottling = 4; version 1, execution_speed controlled and off
        state = PowerThrottlingState(1, 1, 0)
        kernel.SetProcessInformation(kernel.GetCurrentProcess(), 4, ctypes.byref(state), ctypes.sizeof(state))
    except (AttributeError, OSError):
        pass


def main(argv):
    if not argv or argv[0] not in NEEDS:
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    ensure(cmd, rest)
    if cmd == 'hidden-lines':
        full_speed()
        from hiddenlines.hidden import main as draw
        return draw(rest)
    if cmd == 'lint':
        from archkit.lint import main as lint
        return lint(rest)
    import runpy
    runpy.run_path(str(KIT / 'tests' / 'run.py'), run_name='__main__')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
