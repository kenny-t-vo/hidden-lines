"""The kit, the project and the merged tokens.

The kit is the folder holding kit.json; this file sits inside it. A project is the nearest
folder, walking up from the file being worked on (or KIT_PROJECT, or the working folder),
that holds a tokens.json with an "extends" key. "extends" is "house", or the path of another
overlay (relative to the folder of the file naming it, "~" expanded), which extends another in turn
until one extends "house". The kit's tokens.json is merged first, then the farthest overlay, the
nearest last, so the nearest wins. Standard library only.
"""
import json, os, subprocess, tempfile, time
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
PT_PER_MM = 72.0 / 25.4
UNIT_MM = {'mm': 1.0, 'cm': 10.0, 'm': 1000.0, 'in': 25.4, 'ft': 304.8}
KEYS = ('id', 'name', 'scale')


def read_json(path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def find_overlay(start=None, name='tokens.json'):
    """nearest name (tokens.json, or a project's recipes.json) with an "extends" key at or above start, not the kit's own"""
    p = Path(start or os.environ.get('KIT_PROJECT') or os.getcwd()).absolute()
    if p.is_file():
        p = p.parent
    for d in [p] + list(p.parents):
        t = d / name
        if t.is_file() and d != KIT:
            try:
                if 'extends' in read_json(t):
                    return t
            except ValueError as e:                           # a project's settings would revert to the house's unseen
                raise SystemExit(f'{t}: not valid JSON ({e})')
            except OSError:
                pass
    return None


def _key(items):
    for k in KEYS:
        if items and all(isinstance(i, dict) and k in i for i in items):
            return k
    return None


PLACE = ('after', 'before')


def merge(base, over, path=''):
    """deep merge. Lists of dicts keyed by id, name or scale merge item by item: an item with
    "remove": true is dropped, and "after" or "before" naming another item's key puts a new item
    there, or moves an existing one. New items without either go at the end. Other lists replace.
    An item without the key of the list it merges into raises ValueError."""
    if isinstance(base, dict) and isinstance(over, dict):
        out = dict(base)
        for k, v in over.items():
            out[k] = merge(base[k], v, f'{path}.{k}' if path else k) if k in base else v
        return out
    if isinstance(base, list) and isinstance(over, list):
        k = _key(base) if base else _key(over)
        if k and over:
            bad = next((i for i in over if not isinstance(i, dict) or k not in i), None)
            if bad is not None:
                raise ValueError(f'{path}: {json.dumps(bad, ensure_ascii=False)} has no "{k}", so it cannot merge '
                                 'with the list it extends')
            out = [dict(i) for i in base]
            for item in over:
                idx = {i[k]: n for n, i in enumerate(out)}
                if item[k] in idx:
                    new = merge(out[idx[item[k]]], {x: v for x, v in item.items() if x not in PLACE})
                    if not any(x in item for x in PLACE):
                        out[idx[item[k]]] = new
                        continue
                    out.pop(idx[item[k]])
                    idx = {i[k]: n for n, i in enumerate(out)}
                else:
                    new = {x: v for x, v in item.items() if x not in PLACE}
                at = len(out)
                if item.get('after') in idx:
                    at = idx[item['after']] + 1
                elif item.get('before') in idx:
                    at = idx[item['before']]
                out.insert(at, new)
            return [i for i in out if not i.get('remove')]
        return over
    return over


def merge_chain(base, overlay):
    """base with the overlay at path overlay merged over it, and the overlays its "extends" leads to before it:
    (data, chain), chain the overlays' paths nearest first. ValueError names the file at fault."""
    overlay = Path(overlay)
    chain, overs, seen, f = [], [], {}, overlay
    while True:
        try:
            over = read_json(f)
        except ValueError as e:
            raise ValueError(f'{f}: not valid JSON ({e})' + (f'; {chain[-1]} extends it' if chain else ''))
        if chain and 'extends' not in over:
            raise ValueError(f'{chain[-1]}: "extends" names {f}, which has no "extends" key, so it is not an overlay; '
                             'write "house" to extend the house values')
        seen[f.resolve()] = f
        chain.append(f)
        overs.append(over)
        ext = over.get('extends')
        if ext == 'house':
            break
        if not isinstance(ext, str) or not ext:
            raise ValueError(f'{f}: "extends" must be "house" or the path of another overlay')
        up = Path(os.path.expanduser(ext))
        up = Path(os.path.normpath(up if up.is_absolute() else f.parent / up))
        if not up.is_file():
            raise ValueError(f'{f}: "extends" names {up}, which does not exist')
        if up.resolve() in seen:
            loop = chain[chain.index(seen[up.resolve()]):] + [seen[up.resolve()]]
            raise ValueError(f'{f}: "extends" makes a loop: {", ".join(map(str, loop))}')
        f = up
    data = base
    for f, over in reversed(list(zip(chain, overs))):
        try:
            data = merge(data, {k: v for k, v in over.items() if k != 'extends'})
        except ValueError as e:
            raise ValueError(f'{f}: {e}')
    return data, chain


class Tokens(dict):
    """merged tokens, with where they came from: overlay the nearest, chain every overlay merged, nearest first"""

    def __init__(self, data, overlay=None, chain=None):
        super().__init__(data)
        self.overlay = overlay
        self.project = overlay.parent if overlay else None
        self.chain = chain or ([overlay] if overlay else [])

    # ---- lookups
    def band(self, scale):
        for b in self['weights']['bands']:
            if b['to'] is None or scale <= b['to']:
                return b
        return self['weights']['bands'][-1]

    def profile(self, name=None):
        """an output profile: the device's floors for lines, marks and dots"""
        out = self['output']
        name = name or out['default']
        for p in out['profiles']:
            if p['name'] == name:
                return p
        raise KeyError(f'no output profile {name}; profiles: {", ".join(p["name"] for p in out["profiles"])}')

    def level(self, scale):
        """the texture level a drawing at this scale draws at"""
        for L in self['texture']['levels']:
            if L['to'] is None or scale <= L['to']:
                return L
        return self['texture']['levels'][-1]

    def weight(self, w, scale):
        if w is None:
            return None
        floor = self.profile()['line_min']
        if isinstance(w, (int, float)):
            return max(float(w), floor)
        return max(float(self.band(scale)[w]), floor)

    def hairline(self, w, k=1.0):
        """the black (0 to 1) a stroke w pt wide drawn at black k takes on the output profile's device: under 1.5 of
        its pixels (0.18 pt at 600 dpi), which stroke adjustment prints one pixel wide, no darker than the profile's
        hairline colour where it names one"""
        p = self.profile()
        if p.get('hairline') and float(w) < 108.0 / float(p['dpi']):
            return min(float(k), self['colors'][p['hairline']]['cmyk'][3] / 100)
        return float(k)

    def ink(self, name, w):
        """the colour a line w pt wide drawn in the colour name takes on the output profile's device: the profile's
        hairline colour for a black line hairline() makes lighter, else name"""
        c = self['colors'].get(name or '', {}).get('cmyk')
        if w and c and not any(c[:3]) and self.hairline(w, c[3] / 100) < c[3] / 100:
            return self.profile()['hairline']
        return name

    def hex(self, name):
        return self['colors'][name]['hex'] if name else None

    def layers(self, kind):
        return self['layers'][kind]

    def layer(self, kind, lid):
        for L in self['layers'][kind]:
            if L['id'] == lid:
                return L
        raise KeyError(f'no layer {lid} in layers.{kind}; add it to the tokens')

    def look(self, kind, lid, scale):
        """what a layer looks like at a scale: role values with the layer's own overrides, the weight no thinner than the
        output profile's line_min, and a black hairline in the profile's hairline colour"""
        L = self.layer(kind, lid)
        r = dict(self['roles'][L['role']])
        for k in ('stroke', 'fill', 'weight', 'dash', 'print', 'closed'):
            if k in L:
                r[k] = L[k]
        weight = self.weight(r.get('weight'), scale) if r.get('stroke') else None
        return dict(id=lid, role=L['role'], title=L.get('title', ''),
                    stroke=self.ink(r.get('stroke'), weight), fill=r.get('fill'),
                    weight=weight,
                    dash=self['dashes'][r['dash']] if r.get('dash') else None, dash_name=r.get('dash'),
                    print=r.get('print', True), closed=r.get('closed', False))

    def pstyle(self, name):
        by = {p['name']: p for p in self['paragraph_styles']}
        chain, cur = [], by[name]
        while cur:
            chain.append(cur)
            cur = by.get(cur.get('based_on'))
        out = {}
        for p in reversed(chain):
            out.update(p)
        return out


def tokens_hash(t):
    """sha1 of the merged tokens, notes included, so any change to them shows"""
    import hashlib
    return hashlib.sha1(json.dumps(t, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()[:12]


def stamp(folder, t, files, made_by):
    """made-from.json beside generated files: which tokens made them, so doctor can tell when they are stale"""
    data = dict(made_by=made_by, tokens=tokens_hash(t), overlay=str(t.overlay) if t.overlay else None,
                files=sorted(Path(f).name for f in files))
    return place(json.dumps(data, indent=1, ensure_ascii=False) + '\n', Path(folder) / 'made-from.json')


def load(start=None):
    base = read_json(KIT / 'tokens.json')
    ov = find_overlay(start)
    if not ov:
        return Tokens(base)
    try:
        data, chain = merge_chain(base, ov)
    except ValueError as e:
        raise SystemExit(str(e))
    return Tokens(data, ov, chain)


def place(data, dst):
    """write text or bytes to dst and read it back. The drive is exFAT, reached through a FUSE
    mount in Cowork: a truncating open from Python can fail there and a new file can read as
    missing for a second, so write a temp file, copy with cat, and retry the read. Windows has
    no sh and no FUSE, so it writes directly."""
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    raw = data.encode('utf-8') if isinstance(data, str) else data
    if os.name == 'nt':
        dst.write_bytes(raw)
        return dst
    fd, tmp = tempfile.mkstemp(suffix=dst.suffix)
    with os.fdopen(fd, 'wb') as fh:
        fh.write(raw)
    try:
        subprocess.run(['sh', '-c', 'cat "$0" > "$1"', tmp, str(dst)], check=True)
    finally:
        os.unlink(tmp)
    for _ in range(20):
        try:
            if dst.read_bytes() == raw:
                return dst
        except OSError:
            pass
        time.sleep(0.25)
    raise SystemExit(f'write did not read back: {dst}')
