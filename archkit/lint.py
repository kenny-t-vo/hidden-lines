"""Check a drawing for the faults that break fills and look careless on paper.

  kit.py lint FILE.svg|FILE.dxf [--scale N] [--json]

errors (exit 1)
  open-cut     a path on a cut layer that is not closed, so it cannot take a fill or a hatch
  near-miss    a line end that stops short of, or overshoots onto, other linework by a hair:
               farther than lint.touch_mm (model) and nearer than lint.near_pt (paper); a path's own stretch
               until it first leaves the circle of near_pt round the end is not other linework
warnings
  stray        a path shorter than lint.min_len_pt on paper
  duplicate    two straight segments lying on top of each other, but a heavier cut drawn over a lighter cut's edge
  double       two lines running side by side between lint.touch_mm and lint.double_pt apart on paper, which print
               as one heavier line, for 3 pt or more summed over the pair (a line against itself too); five reported
               for a pair of layers, the rest counted; in a hidden-line drawing that keeps its doubles (its <desc>
               says doubles: kept, its DXF's KIT_DOUBLES), counted in one warning, as the model has them
  beside       in a hidden-line drawing (doubles kept or simplified), a line end within near_pt of lines that each run
               within 20 degrees of its own and lie to its side, not ahead: the model's double or converging line,
               counted in one warning, not a near miss
  weight       a stroke weight that is not the one the layer's role sets at this scale, or its sublayer's data-weight
               (a band name or pt) where a group inside the layer carries one (SVG)
  colour       a stroke or fill that is not a token colour (SVG); on a word sheet the word rules check colour
  label        a label box crossing linework (a label with a knockout, data-knockout in the SVG, crosses only
               the layers above its own, since it masks those beneath)
  role         a layer the tokens do not know and whose name carries no {role} tag
  unread       DXF entities lint does not read, so did not check (hatches are fills and are left out)
errors on a word sheet, which kit.py word writes with a <desc> saying so (archkit/word.py, lint)
  word-accent  a colour beside the greys on anything but words the diagram supplies or selects or an element of a
               class the sheet declares, in its colour (or a tint of it on a glyph or band); or two such colours on a
               sheet that declares no classes
  word-fill    a fill on anything but a bar, for a word withheld, a glyph, a band, or a dot
  word-heavy   more than one heavy line
  word-fn      a function word not in the text face's semibold at 7 pt, black and lower case
  word-family  an unquoted font family, which librsvg drops when a word of it starts with a digit

Only what prints through the drawing's window is checked: an SVG group's rectangle clip-path, or a DXF's KIT_CLIP
header (x0,y0,x1,y1 in model units), and a line end on the window's edge is not a drawn end.

A layer's role comes from, in order: data-role on an SVG group, the layer id in the tokens,
a {role} tag in the layer name, or a suggestion from role_words, each matched at the start of a
word (reported, not applied). Dimensions, marks, text and non-printing layers are skipped for
line-end checks. SVG styles come from attributes, class rules in <style>, then style attributes;
a length in px is a user unit.
"""
import json, math, re
from collections import defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET
from .project import load, PT_PER_MM, UNIT_MM

LINE_ROLES = {'cut', 'outline', 'accent', 'medium', 'light', 'fine', 'hidden', 'projection', 'existing', 'boundary', 'context'}
TAG = re.compile(r'\{([a-z]+)\}')


class Path2:
    """one drawn thing on paper: straight segments, whether closed, where it came from, the clip it prints through"""
    def __init__(self, layer, segs, closed, kind, src, width=None, stroke=None, fill=None, clip=None, want=None):
        self.layer, self.segs, self.closed, self.kind, self.src = layer, segs, closed, kind, src
        self.width, self.stroke, self.fill, self.clip = width, stroke, fill, clip
        self.want = want                                # the weight its sublayer sets (data-weight), a band or pt

    def ends(self):
        if self.closed or not self.segs:
            return []
        return [self.segs[0][0], self.segs[-1][1]]

    def length(self):
        return sum(math.dist(a, b) for a, b in self.segs)


# ---------------------------------------------------------------- readers

def _percent(el):
    return any(str(el.get(k, '')).strip().endswith('%') for k in ('x', 'y', 'width', 'height'))

def text_width(txt, size, spacing=0.0):
    """a label's width on paper: capitals at 0.62 em and the rest at 0.5, which covers the house sans
    with a little to spare, plus letter-spacing. Illustrator's own bounds, read by Audit Linework,
    are exact."""
    return sum(0.62 if ch.isupper() or ch.isdigit() else 0.5 for ch in txt) * size + spacing * len(txt)


def _mat_mul(a, b):
    return (a[0] * b[0] + a[2] * b[1], a[1] * b[0] + a[3] * b[1], a[0] * b[2] + a[2] * b[3],
            a[1] * b[2] + a[3] * b[3], a[0] * b[4] + a[2] * b[5] + a[4], a[1] * b[4] + a[3] * b[5] + a[5])


def _parse_transform(s):
    m = (1, 0, 0, 1, 0, 0)
    for name, args in re.findall(r'(\w+)\s*\(([^)]*)\)', s or ''):
        v = [float(x) for x in re.split(r'[\s,]+', args.strip()) if x]
        if name == 'matrix':
            t = tuple(v)
        elif name == 'translate':
            t = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == 'scale':
            t = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == 'rotate':
            a = math.radians(v[0])
            r = (math.cos(a), math.sin(a), -math.sin(a), math.cos(a), 0, 0)
            if len(v) == 3:
                t = _mat_mul(_mat_mul((1, 0, 0, 1, v[1], v[2]), r), (1, 0, 0, 1, -v[1], -v[2]))
            else:
                t = r
        else:
            continue
        m = _mat_mul(m, t)
    return m


def _ap(m, p):
    return (m[0] * p[0] + m[2] * p[1] + m[4], m[1] * p[0] + m[3] * p[1] + m[5])


def _arc_pts(x1, y1, rx, ry, phi, fa, fs, x2, y2, n=12):
    """svg endpoint arc to points (spec F.6.5)"""
    if rx == 0 or ry == 0:
        return [(x2, y2)]
    cp, sp = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p, y1p = cp * dx + sp * dy, -sp * dx + cp * dy
    lam = (x1p ** 2) / rx ** 2 + (y1p ** 2) / ry ** 2
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx ** 2 * ry ** 2 - rx ** 2 * y1p ** 2 - ry ** 2 * x1p ** 2
    den = rx ** 2 * y1p ** 2 + ry ** 2 * x1p ** 2
    co = math.sqrt(max(0, num / den)) * (-1 if fa == fs else 1)
    cxp, cyp = co * rx * y1p / ry, -co * ry * x1p / rx
    cx, cy = cp * cxp - sp * cyp + (x1 + x2) / 2, sp * cxp + cp * cyp + (y1 + y2) / 2
    ang = lambda u, v: math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1])
    t1 = ang((1, 0), ((x1p - cxp) / rx, (y1p - cyp) / ry))
    dt = ang(((x1p - cxp) / rx, (y1p - cyp) / ry), ((-x1p - cxp) / rx, (-y1p - cyp) / ry))
    if not fs and dt > 0:
        dt -= 2 * math.pi
    elif fs and dt < 0:
        dt += 2 * math.pi
    out = []
    for i in range(1, n + 1):
        t = t1 + dt * i / n
        out.append((cx + rx * math.cos(t) * cp - ry * math.sin(t) * sp, cy + rx * math.cos(t) * sp + ry * math.sin(t) * cp))
    out[-1] = (x2, y2)
    return out


def _path_subpaths(d):
    """svg path data to [(points, closed)], curves sampled"""
    toks = re.findall(r'[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?', d)
    i, cmd, cur, start, subs, pts = 0, None, (0.0, 0.0), (0.0, 0.0), [], []

    def flush(closed):
        if len(pts) > 1:
            subs.append((list(pts), closed))
    while i < len(toks):
        if re.match(r'[A-Za-z]', toks[i]):
            cmd = toks[i]
            i += 1
            if cmd in 'Zz':
                flush(True)
                pts.clear()
                cur = start
                continue
        rel = cmd.islower()
        c = cmd.upper()
        if c == 'M':
            x, y = float(toks[i]), float(toks[i + 1])
            i += 2
            if rel:
                x, y = cur[0] + x, cur[1] + y
            flush(False)
            pts.clear()
            cur = start = (x, y)
            pts.append(cur)
            cmd = 'l' if rel else 'L'
        elif c in 'LT':
            x, y = float(toks[i]), float(toks[i + 1])
            i += 2
            cur = (cur[0] + x, cur[1] + y) if rel else (x, y)
            pts.append(cur)
        elif c == 'H':
            x = float(toks[i])
            i += 1
            cur = (cur[0] + x if rel else x, cur[1])
            pts.append(cur)
        elif c == 'V':
            y = float(toks[i])
            i += 1
            cur = (cur[0], cur[1] + y if rel else y)
            pts.append(cur)
        elif c in 'CSQ':
            n = {'C': 6, 'S': 4, 'Q': 4}[c]
            v = [float(t) for t in toks[i:i + n]]
            i += n
            if rel:
                v = [v[j] + (cur[0] if j % 2 == 0 else cur[1]) for j in range(n)]
            ctrl = [(v[j], v[j + 1]) for j in range(0, n - 2, 2)]
            end = (v[-2], v[-1])
            p0 = cur
            ctrls = [p0] + ctrl + [end]
            for s in range(1, 9):
                t = s / 8
                q = ctrls
                while len(q) > 1:
                    q = [((1 - t) * a[0] + t * b[0], (1 - t) * a[1] + t * b[1]) for a, b in zip(q, q[1:])]
                pts.append(q[0])
            pts[-1] = end
            cur = end
        elif c == 'A':
            rx, ry, phi, fa, fs, x, y = [float(t) for t in toks[i:i + 7]]
            i += 7
            if rel:
                x, y = cur[0] + x, cur[1] + y
            pts.extend(_arc_pts(cur[0], cur[1], abs(rx), abs(ry), phi, int(fa), int(fs), x, y))
            cur = (x, y)
        else:
            i += 1
    flush(False)
    return subs


STYLE_KEYS = ('stroke', 'stroke-width', 'fill', 'display', 'font-size', 'letter-spacing', 'text-anchor')


def _decls(css):
    out = {}
    for part in (css or '').split(';'):
        if ':' in part:
            k, v = part.split(':', 1)
            if k.strip() in STYLE_KEYS:
                out[k.strip()] = v.strip()
    return out


def _style(el, inherited, classes=None):
    s = dict(inherited)
    for k in STYLE_KEYS:
        if el.get(k) is not None:
            s[k] = el.get(k)
    for c in (el.get('class') or '').split():
        s.update((classes or {}).get(c, {}))
    s.update(_decls(el.get('style')))
    return s


def _len(v):
    """an svg length in user units: a bare number or px; None for any other unit"""
    m = re.fullmatch(r'\s*([-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?)(?:px)?\s*', str(v))
    return float(m.group(1)) if m else None


def _hex6(c):
    """#abc as #aabbcc, in lower case"""
    c = c.strip().lower()
    return '#' + ''.join(ch * 2 for ch in c[1:]) if len(c) == 4 else c


def _clip_seg(a, b, r):
    """the part of segment ab inside the rectangle r = (x0, y0, x1, y1), or None (Liang-Barsky)"""
    t0, t1, dx, dy = 0.0, 1.0, b[0] - a[0], b[1] - a[1]
    for p, q in ((-dx, a[0] - r[0]), (dx, r[2] - a[0]), (-dy, a[1] - r[1]), (dy, r[3] - a[1])):
        if p == 0:
            if q < 0:
                return None
        elif p < 0:
            t0 = max(t0, q / p)
        else:
            t1 = min(t1, q / p)
        if t0 > t1:
            return None
    return (a[0] + t0 * dx, a[1] + t0 * dy), (a[0] + t1 * dx, a[1] + t1 * dy)


def _text_box(at, w, cap, fx, fy, rot):
    """paper corners of a label w wide and cap high whose anchor, at, sits fx along it and fy up it, turned rot degrees"""
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    x0, x1, top, base = -fx * w, (1 - fx) * w, cap * fy - cap, cap * fy
    return [(at[0] + dx * c + dy * s, at[1] - dx * s + dy * c) for dx, dy in ((x0, top), (x1, top), (x1, base), (x0, base))]


def read_svg(path):
    root = ET.parse(path).getroot()
    ns = lambda tag: tag.split('}')[-1]
    meta = {}
    for el in root:
        if ns(el.tag) == 'desc' and el.text:
            try:
                meta = json.loads(el.text)
            except ValueError:
                pass
    paths, texts, layer_roles, classes, clips, order = [], [], {}, {}, {}, {}
    for el in root.iter():
        if ns(el.tag) == 'style' and el.text:
            for sel, body in re.findall(r'([^{}]+)\{([^}]*)\}', re.sub(r'/\*.*?\*/', '', el.text, flags=re.S)):
                for s in sel.split(','):
                    if re.fullmatch(r'\s*\.[\w-]+\s*', s):
                        classes.setdefault(s.strip()[1:], {}).update(_decls(body))
        if ns(el.tag) == 'clipPath':                    # a rectangle clip, as a map's window
            r = next((c for c in el if ns(c.tag) == 'rect'), None)
            if r is not None and not _percent(r):
                x, y, ww, hh = (float(r.get(k, 0)) for k in ('x', 'y', 'width', 'height'))
                clips[el.get('id')] = ((x, y), (x + ww, y + hh))

    def walk(el, m, style, layer, clip=None, want=None):
        tag = ns(el.tag)
        m = _mat_mul(m, _parse_transform(el.get('transform')))
        style = _style(el, style, classes)
        ref = re.fullmatch(r'\s*url\(#([^)]+)\)\s*', el.get('clip-path') or '')
        if ref and ref.group(1) in clips:
            a, b = (_ap(m, p) for p in clips[ref.group(1)])
            clip = (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))
        if style.get('display') == 'none':
            return
        if tag == 'g':
            name = el.get('{http://www.inkscape.org/namespaces/inkscape}label') or el.get('data-name') or el.get('id')
            if layer is None and name:
                layer = name
                order.setdefault(layer, len(order))
                if el.get('data-role'):
                    layer_roles[layer] = el.get('data-role')
            elif el.get('data-weight'):                 # a sublayer of one weight
                want = el.get('data-weight')
            for ch in el:
                walk(ch, m, style, layer, clip, want)
            return
        if tag in ('defs', 'clipPath', 'title', 'desc', 'metadata', 'style'):
            return
        w = _len(style.get('stroke-width'))
        sub = []
        if tag == 'path':
            sub = _path_subpaths(el.get('d', ''))
        elif tag == 'line':
            sub = [([(float(el.get('x1', 0)), float(el.get('y1', 0))), (float(el.get('x2', 0)), float(el.get('y2', 0)))], False)]
        elif tag in ('polyline', 'polygon'):
            v = [float(x) for x in re.split(r'[\s,]+', (el.get('points') or '').strip()) if x]
            sub = [([(v[j], v[j + 1]) for j in range(0, len(v) - 1, 2)], tag == 'polygon')]
        elif tag == 'rect':
            if _percent(el):                            # a page background sized in percent, as previews write
                sub = []
            else:
                x, y, ww, hh = (float(el.get(k, 0)) for k in ('x', 'y', 'width', 'height'))
                sub = [([(x, y), (x + ww, y), (x + ww, y + hh), (x, y + hh)], True)]
        elif tag in ('circle', 'ellipse'):
            cx, cy = float(el.get('cx', 0)), float(el.get('cy', 0))
            rx = float(el.get('r') or el.get('rx') or 0)
            ry = float(el.get('r') or el.get('ry') or 0)
            sub = [([(cx + rx * math.cos(2 * math.pi * i / 24), cy + ry * math.sin(2 * math.pi * i / 24)) for i in range(24)], True)]
        elif tag == 'text':
            if el.get('data-knockout') == 'halo':          # a label's paper halo, not a label
                return
            txt = ''.join(el.itertext())
            size = _len(style.get('font-size', 6)) or 6
            anchor = style.get('text-anchor', 'start')
            x, y = float(el.get('x', 0)), float(el.get('y', 0))
            wdt = text_width(txt, size, _len(style.get('letter-spacing', 0)) or 0)
            x0 = x - (wdt / 2 if anchor == 'middle' else wdt if anchor == 'end' else 0)
            corners = [_ap(m, p) for p in ((x0, y - 0.7 * size), (x0 + wdt, y - 0.7 * size), (x0 + wdt, y), (x0, y))]
            texts.append(dict(layer=layer, text=txt, box=corners, masks=el.get('data-knockout') is not None))
            return
        for pts, closed in sub:
            pts = [_ap(m, p) for p in pts]
            if closed and pts[0] != pts[-1]:
                pts = pts + [pts[0]]
            segs = [(a, b) for a, b in zip(pts, pts[1:]) if a != b]
            if clip:                                    # only what prints through the clip is checked
                segs = [s for s in (_clip_seg(a, b, clip) for a, b in segs) if s and s[0] != s[1]]
            if segs:
                scale_m = math.sqrt(abs(m[0] * m[3] - m[1] * m[2]))
                paths.append(Path2(layer, segs, closed, tag, el.get('id', ''), w * scale_m if w is not None else None,
                                   style.get('stroke'), style.get('fill'), clip, want))
        for ch in el:
            walk(ch, m, style, layer, clip, want)

    walk(root, (1, 0, 0, 1, 0, 0), {}, None)
    scale = float(meta['scale'].split(':')[1]) if meta.get('scale') else None
    return dict(paths=paths, texts=texts, roles=layer_roles, scale=scale, k=1.0, units='pt', order=order,
                kind=meta.get('kind'), doubles=meta.get('doubles'))


def read_dxf(path, scale):
    import ezdxf
    from ezdxf import path as dxfpath
    doc = ezdxf.readfile(path)
    units = {1: 'in', 2: 'ft', 4: 'mm', 5: 'cm', 6: 'm'}.get(doc.units, 'mm')
    if scale is None:
        try:
            scale = float(doc.header.custom_vars.get('KIT_SCALE'))
        except (TypeError, ValueError):
            scale = None
    if scale is None:
        raise SystemExit('this DXF carries no scale; give --scale N')
    k = PT_PER_MM * UNIT_MM[units] / scale
    paths, texts, unread = [], [], defaultdict(int)
    P = lambda v: (v[0] * k, -v[1] * k)

    def add(e, lay):
        t = e.dxftype()
        if t == 'LINE':
            paths.append(Path2(lay, [(P(e.dxf.start), P(e.dxf.end))], False, t, e.dxf.handle))
        elif t in ('LWPOLYLINE', 'SPLINE', 'ELLIPSE'):
            if t == 'LWPOLYLINE' and not e.has_arc:
                pts = [P(p) for p in e.get_points('xy')]
                closed = bool(e.closed)
                if closed:
                    pts.append(pts[0])
            else:                                               # arcs and curves, flattened to within 0.1 pt on paper
                pts = [P(v) for v in dxfpath.make_path(e).flattening(0.1 / k)]
                closed = (math.isclose(abs(e.dxf.end_param - e.dxf.start_param), math.tau, abs_tol=1e-6) if t == 'ELLIPSE'
                          else bool(e.closed))
            segs = [(a, b) for a, b in zip(pts, pts[1:]) if a != b]
            if segs:
                paths.append(Path2(lay, segs, closed, t, e.dxf.handle))
        elif t == 'POLYLINE':
            pts = [P(v.dxf.location) for v in e.vertices]
            closed = e.is_closed
            if closed:
                pts.append(pts[0])
            segs = [(a, b) for a, b in zip(pts, pts[1:]) if a != b]
            if segs:
                paths.append(Path2(lay, segs, closed, t, e.dxf.handle))
        elif t in ('ARC', 'CIRCLE'):
            c, r = e.dxf.center, e.dxf.radius
            a0, a1 = (math.radians(e.dxf.start_angle), math.radians(e.dxf.end_angle)) if t == 'ARC' else (0, 2 * math.pi)
            if a1 <= a0:
                a1 += 2 * math.pi
            n = max(8, int((a1 - a0) / (math.pi / 12)))
            pts = [P((c[0] + r * math.cos(a0 + (a1 - a0) * i / n), c[1] + r * math.sin(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
            paths.append(Path2(lay, list(zip(pts, pts[1:])), t == 'CIRCLE', t, e.dxf.handle))
        elif t in ('TEXT', 'MTEXT'):
            if t == 'TEXT':
                txt, h, ha, va = e.dxf.text, e.dxf.height * k / 0.7, e.dxf.halign, e.dxf.valign
                fitted = ha in (3, 5)                           # aligned and fit run from insert to align_point
                at = e.dxf.align_point if (ha or va) and not fitted and e.dxf.hasattr('align_point') else e.dxf.insert
                fx = 0.0 if fitted else {1: 0.5, 2: 1.0, 4: 0.5}.get(ha, 0.0)
                fy = 0.5 if ha == 4 else 0.0 if fitted else {2: 0.5, 3: 1.0}.get(va, 0.0)
                rot = e.dxf.rotation
            else:
                txt, h, ap = e.plain_text(), e.dxf.char_height * k / 0.7, e.dxf.attachment_point
                at, fx, fy, rot = e.dxf.insert, (ap - 1) % 3 / 2, 1 - (ap - 1) // 3 / 2, e.get_rotation()
            wdt = max(text_width(ln, h) for ln in txt.split('\n'))
            texts.append(dict(layer=lay, text=txt, box=_text_box(P(at), wdt, 0.7 * h, fx, fy, rot)))
        elif t == 'INSERT':
            for v in e.virtual_entities():
                add(v, lay if v.dxf.layer == '0' else v.dxf.layer)     # a block's layer-0 contents take the insert's layer
        elif t != 'HATCH':
            unread[t] += 1

    for e in doc.modelspace():
        add(e, e.dxf.layer)
    clip = doc.header.custom_vars.get('KIT_CLIP')       # x0,y0,x1,y1 in model units: only what prints through it is checked
    if clip:
        x0, y0, x1, y1 = (float(v) for v in clip.split(','))
        (ax, ay), (bx, by) = P((x0, y0)), P((x1, y1))
        box = (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))
        kept = []
        for p in paths:
            p.segs = [s for s in (_clip_seg(a, b, box) for a, b in p.segs) if s and s[0] != s[1]]
            p.clip = box
            if p.segs:
                kept.append(p)
        paths = kept
    return dict(paths=paths, texts=texts, roles={}, scale=scale, k=k, units=units, unread=dict(unread),
                doubles=doc.header.custom_vars.get('KIT_DOUBLES'))


# ---------------------------------------------------------------- checks
def _seg_dist(p, a, b):
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return math.dist(p, (ax + t * dx, ay + t * dy))


def _cross(a, b, c, d):
    def o(p, q, r):
        v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        return 0 if abs(v) < 1e-12 else (1 if v > 0 else -1)
    return o(a, b, c) != o(a, b, d) and o(c, d, a) != o(c, d, b)


def within(p, box):
    """is p inside the convex box (its corners in order), so a turned label is not read as its upright bounds"""
    sides = [(b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) for a, b in zip(box, box[1:] + box[:1])]
    return all(v > 0 for v in sides) or all(v < 0 for v in sides)


def role_of(layer, t, svg_roles):
    if layer in svg_roles:
        return svg_roles[layer], 'svg'
    lid = (layer or '').split(' › ', 1)[0].replace(' ', '_')
    for kind in ('drawing', 'map'):
        for L in t['layers'][kind]:
            if L['id'].replace(' ', '_') == lid:           # PROPERTY LINES as written, or as PROPERTY_LINES
                return L['role'], 'tokens'
    m = TAG.search(layer or '')
    if m and m.group(1) in t['roles']:
        return m.group(1), 'tag'
    low = (layer or '').lower()
    for role, words in t['role_words'].items():
        if not role.startswith('_') and any(re.search(r'(^|[^a-z])' + re.escape(w), low) for w in words):
            return role, 'guess'
    return None, None


def check(data, t):
    near, minlen = t['lint']['near_pt'], t['lint']['min_len_pt']
    if data['units'] == 'pt':
        touch = max(t['lint']['touch_mm'] * PT_PER_MM / data['scale'], 0.005) if data['scale'] else 0.005
    else:
        touch = max(t['lint']['touch_mm'] / UNIT_MM[data['units']] * data['k'], 0.005)
    found = []
    roles, notes = {}, []
    for p in data['paths']:
        if p.layer not in roles:
            r, how = role_of(p.layer, t, data['roles'])
            roles[p.layer] = None if how == 'guess' else r
            if how == 'guess':
                notes.append(('role', f'layer "{p.layer}": no {{role}} tag; reads as {r}; name it "{p.layer} {{{r}}}" to apply'))
            elif r is None and p.layer:
                notes.append(('role', f'layer "{p.layer}": role unknown; add a {{role}} tag'))
    lines = [p for p in data['paths'] if roles.get(p.layer) in LINE_ROLES and p.stroke != 'none']   # a fill alone draws no line

    # open cuts
    for p in data['paths']:
        if roles.get(p.layer) == 'cut' and not p.closed:
            found.append(('error', 'open-cut', f'{p.layer}: open path {p.src or p.kind} on a cut layer, from {_fmt(p.segs[0][0])} to {_fmt(p.segs[-1][1])}', p.segs[0][0]))

    # grid of segments
    cell = max(near * 2, 1.0)
    grid = defaultdict(list)
    for pi, p in enumerate(lines):
        for si, (a, b) in enumerate(p.segs):
            for gx in range(int(min(a[0], b[0]) // cell) - 1, int(max(a[0], b[0]) // cell) + 2):
                for gy in range(int(min(a[1], b[1]) // cell) - 1, int(max(a[1], b[1]) // cell) + 2):
                    grid[(gx, gy)].append((pi, si))

    # near misses
    beside = []                                         # in a hidden-line drawing, ends beside the line they run along
    for pi, p in enumerate(lines):
        if data.get('doubles') and roles.get(p.layer) == 'hidden':
            continue                                    # dashed ends are visibility stops
        for ei, e in enumerate(p.ends()):
            if p.clip and not (p.clip[0] + 1e-6 < e[0] < p.clip[2] - 1e-6 and p.clip[1] + 1e-6 < e[1] < p.clip[3] - 1e-6):
                continue                                # an end the clip cuts is not a drawn end
            own = 0 if ei == 0 else len(p.segs) - 1
            itself = set()                              # the path's own stretch until it first leaves the circle of
            for si in (range(len(p.segs)) if ei == 0 else range(len(p.segs) - 1, -1, -1)):   # near round the end:
                itself.add(si)                          # coming back into it later is a hook
                if math.dist(e, p.segs[si][1] if ei == 0 else p.segs[si][0]) >= near:
                    break
            best, near_segs = None, []
            for qi, si in grid.get((int(e[0] // cell), int(e[1] // cell)), []):
                if qi == pi and (abs(si - own) <= 1 or si in itself):
                    continue
                if data.get('doubles') and ((roles.get(p.layer) == 'hidden') != (roles.get(lines[qi].layer) == 'hidden')):
                    continue
                a, b = lines[qi].segs[si]
                dd = _seg_dist(e, a, b)
                best = dd if best is None or dd < best else best
                if dd < near:
                    near_segs.append((a, b))
            if best is not None and touch < best < near:
                if data.get('doubles') and _end_beside(p, ei, near_segs):
                    beside.append(e)
                    continue
                found.append(('error', 'near-miss', f'{p.layer}: line end {best:.3f} pt from other linework at {_fmt(e)}', e))
    if beside:
        found.append(('warning', 'beside', f'{len(beside)} line ends lie beside a line their own runs along, as the model has '
                      f'them: a hidden-line drawing keeps them', beside[0]))

    # strays
    for p in lines:
        if p.length() < minlen:
            found.append(('warning', 'stray', f'{p.layer}: {p.kind} {p.length():.3f} pt long at {_fmt(p.segs[0][0])}', p.segs[0][0]))

    # duplicates: straight segments on the same line overlapping
    buckets = defaultdict(list)
    for pi, p in enumerate(lines):
        for (a, b) in p.segs:
            if a > b:
                a, b = b, a
            L = math.dist(a, b)
            if L < minlen:
                continue
            ang = round(math.atan2(b[1] - a[1], b[0] - a[0]) % math.pi, 3)   # one axis for the bucket: on each
            nx, ny = -math.sin(ang), math.cos(ang)     # segment's own, two meeting end to end 900 pt out overlapped 0.24 pt
            off = a[0] * nx + a[1] * ny
            ux, uy = math.cos(ang), math.sin(ang)
            s0, s1 = sorted((a[0] * ux + a[1] * uy, b[0] * ux + b[1] * uy))
            buckets[(ang, round(off, 1))].append((s0, s1, pi, a))
    seen = set()
    for key, segs in buckets.items():
        segs.sort()
        for i in range(len(segs)):
            for j in range(i + 1, len(segs)):
                if segs[j][0] >= segs[i][1] - minlen:
                    break
                if segs[i][2] == segs[j][2] and lines[segs[i][2]].closed:
                    continue
                li_, lj_ = lines[segs[i][2]], lines[segs[j][2]]
                if roles.get(li_.layer) == 'cut' and roles.get(lj_.layer) == 'cut' and (li_.width or 0.0) != (lj_.width or 0.0) \
                        and ((li_.width or 0.0) > (lj_.width or 0.0)) == (segs[i][2] > segs[j][2]):
                    continue                           # a heavier cut drawn over a lighter one's edge: the print is the same
                ov = min(segs[i][1], segs[j][1]) - segs[j][0]
                tag = (key, round(segs[j][0], 1))
                if ov > minlen and tag not in seen:
                    seen.add(tag)
                    found.append(('warning', 'duplicate', f'{lines[segs[i][2]].layer} / {lines[segs[j][2]].layer}: '
                                  f'{ov:.2f} pt of overlapping line at {_fmt(segs[j][3])}', segs[j][3]))

    double_sets = [[p for p in lines if (roles.get(p.layer) == 'hidden') == hidden] for hidden in (False, True)] if data.get('doubles') else [lines]
    for paths in double_sets:
        found += doubles(paths, t['lint']['double_pt'], minlen, touch, kept=data.get('doubles') == 'kept')

    # weights and colours (svg)
    if data['units'] == 'pt' and data['scale']:
        hexes = {c['hex'].lower() for n, c in t['colors'].items() if not n.startswith('_')}
        for p in data['paths']:
            r = roles.get(p.layer)
            lid = (p.layer or '').replace(' ', '_')
            want = None
            try:
                if p.want:                              # its sublayer's own weight
                    want = t.weight(float(p.want) if re.fullmatch(r'[\d.]+', p.want) else p.want, data['scale'])
                else:
                    for kind in ('drawing', 'map'):
                        ids = [L['id'] for L in t['layers'][kind] if L['id'].replace(' ', '_') == lid]
                        if ids:
                            want = t.look(kind, ids[0], data['scale'])['weight']
                            break
                    else:
                        if r in t['roles'] and t['roles'][r].get('weight'):
                            want = t.weight(t['roles'][r]['weight'], data['scale'])
            except KeyError:
                pass
            if want and p.width and p.stroke not in (None, 'none') and abs(p.width - want) > 0.011 and r in LINE_ROLES:
                found.append(('warning', 'weight', f'{p.layer}: {p.width:g} pt where {r} is {want:g} pt at 1:{data["scale"]:g}', p.segs[0][0]))
            for c in (p.stroke, p.fill):
                if c and c.startswith('#') and _hex6(c) not in hexes:
                    found.append(('warning', 'colour', f'{p.layer}: {c} is not a token colour', p.segs[0][0]))

    # labels crossing linework; a label with a knockout masks the layers under its own
    order = data.get('order') or {}
    under = lambda tx, p: tx.get('masks') and order.get(p.layer, 1e9) < order.get(tx['layer'], -1)
    for tx in data['texts']:
        box = tx['box']
        edges = list(zip(box, box[1:] + box[:1]))
        hit = None
        xs, ys = [p[0] for p in box], [p[1] for p in box]
        for gx in range(int(min(xs) // cell), int(max(xs) // cell) + 1):
            for gy in range(int(min(ys) // cell), int(max(ys) // cell) + 1):
                for qi, si in grid.get((gx, gy), []):
                    if under(tx, lines[qi]):
                        continue
                    a, b = lines[qi].segs[si]
                    if within(a, box) or any(_cross(a, b, c, d) for c, d in edges):
                        hit = lines[qi].layer
                        break
                if hit:
                    break
            if hit:
                break
        if hit:
            found.append(('warning', 'label', f'"{tx["text"]}" on {tx["layer"]} crosses {hit}', box[0]))

    if data.get('unread'):
        notes.append(('unread', 'not read, so not checked: ' + ', '.join(f'{n} {k}' for k, n in sorted(data['unread'].items()))))
    for kind, msg in notes:
        found.append(('warning', kind, msg, None))
    return found


DOUBLE_DEG = 5           # segments within this of parallel can run side by side
DOUBLE_RUN = 3.0         # pt of side-by-side run, summed over a pair of paths, before it is reported (mark_len)
DOUBLE_EACH = 5          # reports for one pair of layers before the rest are counted in one line


def _end_beside(p, ei, others, deg=20.0, back=0.3):
    """the end ei (0 or 1) of path p lies beside each of the segments others: each within deg of the way the path
    runs into its end, over back pt, and to its side, not ahead (a double kept, or a line converging on another)"""
    segs = p.segs if ei else [(b, a) for a, b in reversed(p.segs)]
    e, run, q = segs[-1][1], 0.0, segs[-1][0]
    for a, b in reversed(segs):
        run += math.dist(a, b)
        q = a
        if run >= back:
            break
    u = (e[0] - q[0], e[1] - q[1])
    nu = math.hypot(*u)
    if not nu or not others:
        return False
    u, c = (u[0] / nu, u[1] / nu), math.cos(math.radians(deg))
    for a, b in others:
        d = (b[0] - a[0], b[1] - a[1])
        nd = math.hypot(*d)
        if not nd or abs(u[0] * d[0] + u[1] * d[1]) < c * nd:
            return False
        t = max(0.0, min(1.0, ((e[0] - a[0]) * d[0] + (e[1] - a[1]) * d[1]) / (nd * nd)))
        o = (a[0] + d[0] * t - e[0], a[1] + d[1] * t - e[1])
        if abs(o[0] * u[0] + o[1] * u[1]) > 0.5 * math.hypot(*o):
            return False
    return True


def _beside(s, q, gap, touch):
    """how far segment q runs beside segment s, between touch and gap off it, measured along s, and where; (0, None)
    when they are not near parallel or do not run side by side"""
    (ax, ay), (bx, by) = s
    L = math.hypot(bx - ax, by - ay)
    ux, uy = (bx - ax) / L, (by - ay) / L
    (cx, cy), (dx, dy) = q
    M = math.hypot(dx - cx, dy - cy)
    if abs(ux * (dy - cy) - uy * (dx - cx)) / M > math.sin(math.radians(DOUBLE_DEG)):
        return 0.0, None
    tc, td = (cx - ax) * ux + (cy - ay) * uy, (dx - ax) * ux + (dy - ay) * uy
    nc, nd = (cx - ax) * -uy + (cy - ay) * ux, (dx - ax) * -uy + (dy - ay) * ux
    if tc > td:
        tc, td, nc, nd = td, tc, nd, nc
    t0, t1 = max(0.0, tc), min(L, td)
    if t1 - t0 <= 0:
        return 0.0, None
    n = lambda t: nc + (nd - nc) * (t - tc) / (td - tc) if td > tc else nc
    lo, hi = t0, t1
    n0, n1 = n(t0), n(t1)
    if n0 * n1 < 0:                                     # they cross: only the side with more run counts
        tx = t0 + (t1 - t0) * abs(n0) / (abs(n0) + abs(n1))
        lo, hi = (t0, tx) if tx - t0 > t1 - tx else (tx, t1)
    fa, fb = abs(n(lo)), abs(n(hi))                     # the offset's size, linear from lo to hi
    if abs(fb - fa) < 1e-12:
        if not touch < fa < gap:
            return 0.0, None
    else:
        u = sorted(((touch - fa) / (fb - fa), (gap - fa) / (fb - fa)))
        lo, hi = lo + (hi - lo) * max(0.0, u[0]), lo + (hi - lo) * min(1.0, u[1])
    if hi <= lo:
        return 0.0, None
    m = (lo + hi) / 2
    return hi - lo, (ax + ux * m, ay + uy * m)


def doubles(lines, gap, minlen, touch, kept=False):
    """two lines running side by side between touch and gap apart on paper, which print as one heavier line: summed
    over each pair of paths (a path against itself too, its neighbouring segments left out), reported where the run
    reaches DOUBLE_RUN; lines that cross or meet run beside each other only for a stretch near the crossing, under
    that. Kept (a hidden-line drawing that keeps its doubles, as the model has them), the pairs are counted in one
    warning"""
    cell = max(gap * 2, 1.0)
    grid = defaultdict(list)
    for pi, p in enumerate(lines):
        for si, (a, b) in enumerate(p.segs):
            if math.dist(a, b) < minlen:
                continue
            for gx in range(int(min(a[0], b[0]) // cell), int(max(a[0], b[0]) // cell) + 2):
                for gy in range(int(min(a[1], b[1]) // cell), int(max(a[1], b[1]) // cell) + 2):
                    grid[(gx, gy)].append((pi, si))
    runs = {}                                           # (pi, qi) -> [length, where]
    done = set()
    for cellsegs in grid.values():
        for i, (pi, si) in enumerate(cellsegs):
            for qi, sj in cellsegs[i + 1:]:
                key = (pi, si, qi, sj) if (pi, si) < (qi, sj) else (qi, sj, pi, si)
                if key in done:
                    continue
                done.add(key)
                if pi == qi and (lines[pi].closed or abs(si - sj) <= 1):
                    continue
                s, q = lines[key[0]].segs[key[1]], lines[key[2]].segs[key[3]]
                if math.dist(*s) < math.dist(*q):
                    s, q = q, s
                run, at = _beside(s, q, gap, touch)
                if run > 0:
                    r = runs.setdefault((key[0], key[2]), [0.0, at])
                    r[0] += run
    found, per = [], defaultdict(list)
    for (pi, qi), (run, at) in sorted(runs.items(), key=lambda kv: -kv[1][0]):
        if run >= DOUBLE_RUN:
            per[tuple(sorted((lines[pi].layer or '', lines[qi].layer or '')))].append((run, at, pi == qi))
    if kept:
        n = sum(len(h) for h in per.values())
        return [('warning', 'double', f'{n} pairs of lines run side by side under {gap:g} pt, kept as the model has them',
                 next(iter(per.values()))[0][1])] if n else []
    for (la, lb), hits in per.items():
        for run, at, own in hits[:DOUBLE_EACH]:
            what = f'{la}: a line runs beside itself' if own else f'{la} / {lb}: two lines run side by side'
            found.append(('warning', 'double', f'{what} under {gap:g} pt apart for {run:.1f} pt near {_fmt(at)}', at))
        if len(hits) > DOUBLE_EACH:
            found.append(('warning', 'double', f'{la} / {lb}: {len(hits) - DOUBLE_EACH} more pairs side by side under {gap:g} pt', hits[DOUBLE_EACH][1]))
    return found


def _fmt(p):
    return f'({p[0]:.1f}, {p[1]:.1f})'


_SUSPECTS = {}


def cause_of(at, f, t):
    """the likely cause of a finding at page point at, from the suspects of the hidden-lines report beside the drawing
    f (ID-report.json): the nearest within near_pt, as {confidence, why, ids, kinds}, or None"""
    if at is None or f.suffix.lower() != '.svg':
        return None
    if f not in _SUSPECTS:
        rp = f.with_name(f.stem + '-report.json')
        try:
            _SUSPECTS[f] = json.loads(rp.read_text(encoding='utf-8')).get('suspects') or [] if rp.is_file() else []
        except (OSError, ValueError):
            _SUSPECTS[f] = []
    near = [(math.dist(at, s['at_pt']), s) for s in _SUSPECTS[f] if math.dist(at, s['at_pt']) <= float(t['lint']['near_pt'])]
    if not near:
        return None
    s = min(near, key=lambda x: x[0])[1]
    return dict(confidence=s['confidence'], why=s['why'], ids=s['ids'], kinds=s['kinds'])


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    files = [a for a in argv if not a.startswith('--') and not re.fullmatch(r'\d+(\.\d+)?', a)]
    scale = float(argv[argv.index('--scale') + 1].split(':')[-1]) if '--scale' in argv else None
    bad = 0
    for f in files:
        f = Path(f).absolute()
        t = load(f)
        data = read_svg(f) if f.suffix.lower() == '.svg' else read_dxf(f, scale)
        if scale and data['units'] == 'pt':
            data['scale'] = scale
        found = check(data, t)
        found = [x + (cause_of(x[3], f, t),) for x in found]
        if data.get('kind') == 'word':
            try:
                from . import word
            except ImportError:
                word = None
            if word is not None:
                allowed = word.allowed_colours(f)
                found = [x for x in found if x[:2] != ('warning', 'colour')
                         or _hex6(x[2].rsplit(': ', 1)[-1].split()[0]) not in allowed]
                found += [(level, kind, msg, None, None) for level, kind, msg in word.lint(f)]
        errors = [x for x in found if x[0] == 'error']
        bad += len(errors)
        if '--json' in argv:
            print(json.dumps(dict(file=str(f), found=[dict(level=a, kind=b, msg=c, **(dict(cause=x) if x else {}))
                                                      for a, b, c, _, x in found]), ensure_ascii=False))
            continue
        print(f'{f.name}: {len(data["paths"])} paths, {len(data["texts"])} labels, 1:{data["scale"]:g}' if data['scale'] else f'{f.name}')
        for level, kind, msg, _, cause in sorted(found, key=lambda x: (x[0] != 'error', x[1])):
            print(f'  {level:7} {kind:10} {msg}' + (f'; probably the model ({cause["confidence"]}): {cause["why"]}' if cause else ''))
        print(f'  {len(errors)} errors, {len(found) - len(errors)} warnings')
    return 1 if bad else 0
