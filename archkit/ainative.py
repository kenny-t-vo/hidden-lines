"""Illustrator's own data inside an .ai file, read without Illustrator.

  kit.py ai FILE.ai [--json]      what the file holds, layer by layer: objects, anchors, marks and their weights,
                                  pattern fills and swatches, colour, opacity, symbols, images

An .ai saved with PDF compatibility is a PDF whose page carries Illustrator's art tree in AIPrivateData streams,
which join into one text: plain in old files, zlib after %AI12_CompressedData, Zstandard after %AI24_ZStandard_Data
(Illustrator 24 and later). A file that starts %!PS-Adobe is that text already (an Illustrator 8 file, or one the kit
wrote). The text is PostScript-like, an operator at the end of each line: m, l, c ... build a path and f, S, B ...
paint it (lower case closes it first); *u and *U bracket a compound path, u and U a group, q and Q a clip group; a
layer runs from %AI5_BeginLayer to %AI5_EndLayer with its flags on the Lb line and its name on the Ln line; p paints
with a pattern, (name) ... [a b c d tx ty] p. Type is /AI11Text in Illustrator 11 and later, its text in the text
engine's data; in a legacy (version 7) file, as VectorCraft and Rhino write one, it runs from 0 To (1 for area type, 2
on a path) to TO, its text on (string) Tx lines in Windows Latin-1. Lines starting %_ are the live source of objects
with an appearance (brushes, stacked fills, effects); the plain lines beside them are the rendering Illustrator writes,
which is what prints, so marks and weights are read from the plain lines and the %_ lines are counted as live objects. Each painted
path is also counted under its appearance (fill, stroke colour, weight and dash; a dot drawn as a zero-length stroke by its colour alone, since its weight is its size) in looks.

Writer puts a drawing into that text: layers and sublayers (hidden, locked or coloured as asked, and opened so),
named objects, K100 pattern swatches, pattern fills, global K100 colours painted at a tint (edit one in Illustrator
and every object painted with it follows), compound paths with holes and dots as zero-length round-capped strokes,
and artboards, spliced into a template Illustrator saved for its version (adobe/illustrator/Kit Template.jsx), so the
file opens as a normal document. Coordinates are page points, y up, from the document's ruler origin; a pattern fill's
matrix is in the same page points, the form Illustrator writes and reads back unchanged (tested in Illustrator 30.6,
24 September 2026; sublayers, hidden layers, layer colours and global colours on 28 September).
"""
import collections, json, math, mmap, re, zlib
from pathlib import Path

PAINT = frozenset(b'FfSsBbNn')
FILLS = frozenset(b'FfBb')
STROKES = frozenset(b'SsBb')
ANCHORS = {b'm', b'l', b'L', b'c', b'C', b'v', b'V', b'y', b'Y'}
BLOCKS = {b'%AI3_BeginPattern': b'%AI3_EndPattern', b'%AI8_BeginBrushPattern': b'%AI8_EndBrushPattern',
          b'%AI9_BeginArtStyles': b'%AI9_EndArtStyles', b'%AI9_BeginDocumentData': b'%AI9_EndDocumentData',
          b'%AI5_BeginPalette': b'%AI5_EndPalette', b'%AI11_BeginTextDocument': b'%AI11_EndTextDocument',
          b'%AI8_BeginPluginObject': b'%AI8_EndPluginObject', b'%%BeginProlog': b'%%EndProlog'}
DOT_PT = 1.5          # a filled closed path no wider than this is a dot
LEGACY_TO = re.compile(rb'[0-2] To')     # legacy (version 7) type: point, area or on a path, to TO
HEADER = [(b'AI9_ColorModel:', 'ColorModel'), (b'AI3_Cropmarks:', 'Cropmarks'), (b'AI5_NumLayers:', 'NumLayers'),
          (b'AI8_CreatorVersion:', 'CreatorVersion'), (b'HiResBoundingBox:', 'BoundingBox')]
TEMPLATE = Path(__file__).resolve().parent.parent / 'adobe' / 'illustrator' / 'template' / 'kit-template.ai'
LAYER_RGB = [(79, 128, 255), (255, 79, 79), (79, 255, 79), (79, 79, 255), (255, 255, 79), (255, 79, 255),
             (79, 255, 255), (153, 153, 255), (255, 153, 79), (0, 150, 0), (150, 0, 150), (128, 128, 128), (255, 0, 0)]


def _stream(mm, start):
    head_end = mm.find(b'stream', start)
    head = bytes(mm[start:head_end])
    s = head_end + 6
    s += 2 if mm[s:s + 2] == b'\r\n' else (1 if mm[s:s + 1] in (b'\n', b'\r') else 0)
    ln = re.search(rb'/Length (\d+)(\s+\d+\s+R)?', head)
    end = s + int(ln.group(1)) if ln and not ln.group(2) else mm.find(b'endstream', s)
    data = bytes(mm[s:end])
    return zlib.decompress(data) if b'/FlateDecode' in head else data


def _unpack(raw):
    if raw.startswith(b'%AI24_ZStandard_Data'):
        body = raw[len(b'%AI24_ZStandard_Data'):]
        try:
            from compression import zstd
            return zstd.decompress(body)
        except ImportError:
            import zstandard
            return zstandard.ZstdDecompressor().decompressobj().decompress(body)
    if raw.startswith(b'%AI12_CompressedData'):
        d = zlib.decompressobj()
        return d.decompress(raw[len(b'%AI12_CompressedData'):]) + d.flush()
    return raw


def native(path):
    """Illustrator's art tree for an .ai file, as bytes"""
    with open(path, 'rb') as fh:
        if fh.read(10).startswith(b'%!PS-Adobe'):
            fh.seek(0)
            return fh.read()
        mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            refs = sorted({(int(n), int(o)) for n, o in re.findall(rb'/AIPrivateData(\d+) (\d+) 0 R', mm)})
            if not refs:
                raise ValueError(f'{path}: no Illustrator data in it (not an .ai, or saved without PDF compatibility)')
            offs = {int(m.group(1)): m.end() for m in re.finditer(rb'(?:^|[\r\n])(\d+) 0 obj', mm)}
            raw = b''.join(_stream(mm, offs[o]) for _, o in refs)
        finally:
            mm.close()
    return _unpack(raw)


def lines(data):
    for m in re.finditer(rb'[^\r\n]+', data):
        yield m.group(0)


class Stats:
    __slots__ = ('paths', 'anchors', 'compounds', 'groups', 'clips', 'dots', 'separate_dots', 'marks', 'lines_',
                 'live_paths', 'live_anchors', 'symbols', 'text', 'rasters', 'placed', 'plugins', 'in_compound',
                 'opacity', 'patterns', 'widths', 'colours', 'looks')

    def __init__(self):
        for k in ('paths', 'anchors', 'compounds', 'groups', 'clips', 'dots', 'separate_dots', 'marks', 'lines_',
                  'live_paths', 'live_anchors', 'symbols', 'text', 'rasters', 'placed', 'plugins', 'in_compound'):
            setattr(self, k, 0)
        self.opacity = collections.Counter()
        self.patterns = collections.Counter()
        self.widths = collections.Counter()           # (kind, width or diameter in pt) -> count
        self.colours = collections.Counter()
        self.looks = collections.Counter()            # (fill, (stroke, weight, dash)) or ('dot', colour) -> painted paths; a colour is ('K', k), ('CMYK', c, m, y, k), ('RGB', r, g, b) or ('pattern', name)

    def add(self, o):
        for k in self.__slots__:
            v = getattr(o, k)
            if isinstance(v, collections.Counter):
                getattr(self, k).update(v)
            else:
                setattr(self, k, getattr(self, k) + v)

    def objects(self):
        """separate objects Illustrator holds: paths outside compound paths, compound paths, symbols, images, text"""
        return (self.paths - self.in_compound + self.compounds + self.symbols + self.rasters + self.placed + self.text
                + self.plugins)

    def as_dict(self):
        d = {k.rstrip('_'): getattr(self, k) for k in self.__slots__}
        d['objects'] = self.objects()
        for k in ('opacity', 'patterns', 'colours'):
            d[k] = dict(d[k])
        d['widths'] = [[k, w, n] for (k, w), n in sorted(d['widths'].items())]
        d['looks'] = sorted(([look_text(k), n] for k, n in self.looks.items()), key=lambda r: (-r[1], r[0]))
        return d


class Layer:
    def __init__(self, name, flags, parent):
        self.name, self.flags, self.parent = name, flags, parent
        self.kids, self.stats = [], Stats()
        f = flags.split()
        self.visible = bool(f) and f[0] == b'1'
        self.printing = len(f) > 3 and f[3] == b'1'
        self.locked = len(f) > 2 and f[2] == b'0'

    def path(self):
        out, L = [], self
        while L and L.parent:
            out.append(L.name)
            L = L.parent
        return '/'.join(reversed(out))

    def total(self):
        s = Stats()
        s.add(self.stats)
        for k in self.kids:
            s.add(k.total())
        return s


def _colour_text(c):
    return f'pattern "{c[1]}"' if c[0] == 'pattern' else f'{c[0]} ' + ' '.join(f'{v:g}' for v in c[1:])


def look_text(a):
    """an appearance (see census) in words: 'fill K 0 + stroke K 1 0.1 pt', 'stroke K 1 0.2 pt dash 1,2', 'dots K 1'"""
    if a[0] == 'dot':
        return f'dots {_colour_text(a[1])}'
    fill, stroke = a
    parts = ([_colour_text(fill) if fill[0] == 'pattern' else f'fill {_colour_text(fill)}'] if fill is not None else []) + \
            ([f'stroke {_colour_text(stroke[0])} {stroke[1]:g} pt' + (' dash ' + ','.join(f'{v:g}' for v in stroke[2]) if stroke[2] else '')]
             if stroke is not None else [])
    return ' + '.join(parts) or 'no fill, no stroke'


def _colour(op, body):
    """the colour an operator line sets: ('K', k) for K only, ('CMYK', c, m, y, k), ('RGB', r, g, b); None if it has too few numbers.
    A global colour's tint field is 1 minus the amount painted, as Writer writes it"""
    tok = body.split()
    if op in (b'Xk', b'XK'):
        v = _nums(tok[:4])
        after = _nums(body[body.rfind(b')') + 1:].split()[:1]) if b')' in body else []
        amount = 1 - after[0] if after else 1.0
        v = [x * amount for x in v]
    else:
        v = _nums(tok[:-1])
    if op in (b'g', b'G'):
        v = [0, 0, 0, 1 - v[0]] if v else v
    elif op in (b'Xa', b'XA'):
        # 'c m y k r g b Xa': Illustrator writes the colour's CMYK equivalent before its RGB, so RGB black is '0.75 0.68 0.67 0.9 0 0 0'
        return ('RGB',) + tuple(round(x, 3) + 0.0 for x in v[-3:]) if len(v) >= 3 else None
    if len(v) < 4:
        return None
    v = [round(x, 3) + 0.0 for x in v[:4]]
    return ('K', v[3]) if not any(v[:3]) else ('CMYK',) + tuple(v)


def _nums(tokens):
    out = []
    for t in tokens:
        try:
            out.append(float(t))
        except ValueError:
            pass
    return out


def census(src, mark_len=3.0):
    """what an .ai file (a path) or an art tree (bytes) holds, layer by layer"""
    data = native(src) if not isinstance(src, (bytes, bytearray)) else src
    root = Layer('(document)', b'1 1 1 1', None)
    cur = root
    head = {}
    pat_defs, brushes, symbol_names, placed_paths = {}, [], [], set()
    skip_until, pending_layer, plugin_next, in_symbols, pat_name, legacy_text = None, None, False, False, None, False
    width, cap, depth = 1.0, 0, 0
    fill_c = stroke_c = ('K', 1.0)                       # current colours; ('pattern', name) after p and P
    dash = ()
    length, first, last = 0.0, None, None
    lo_x = lo_y = math.inf
    hi_x = hi_y = -math.inf
    for n, ln in enumerate(lines(data)):
        if n < 400 and ln.startswith(b'%'):
            k = ln.lstrip(b'%')
            for key, name in HEADER:
                if k.startswith(key):
                    head[name] = k[len(key):].strip().decode('latin1')
        if skip_until is not None:
            if ln.startswith(skip_until):
                if skip_until == b'%AI3_EndPattern' and pat_name is not None:
                    pat_name = None
                skip_until = None
                continue
            if skip_until == b'%AI3_EndPattern' and pat_name is None and ln.startswith(b'('):
                m = re.match(rb'\((.*)\) (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)', ln)
                if m:
                    pat_name = m.group(1).decode('latin1')
                    x0, y0, x1, y1 = (float(m.group(k)) for k in range(2, 6))
                    pat_defs[pat_name] = {'tile': [round(x1 - x0, 2), round(y1 - y0, 2)], 'marks': 0, 'used': 0}
            elif skip_until == b'%AI3_EndPattern' and pat_name is not None:
                b = ln[2:] if ln.startswith(b'%_') else ln
                if b.endswith(b' m'):
                    pat_defs[pat_name]['marks'] += 1
            elif skip_until == b'%AI8_EndPluginObject' and plugin_next:
                if ln.startswith(b'('):
                    brushes.append(ln.strip(b'()').decode('latin1'))
                    plugin_next = False
            continue
        if in_symbols:
            if ln.startswith(b'%AI24_EndSymbolList'):
                in_symbols = False
            elif ln.startswith(b'('):
                symbol_names.append(ln[1:ln.rfind(b')')].replace(b'\\(', b'(').replace(b'\\)', b')').decode('latin1'))
            continue
        marker = ln[:1] == b'%' and ln[1:2] != b'_'
        if marker:
            if ln.startswith(b'%AI24_BeginSymbolList'):
                in_symbols = True
                continue
            started = next((k for k in BLOCKS if ln.startswith(k)), None)
            if started:
                skip_until = BLOCKS[started]
                plugin_next = started == b'%AI8_BeginPluginObject'
                if plugin_next and cur is not root:
                    cur.stats.plugins += 1
                pat_name = None
                continue
            if ln.startswith(b'%AI5_BeginLayer'):
                pending_layer = b''
                continue
        if pending_layer is not None:
            if ln.endswith(b' Lb'):
                pending_layer = ln[:-3]
                continue
            if ln.endswith(b') Ln'):
                raw_name = re.sub(rb'\\([0-7]{3}|.)', lambda m: bytes([int(m[1], 8)]) if len(m[1]) == 3 else m[1], ln[1:-4])
                name = raw_name[2:].decode('utf-16-be') if raw_name.startswith(b'\xfe\xff') else raw_name.decode('latin1')
                L = Layer(name, pending_layer, cur)
                cur.kids.append(L)
                cur = L
                pending_layer = None
                continue
        if marker and ln.startswith(b'%AI5_EndLayer'):
            cur = cur.parent or root
            continue
        if cur is root:                                  # definitions and settings, not art
            continue
        st = cur.stats
        if ln.startswith(b'%AI5_BeginRaster'):
            st.rasters += 1
            continue
        if ln.startswith(b'%AI5_BeginPlace') or ln.startswith(b'%_%AI5_BeginPlace'):
            continue
        if ln.startswith(b'%%IncludeFile:') or ln.startswith(b'%_%%IncludeFile:'):
            p = ln.split(b':', 1)[1].strip().decode('latin1')
            if p not in placed_paths:
                placed_paths.add(p)
                st.placed += 1
            continue
        hidden = ln.startswith(b'%_')
        body = ln[2:] if hidden else ln
        if legacy_text:
            legacy_text = body != b'TO'
            continue
        if not hidden and LEGACY_TO.fullmatch(body):
            st.text += 1
            legacy_text = True
            continue
        if body.startswith(b'/SymbolInstance'):
            st.symbols += 1
            continue
        if b'/AI11Text' in body and not hidden:
            st.text += 1
            continue
        if not body or body[:1] == b'%':
            continue
        sp = body.rfind(b' ')
        op = body[sp + 1:] if sp >= 0 else body
        if hidden:
            if op in ANCHORS:
                st.live_anchors += 1
            elif len(op) == 1 and op[0] in PAINT:
                st.live_paths += 1
            continue
        if op in ANCHORS:
            st.anchors += 1
            v = _nums(body.split()[:-1])
            if len(v) < 2:
                continue
            pts = list(zip(v[0::2], v[1::2]))
            if op == b'm':
                first = last = pts[0]
            elif last is not None:
                for p in pts:
                    length += math.hypot(p[0] - last[0], p[1] - last[1])
                    last = p
            for x, y in pts:
                lo_x, hi_x = min(lo_x, x), max(hi_x, x)
                lo_y, hi_y = min(lo_y, y), max(hi_y, y)
            continue
        if len(op) == 1 and op[0] in PAINT:
            st.paths += 1
            if depth:
                st.in_compound += 1
            c = op[0]
            size = max(hi_x - lo_x, hi_y - lo_y) if lo_x != math.inf else 0.0
            look = (fill_c if c in FILLS else None, (stroke_c, round(width, 3), dash) if c in STROKES else None)
            if c in STROKES and length < 1e-6 and cap == 1:
                look = ('dot', stroke_c)
                st.dots += 1
                st.widths[('dot', round(width, 3))] += 1
                if depth == 0:
                    st.separate_dots += 1
            elif c in FILLS and size <= DOT_PT and (c in b'fb' or (first == last)) and c not in STROKES \
                    and fill_c[0] != 'pattern' and fill_c != ('K', 0.0):     # a sliver of pattern or paper prints no dot
                st.dots += 1
                st.widths[('dot', round(size, 3))] += 1
                if depth == 0:
                    st.separate_dots += 1
            elif c in STROKES:
                kind = 'mark' if length < mark_len else 'line'
                if kind == 'mark':
                    st.marks += 1
                else:
                    st.lines_ += 1
                st.widths[(kind, round(width, 3))] += 1
            st.looks[look] += 1
            length, first, last = 0.0, None, None
            lo_x = lo_y = math.inf
            hi_x = hi_y = -math.inf
            continue
        if body == b'*u':
            st.compounds += 1
            depth += 1
            continue
        if body == b'*U':
            depth = max(0, depth - 1)
            continue
        if body == b'u':
            st.groups += 1
            continue
        if body == b'q':
            st.clips += 1
            continue
        if op in (b'p', b'P') and body.startswith(b'('):
            name = body[1:body.find(b')')].decode('latin1')
            st.patterns[name] += 1
            if op == b'p':
                fill_c = ('pattern', name)
            else:
                stroke_c = ('pattern', name)
            if name in pat_defs:
                pat_defs[name]['used'] += 1
            continue
        if op == b'Xy':
            v = body.split()
            try:
                o = float(v[1])
            except (IndexError, ValueError):
                continue
            if o < 1:
                st.opacity[round(o, 2)] += 1
            continue
        if op in (b'k', b'K', b'Xk', b'XK', b'Xa', b'XA', b'g', b'G'):
            col = _colour(op, body)
            if op in (b'k', b'Xk', b'Xa', b'g'):
                fill_c = col or fill_c
            else:
                stroke_c = col or stroke_c
            if op in (b'Xa', b'XA'):
                st.colours['RGB'] += 1
            elif op in (b'g', b'G'):
                st.colours['grey'] += 1
            else:
                v = _nums(body.split()[:4] if op in (b'Xk', b'XK') else body.split()[:-1])   # a global colour's c m y k (name) tint type
                if len(v) >= 4:
                    cmy = v[0] + v[1] + v[2]
                    st.colours['rich black' if v[3] >= 0.9 and cmy >= 0.3 else ('K only' if cmy == 0 else 'CMYK colour')] += 1
            continue
        if op == b'd':
            m = re.search(rb'\[([^\]]*)\]\s*[-\d.]+ d$', body)
            if m:
                dash = tuple(round(v, 3) + 0.0 for v in _nums(m.group(1).split()))
        toks = body.split()
        for i, t in enumerate(toks):
            if t == b'w' and i:
                try:
                    width = float(toks[i - 1])
                except ValueError:
                    pass
            elif t == b'J' and i:
                try:
                    cap = int(float(toks[i - 1]))
                except ValueError:
                    pass
    total = root.total()
    layers = []

    def walk(L, d):
        for k in L.kids:
            t = k.total()
            layers.append(dict(name=k.name, path=k.path(), depth=d, visible=k.visible, printing=k.printing,
                               locked=k.locked, own=k.stats.as_dict(), total=t.as_dict()))
            walk(k, d + 1)
    walk(root, 0)
    model = head.get('ColorModel', '').strip()
    return dict(header=dict(head, colour='RGB' if model == '1' else ('CMYK' if model == '2' else model or 'unknown')),
                layers=layers, totals=total.as_dict(), patterns=pat_defs, brushes=brushes,
                symbol_definitions=symbol_names, placed=sorted(placed_paths))


def summary(c):
    t = c['totals']
    h = c['header']
    top = [L for L in c['layers'] if L['depth'] == 0]
    out = [f'{h.get("CreatorVersion", "?")}; {h["colour"]}; {len(c["layers"])} layers ({len(top)} at the top)',
           f'objects: {t["paths"]:,} painted paths, {t["compounds"]:,} compound paths, {t["groups"]:,} groups, '
           f'{t["clips"]:,} clip groups, {t["symbols"]:,} symbol instances, {t["plugins"]} plug-in objects, {t["rasters"]} images, '
           f'{t["placed"]} linked files, {t["text"]} text objects',
           f'anchors: {t["anchors"]:,} drawn, {t["live_anchors"]:,} more in live sources of appearances',
           f'marks: {t["lines"]:,} lines, {t["marks"]:,} short marks, {t["dots"]:,} dots ({t["separate_dots"]:,} as separate objects)',
           f'swatches: {len(c["patterns"])} patterns, {sum(1 for p in c["patterns"].values() if p["used"] == 1)} used once; '
           f'{len(c["brushes"])} brush entries; {len(c["symbol_definitions"])} symbols defined']
    if t['opacity']:
        out.append('opacity under 100%: ' + ', '.join(f'{k} x{v}' for k, v in sorted(t['opacity'].items())))
    if t['colours']:
        out.append('colour operators: ' + ', '.join(f'{k} x{v}' for k, v in sorted(t['colours'].items())))
    out.append('layers in file order, the bottom one first (painted paths, anchors, dots):')
    for L in c['layers']:
        tt = L['total']
        flags = ('' if L['visible'] else ' hidden') + ('' if L['printing'] else ' non-printing') + (' locked' if L['locked'] else '')
        out.append(f'  {"  " * L["depth"]}{L["name"][:48]}{flags}: {tt["paths"]:,} / {tt["anchors"]:,} / {tt["dots"]:,}')
    return '\n'.join(out)


# ---------------------------------------------------------------- notes and artboards
def _ps_tokens(b):
    """tokens of the text engine's PostScript-like data: <<, >>, [, ], ('name', s), ('str', bytes), ('atom', s)"""
    i, n = 0, len(b)
    stop = b' \t\r\n/[]<>()'
    while i < n:
        c = b[i:i + 1]
        if c in b' \t\r\n':
            i += 1
        elif b[i:i + 2] in (b'<<', b'>>'):
            yield b[i:i + 2].decode()
            i += 2
        elif c in b'[]':
            yield c.decode()
            i += 1
        elif c == b'(':
            depth, j, out = 1, i + 1, bytearray()
            while j < n:
                ch = b[j]
                if ch == 0x5C and j + 1 < n:                     # a backslash takes the next byte as it is
                    out.append(b[j + 1])
                    j += 2
                    continue
                if ch == 0x28:
                    depth += 1
                elif ch == 0x29:
                    depth -= 1
                    if depth == 0:
                        break
                out.append(ch)
                j += 1
            yield ('str', bytes(out))
            i = j + 1
        else:
            j = i + 1
            while j < n and b[j:j + 1] not in stop:
                j += 1
            yield ('name', b[i + 1:j].decode('latin-1')) if c == b'/' else ('atom', b[i:j].decode('latin-1'))
            i = j


def _ps_parse(b):
    """the text engine's data as dicts, lists, bytes and strings; the top level is a run of keys and values"""
    toks = list(_ps_tokens(b))
    pos = 0

    def value():
        nonlocal pos
        t = toks[pos]
        pos += 1
        if t == '<<':
            d = {}
            while toks[pos] != '>>':
                k = toks[pos]
                pos += 1
                d[k[1] if isinstance(k, tuple) else k] = value()
            pos += 1
            return d
        if t == '[':
            out = []
            while toks[pos] != ']':
                out.append(value())
            pos += 1
            return out
        return t[1] if isinstance(t, tuple) else t
    top = {}
    while pos < len(toks):
        k = toks[pos]
        pos += 1
        top[k[1] if isinstance(k, tuple) else k] = value()
    return top


def _utf16(v):
    return v[2:].decode('utf-16-be', errors='replace') if isinstance(v, bytes) and v[:2] == b'\xfe\xff' else \
           (v.decode('latin-1') if isinstance(v, bytes) else str(v))


def legacy_string(b):
    """a PostScript string's bytes, escapes undone, as legacy type's Windows Latin-1"""
    out, i = bytearray(), 0
    while i < len(b):
        if b[i] == 0x5C and i + 1 < len(b):
            m = re.match(rb'[0-7]{1,3}', b[i + 1:i + 4])
            if m:
                out.append(int(m.group(0), 8) & 0xFF)
                i += 1 + len(m.group(0))
            else:
                out.append({0x6E: 10, 0x72: 13, 0x74: 9, 0x62: 8, 0x66: 12}.get(b[i + 1], b[i + 1]))
                i += 2
            continue
        out.append(b[i])
        i += 1
    return out.decode('cp1252', errors='replace')


def stories(data):
    """the text of every text object, by story index, from the file's text engine data"""
    import base64
    a = data.find(b'%AI11_BeginTextDocument')
    b = data.find(b'%AI11_EndTextDocument')
    if a < 0 or b < 0:
        return []
    body = b''.join(ln[1:] for ln in re.split(rb'\r\n|\r|\n', data[a:b])[2:] if ln.startswith(b'%'))
    end = body.find(b'~>')
    try:
        doc = _ps_parse(base64.a85decode(body[:end] if end >= 0 else body, adobe=False))
    except Exception:
        return []
    runs = doc.get('1', {}).get('1', []) if isinstance(doc.get('1'), dict) else []      # the stories, by index
    out = []
    for st in runs if isinstance(runs, list) else []:
        text = st.get('0', {}).get('0') if isinstance(st, dict) and isinstance(st.get('0'), dict) else None
        out.append(_utf16(text).replace('\r', '\n').strip() if text is not None else '')
    return out


def artboards(src):
    """the artboards: [(name, x0, y0, x1, y1)] in page points, y up"""
    data = native(src) if not isinstance(src, (bytes, bytearray)) else src
    a = data.find(b'(ArtboardArray)')
    s = data.rfind(b'%_/Array :', 0, a)
    out = []
    for blk in data[s:a].split(b'%_/Dictionary :')[1:]:
        p1 = re.search(rb'%_(-?[\d.]+) (-?[\d.]+) /RealPointRelToROrigin\s+%_ \(PositionPoint1\)', blk)
        p2 = re.search(rb'%_(-?[\d.]+) (-?[\d.]+) /RealPointRelToROrigin\s+%_ \(PositionPoint2\)', blk)
        nm = re.search(rb'%_\(((?:[^()\\\r\n]|\\.)*)\) /UnicodeString \(Name\)', blk)      # one entry: Illustrator 2026 puts the UUID first
        if p1 and p2:
            x0, y1 = float(p1.group(1)), float(p1.group(2))
            x1, y0 = float(p2.group(1)), float(p2.group(2))
            out.append((nm.group(1).decode('latin-1') if nm else '', min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
    if not out:                                          # a legacy (version 7) file: one artboard, unnamed, in its header
        num = rb' (-?[\d.]+)'
        tb = re.search(rb'%AI3_TemplateBox:' + num * 4, data[:65536])
        size = re.search(rb'%AI5_ArtSize:' + num * 2, data[:65536])
        if tb and size:            # ArtSize centred on the template box; Rhino writes no ArtSize, and its art isn't on its page
            cx, cy = (float(tb.group(1)) + float(tb.group(3))) / 2, (float(tb.group(2)) + float(tb.group(4))) / 2
            w, h = float(size.group(1)), float(size.group(2))
            out.append(('', cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))
    return out


def notes(src, layer='REVIEW'):
    """what a layer holds as review marks: its text objects (with their text) and its other paths, each with its
    bounds in page points: [{kind, text, bounds}]"""
    data = native(src) if not isinstance(src, (bytes, bytearray)) else src
    texts = stories(data)
    out = []
    found = False
    rows = re.split(rb'\r\n|\r|\n', data)
    i = 0
    while i < len(rows):
        if rows[i].startswith(b'%AI5_BeginLayer') and i + 2 < len(rows) and rows[i + 2] == b'(' + layer.encode() + b') Ln':
            found = True
            break
        i += 1
    if not found:
        return None
    depth, xs, ys, story, in_text, colour = 0, [], [], None, False, None
    legacy, runs, origin = False, [], None
    for ln in rows[i + 1:]:
        if ln.startswith(b'%AI5_BeginLayer'):
            depth += 1
        elif ln.startswith(b'%AI5_EndLayer'):
            if depth == 0:
                break
            depth -= 1
        if ln.startswith(b'%_'):
            continue
        m = re.match(rb'(-?[\d.]+) (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) K$', ln)
        if m:                                                    # a mark's stroke, CMYK
            colour = colour_name(*(float(v) for v in m.groups()))
            continue
        if ln == b'/AI11Text :':
            in_text, story, xs, ys = True, None, [], []
            continue
        if LEGACY_TO.fullmatch(ln):
            legacy, runs, origin, xs, ys = True, [], None, [], []
            continue
        if legacy and ln == b'TO':
            box = [min(xs), min(ys), max(xs), max(ys)] if xs else (list(origin) * 2 if origin else None)
            out.append(dict(kind='text', story=None, text=''.join(runs).replace('\r', '\n').strip(),
                            bounds=[round(v, 1) for v in box] if box else None))
            legacy, xs, ys = False, [], []
            continue
        if legacy and ln.endswith(b' Tp'):                       # a b c d x y: the type's origin, for point type
            v = _nums(ln.split()[:-1])
            origin = (v[4], v[5]) if len(v) >= 6 else None
            continue
        if legacy and ln.endswith(b') Tx'):
            runs.append(legacy_string(ln[ln.find(b'(') + 1:-4]))
            continue
        m = re.match(rb'(\d+) /StoryIndex ,', ln)
        if in_text and m:
            story = int(m.group(1))
            continue
        m = re.match(rb'(-?[\d.]+) (-?[\d.]+) [mLl]$', ln) or re.match(rb'.* (-?[\d.]+) (-?[\d.]+) [cCvVyY]$', ln)   # a curve ends on its last point
        if m:
            xs.append(float(m.group(1)))
            ys.append(float(m.group(2)))
            continue
        if in_text and ln == b'X+':
            box = [min(xs), min(ys), max(xs), max(ys)] if xs else None
            out.append(dict(kind='text', story=story, text=texts[story] if story is not None and story < len(texts) else '',
                            bounds=[round(v, 1) for v in box] if box else None))
            in_text, xs, ys = False, [], []
            continue
        if not in_text and not legacy and ln in (b'f', b'F', b's', b'S', b'b', b'B', b'n', b'N') and xs:
            out.append(dict(kind='path', text='', colour=colour,
                            bounds=[round(min(xs), 1), round(min(ys), 1), round(max(xs), 1), round(max(ys), 1)]))
            xs, ys = [], []
    return out


BLEND = {'normal': 0, 'multiply': 1}     # Xy's first operand, as Illustrator 30.6 reads it (multiply checked 5 October 2026)


def _cmyk(c):
    """a global colour's CMYK as the palette writes it: 0 0 0 1 for a K100 one"""
    return ' '.join(num(v) for v in (c if c is not True else (0, 0, 0, 1)))


def colour_name(c, m, y, k):
    """a CMYK colour as the word a reviewer would use for it: black, grey, white, or the nearest hue"""
    r, g, b = ((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))
    hi, lo = max(r, g, b), min(r, g, b)
    if hi < 0.25:
        return 'black'
    if hi - lo < 0.15:
        return 'white' if hi > 0.85 else 'grey'
    import colorsys
    h = colorsys.rgb_to_hsv(r, g, b)[0] * 360
    for top, name in ((15, 'red'), (45, 'orange'), (70, 'yellow'), (165, 'green'), (200, 'cyan'), (260, 'blue'),
                      (330, 'purple'), (361, 'red')):
        if h < top:
            return name


# ---------------------------------------------------------------- writing
def num(v):
    """a number as Illustrator's text wants it: at most four decimals, no trailing zeros"""
    t = f'{v:.4f}'.rstrip('0').rstrip('.')
    return '0' if t in ('', '-0') else t


def written(pts):
    """points as the file holds them, at num's four decimals, so a length measured on them is the one the census reads back"""
    return [(float(num(x)), float(num(y))) for x, y in pts]


def ps(s):
    """a PostScript string's body: ASCII, with parentheses and backslashes escaped"""
    return str(s).encode('ascii', 'replace').decode().replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def ps_layer(s):
    """unicode layer names use a UTF-16BE PostScript string with a byte-order mark"""
    return ps(s) if str(s).isascii() else ''.join(f'\\{v:03o}' for v in b'\xfe\xff' + str(s).encode('utf-16-be'))


def uid(s):
    """an object name as the XMLUID Illustrator writes for it"""
    return re.sub(r'[^A-Za-z0-9_.\-]', '_', str(s))


def _named(name):
    return [f'%_/ArtDictionary :', f'%_/XMLUID : ({ps(uid(name))}) ; (AI10_ArtUID) ,', '%_;', '%_'] if name else \
           ['%_/ArtDictionary :', '%_;', '%_']


def _ring_ops(pts, prefix=''):
    """a closed ring as m and L lines, the first point repeated at the end as Illustrator writes it"""
    pts = [(q[0], q[1]) for q in pts]                        # a z, where a source carries one, is dropped
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    out = [f'{prefix}{num(pts[0][0])} {num(pts[0][1])} m']
    out += [f'{prefix}{num(x)} {num(y)} L' for x, y in pts[1:]]
    out.append(f'{prefix}{num(pts[0][0])} {num(pts[0][1])} L')
    return len(pts), out


class Sheet:
    """a layer being written, and the sublayers written inside it"""

    def __init__(self, w, name, visible, printing, locked, rgb):
        self.w, self.name = w, name
        self.flags = (visible, printing, locked, rgb)
        self.out, self.kids = [], []
        self.swatch = None                              # the global colour its black strokes and fills take unless given one

    def _paint(self, fill, stroke, evenodd, dot=False):
        """the paint state before a path: fill ('k', K), ('k', K, swatch), ('c', [c, m, y, k], opacity, hex[, blend]) or ('p',
        pattern, matrix) or None; stroke a dict or None, its swatch a global colour's name. A swatch is a global K100
        colour painted at a tint of K, so editing it in Illustrator recolours every object painted with it; white (K 0)
        is plain. A 'c' fill is a process colour at an opacity from 0 to 1 (the key map's band, the one mark the
        standard lets under 100 percent). A line's K is the writer's hairline of its width and K; a dot's is as given"""
        o = ['0 O']
        if fill and fill[0] == 'c':
            o.append(' '.join(num(float(v)) for v in fill[1]) + ' k')
        elif fill and fill[0] == 'k':
            o.append(self.w.tint(fill[1], fill[2] if len(fill) > 2 else self.swatch, 'Xk', 'k'))
        elif fill and fill[0] == 'p':
            self.w.used.add(fill[1])
            o.append(f'({ps(fill[1])}) 0 0 1 1 0 0 0 0 0 [{" ".join(num(v) for v in fill[2])}] p')
        s = stroke or {}
        k = float(s['hair']) if stroke and not dot and s.get('hair') is not None else \
            self.w.hairline(float(s.get('w', 1)), float(s.get('k', 1))) if stroke and not dot else s.get('k', 1)
        opacity = float(fill[2]) if fill and fill[0] == 'c' else 1.0
        mode = BLEND.get(fill[4], 0) if fill and fill[0] == 'c' and len(fill) > 4 else 0
        o += ['0 R', self.w.tint(k, s.get('swatch') or self.swatch, 'XK', 'K'), f'{mode} {num(opacity)} 0 0 0 Xy',
              f'{s.get("cap", 0)} J {s.get("join", 0)} j {num(s.get("w", 1))} w {num(s.get("miter", 10))} M '
              f'[{" ".join(num(v) for v in s.get("dash", []))}]0 d', f'{1 if evenodd else 0} XR']
        return o

    @staticmethod
    def _op(fill, stroke, closed=True):
        if fill and stroke:
            return 'b' if closed else 'B'
        if fill:
            return 'f' if closed else 'F'
        if stroke:
            return 's' if closed else 'S'
        return 'n' if closed else 'N'

    def polygon(self, rings, fill=None, stroke=None, name=None):
        """a closed shape: rings[0] its outline, the rest holes; with holes it is a compound path, filled even-odd"""
        rings = [r for r in rings if len(r) >= 3]
        if not rings:
            return
        op = self._op(fill, stroke)
        paint = self._paint(fill, stroke, len(rings) > 1)
        if len(rings) == 1:
            n, ops = _ring_ops(rings[0])
            self.w.anchors += n
            self.out += [f'{n} As'] + paint + ops + [op] + _named(self.w.name(name))
            return
        self.out += ['0 Ae', '*u']
        for k, r in enumerate(rings):
            n, ops = _ring_ops(r)
            self.w.anchors += n
            self.out += [f'{n} As'] + (paint if k == 0 else []) + ops + [op]
        self.out += ['*U'] + _named(self.w.name(name))

    def line(self, pts, stroke, name=None, closed=False):
        """an open path, or a closed one with closed=True"""
        if closed:
            n, ops = _ring_ops(pts)
        else:
            n, ops = len(pts), [f'{num(pts[0][0])} {num(pts[0][1])} m'] + [f'{num(x)} {num(y)} L' for x, y in pts[1:]]
        self.w.anchors += n
        self.out += [f'{n} As'] + self._paint(None, stroke, False) + ops + [self._op(None, stroke, closed)] + \
                    _named(self.w.name(name))

    def strokes(self, paths, stroke, name=None):
        """several open paths as one compound path, stroked (a ring is given with its first point again at its end)"""
        paths = [p for p in paths if len(p) >= 2]
        if not paths:
            return
        self.out += ['0 Ae', '*u']
        for k, pts in enumerate(paths):
            n = len(pts)
            self.w.anchors += n
            self.out += [f'{n} As'] + (self._paint(None, stroke, False) if k == 0 else []) + \
                        [f'{num(pts[0][0])} {num(pts[0][1])} m'] + [f'{num(x)} {num(y)} L' for x, y in pts[1:]] + \
                        [self._op(None, stroke, False)]
        self.out += ['*U'] + _named(self.w.name(name))

    def curves(self, cubics, stroke, name=None, chunk=50000):
        """open cubics (p0, p1, p2, p3) as compound paths of at most chunk, stroked"""
        for c in range(0, len(cubics), chunk):
            part = cubics[c:c + chunk]
            self.out += ['0 Ae', '*u']
            for i, (p0, p1, p2, p3) in enumerate(part):
                self.out.append('2 As')
                if i == 0:
                    self.out += self._paint(None, stroke, False)
                self.out += [f'{num(p0[0])} {num(p0[1])} m',
                             f'{num(p1[0])} {num(p1[1])} {num(p2[0])} {num(p2[1])} {num(p3[0])} {num(p3[1])} c', 'S']
            self.w.anchors += 2 * len(part)
            self.out += ['*U'] + _named(self.w.name(name if len(cubics) <= chunk else f'{name}-{c // chunk + 1}'))

    def dots(self, pts, d, k=1.0, name=None, chunk=50000):
        """dots of diameter d as zero-length strokes with round caps, compound paths of at most chunk dots"""
        for c in range(0, len(pts), chunk):
            self.out += ['0 Ae', '*u']
            for i, (x, y) in enumerate(pts[c:c + chunk]):
                self.out.append('2 As')
                if i == 0:
                    self.out += self._paint(None, dict(k=k, w=d, cap=1, join=1, miter=4), False, dot=True)
                self.out += [f'{num(x)} {num(y)} m', f'{num(x)} {num(y)} L', 'S']
            self.w.anchors += 2 * len(pts[c:c + chunk])
            self.out += ['*U'] + _named(self.w.name(name if len(pts) <= chunk else f'{name}-{c // chunk + 1}'))

    def begin(self, name=None):
        """a group, closed by end()"""
        self.out += ['0 Ae', 'u']
        self._groups = getattr(self, '_groups', []) + [name]

    def end(self):
        self.out += ['U'] + _named(self.w.name(self._groups.pop()))

    def lines(self):
        """the layer's record: its own art, then each sublayer's whole record above it, before its LB, as Illustrator
        30.6 writes them. On the Lb line a hidden layer has 0 in the first and seventh places, and the eighth is the
        colour's index, -1 for the rgb after it (a preset's index overrides the rgb); a hidden layer adds 1 Xw and a
        locked one 1 A, as it writes them"""
        visible, printing, locked, rgb = self.flags
        v = int(visible)
        return (['%AI5_BeginLayer', f'{v} 1 {int(not locked)} {int(printing)} 0 0 {v} -1 {rgb[0]} {rgb[1]} {rgb[2]} 0 50 0 Lb',
                 f'({ps_layer(self.name)}) Ln', '0 AE'] + _named(self.w.name(self.name)) + (['1 A'] if locked else ['0 A'])
                + ([] if visible else ['1 Xw']) + ['0 Xw'] + (['0 A'] if locked else []) + self.out
                + [l for k in self.kids for l in k.lines()] + ['LB', '%AI5_EndLayer--'])


class Writer:
    """a drawing in Illustrator's own text, spliced into a template Illustrator saved; hairline(w, k) gives the black a
    line w pt wide at black k is written at (Tokens.hairline), the K given unless it is passed; dots keep theirs"""

    def __init__(self, template, hairline=None):
        text = native(template)
        self.t = [l.decode('latin-1') for l in re.split(rb'\r\n|\r|\n', text)]
        head = {l.split(':', 1)[0]: l.split(':', 1)[1].strip() for l in self.t[:60] if l.startswith('%%AI8_CreatorVersion')}
        self.version = head.get('%%AI8_CreatorVersion', '')
        ro = next((l for l in self.t if l.endswith('/RulerOrigin ,') and not l.startswith('%_')), None)
        if not ro:
            raise ValueError(f'{template}: no ruler origin; write the template again with Kit Template.jsx')
        self.origin = tuple(float(v) for v in ro.split()[:2])       # canvas point of page 0,0, y down
        self.patterns, self.used = {}, set()
        self.colours = {}                                           # global colours by name, in the order used: True for K100, else their [c, m, y, k] 0 to 1
        self.layers, self.boards = [], []
        self._names = collections.Counter()
        self.anchors = 0                                            # as written, counted as the census counts them
        self.hairline = hairline or (lambda w, k: k)

    def name(self, name):
        """a name made unique in the document, as Illustrator would make it"""
        if not name:
            return None
        self._names[name] += 1
        return name if self._names[name] == 1 else f'{name}-{self._names[name]}'

    def define(self, name, cmyk):
        """a global process colour of its own CMYK (0 to 1), so a stroke or fill naming it as its swatch takes that
        colour at its tint, and editing the swatch in Illustrator recolours them"""
        self.colours[name] = [float(v) for v in cmyk]

    def tint(self, k, swatch, named_op, plain_op):
        """K at k, as a tint of the global colour swatch where one is named: C M Y K (name) 1-tint 0 Xk, as
        Illustrator 30.6 writes a global process colour (0 0 0 1 for the K100 ones)"""
        if not swatch or k == 0:
            return f'0 0 0 {num(k)} {plain_op}'
        c = self.colours.setdefault(swatch, True)
        cmyk = ' '.join(num(v) for v in (c if c is not True else (0, 0, 0, 1)))
        return f'{cmyk} ({ps(swatch)}) {num(1 - k)} 0 {named_op}'

    def pattern(self, name, W, H, lines=(), curves=(), dots=(), fills=()):
        """a pattern swatch of W x H pt: lines [(pts, width)] of two points or more (a closed ring where the last
        point is the first), cubics [((p0, p1, p2, p3), width)], dots [(x, y, diameter)] and fills [[outline, hole,
        ...]], all K100 but a line or cubic the writer's hairline makes lighter; lines and cubics butt-capped, dots
        round-capped, each set one compound path; the fills one compound path filled even-odd, unstroked"""
        o = [f'%AI3_BeginPattern: ({ps(name)})', f'({ps(name)}) 0 0 {num(W)} {num(H)}', '%_0 A', '%_0 Xw', '%_0 Ae', '%_u',
             '%_4 As', '%_0 1 0 0 0 Xy', '%_0 J 0 j 1 w 10 M []0 d', '%_0 XR', '%_0 0 m', f'%_0 {num(H)} L',
             f'%_{num(W)} {num(H)} L', f'%_{num(W)} 0 L', '%_0 0 L', '%_n']

        def group(marks, cap, draw, anchors=lambda m: 2):
            by = collections.defaultdict(list)
            for m in marks:
                by[round(m[-1], 4)].append(m)
            for width, ms in sorted(by.items()):
                o.extend(['%_0 Ae', '%_*u'])
                for i, m in enumerate(ms):
                    o.append(f'%_{anchors(m)} As')
                    if i == 0:
                        o.extend(['%_0 R', f'%_0 0 0 {num(1.0 if cap else self.hairline(width, 1.0))} K',
                                  f'%_{cap} J 0 j {num(width)} w 4 M []0 d', '%_0 XR'])
                    o.extend(draw(m))
                o.extend(['%_*U'] + _named(None))
        closed = lambda m: len(m[0]) >= 4 and tuple(m[0][0]) == tuple(m[0][-1])
        group(lines, 0, lambda m: _ring_ops(m[0], '%_')[1] + ['%_s'] if closed(m) else
              [f'%_{num(m[0][0][0])} {num(m[0][0][1])} m'] + [f'%_{num(x)} {num(y)} L' for x, y in m[0][1:]] + ['%_S'],
              lambda m: len(m[0]) - 1 if closed(m) else len(m[0]))
        group(curves, 0, lambda m: [f'%_{num(m[0][0][0])} {num(m[0][0][1])} m',
                                    '%_' + ' '.join(num(v) for q in m[0][1:] for v in q) + ' c', '%_S'])
        group(dots, 1, lambda m: [f'%_{num(m[0])} {num(m[1])} m', f'%_{num(m[0])} {num(m[1])} L', '%_S'])
        rings = [r for f in fills for r in f if len(r) >= 3]
        if rings:
            o.extend(['%_0 Ae', '%_*u'])
            for i, r in enumerate(rings):
                n, ops = _ring_ops(r, '%_')
                o.append(f'%_{n} As')
                if i == 0:
                    o.extend(['%_0 O', '%_0 0 0 1 k', '%_0 R', '%_0 0 0 1 K', '%_0 1 0 0 0 Xy', '%_0 J 0 j 1 w 4 M []0 d', '%_1 XR'])
                o.extend(ops + ['%_f'])
            o.extend(['%_*U'] + _named(None))
        o += ['%_U'] + _named(None) + ['%_9 () XW', 'E', '%AI3_EndPattern']
        self.patterns[name] = o

    def layer(self, name, visible=True, printing=True, locked=False, rgb=(79, 128, 255), parent=None):
        """a layer above those made before it, or with parent (a layer this writer made) a sublayer of it, above the
        parent's other sublayers; only top layers count in the header"""
        L = Sheet(self, name, visible, printing, locked, rgb)
        (parent.kids if parent is not None else self.layers).append(L)
        return L

    def artboard(self, name, x0, y0, x1, y1):
        self.boards.append((name, min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))

    def _boards(self, title=''):
        import uuid
        rx, ry = self.origin
        out = []
        for i, (name, x0, y0, x1, y1) in enumerate(self.boards):
            aid = uuid.uuid5(uuid.NAMESPACE_URL, f'kit|{title}|{i}|{name}|{x0:.3f},{y0:.3f},{x1:.3f},{y1:.3f}')   # the same build writes the same bytes
            out += ['%_/Dictionary :', '%_0 /Int (DisplayMark) ,', f'%_{num(rx + x0)} {num(ry - y1)} /RealPoint', '%_ (RulerOrigin) ,',
                    f'%_{num(x1)} {num(y0)} /RealPointRelToROrigin', '%_ (PositionPoint2) ,',
                    f'%_{num(x0)} {num(y1)} /RealPointRelToROrigin', '%_ (PositionPoint1) ,',
                    f'%_({aid}) /String (ArtboardUUID) ,', '%_1 /Real (PAR) ,',
                    f'%_({ps(name)}) /UnicodeString (Name) ,', '%_0 /Bool (IsArtboardDefaultName) ,',
                    '%_0 /Bool (IsArtboardSelected) ,', '%_/FillStyle : 0 1 0 0 0 Xy', '%_0 J 0 j 1 w 10 M []0 d',
                    '%_0 XR', '%_0 0 Xd', '%_/Def ; ', '%_ (EachArtboardColor) ,', '%_0 /Bool (IsArtboardLocked) ,', '%_; ,']
        return out

    def text(self, title='drawing'):
        missing = self.used - set(self.patterns)
        if missing:
            raise ValueError(f'pattern fills name swatches never defined: {", ".join(sorted(missing))}')
        t = list(self.t)
        # the art: every template layer out, ours in
        a = next(i for i, l in enumerate(t) if l.startswith('%AI5_BeginLayer'))
        b = max(i for i, l in enumerate(t) if l.startswith('%AI5_EndLayer'))
        t[a:b + 1] = [l for L in self.layers for l in L.lines()]
        # artboards
        if self.boards:
            e = next(i for i, l in enumerate(t) if l.endswith('(ArtboardArray) ,'))
            s = max(i for i in range(e) if t[i] == '%_/Array :')
            t[s + 1:e] = self._boards(title)
        # swatches: pattern definitions after the plug-in list, then the palette
        pal = next(i for i, l in enumerate(t) if l == '%AI5_BeginPalette')
        pb = next(i for i in range(pal, len(t)) if t[i] == 'PB')
        entries = ['0 0 0 1 k', '(K100)', 'Pc'] + \
                  [x for n, c in self.colours.items() for x in (f'{_cmyk(c)} ({ps(n)}) 0 0 Xk', f'({ps(n)})', 'Pc')] + \
                  [x for n in self.patterns for x in (f'({ps(n)}) 0 0 1 1 0 0 0 0 0 [1 0 0 1 0 0] p', f'({ps(n)})', 'Pc')]
        t[pb:pb] = entries
        if self.colours:                                   # the header lists a document's global process colours
            dpc = next(i for i, l in enumerate(t) if l.startswith('%%DocumentProcessColors:'))
            t[dpc + 1:dpc + 1] = [('%%CMYKProcessColor: ' if i == 0 else '%%+ ') + f'{_cmyk(c)} ({ps(n)})'
                                  for i, (n, c) in enumerate(self.colours.items())]
        setup = next(i for i, l in enumerate(t) if l == '%%BeginSetup')
        after = next(i for i in range(setup, len(t)) if t[i].startswith('%AI5_End_NonPrinting'))
        t[after + 1:after + 1] = [l for n in self.patterns for l in self.patterns[n]]
        # the header
        box = self.boards[0][1:] if self.boards else (0, 0, 1000, 1000)
        allb = [b[1:] for b in self.boards] or [box]
        ux0, uy0 = min(b[0] for b in allb), min(b[1] for b in allb)
        ux1, uy1 = max(b[2] for b in allb), max(b[3] for b in allb)
        head = {'%%Title:': f'%%Title: ({ps(title)})', '%AI5_NumLayers:': f'%AI5_NumLayers: {len(self.layers)}',
                '%AI3_Cropmarks:': f'%AI3_Cropmarks: {num(box[0])} {num(box[1])} {num(box[2])} {num(box[3])}',
                '%%BoundingBox:': f'%%BoundingBox: {math.floor(ux0)} {math.floor(uy0)} {math.ceil(ux1)} {math.ceil(uy1)}',
                '%%HiResBoundingBox:': f'%%HiResBoundingBox: {num(ux0)} {num(uy0)} {num(ux1)} {num(uy1)}',
                '%AI3_ColorUsage:': '%AI3_ColorUsage: Color', '%%DocumentProcessColors:': '%%DocumentProcessColors: Black',
                # a digit a top layer, the top one first, or it quits: 1 shown, 2 previewed, 4 unlocked; the layer's
                # own Lb flags do not hide a top layer on opening, this does
                '%AI5_OpenViewLayers:': '%AI5_OpenViewLayers: ' + ''.join(
                    str(int(L.flags[0]) + 2 + (0 if L.flags[2] else 4)) for L in reversed(self.layers))}
        end = next(i for i, l in enumerate(t) if l == '%%EndComments')
        for i in range(end):
            for k, v in head.items():
                if t[i].startswith(k):
                    t[i] = v
        return ('\r'.join(t) + '\r').encode('latin-1')

    def save(self, path, title=None):
        from .project import place
        return place(self.text(title or Path(path).stem), path)


def main(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 2
    c = census(argv[0])
    if '--json' in argv:
        print(json.dumps(c, indent=1))
    else:
        print(summary(c))
    return 0
