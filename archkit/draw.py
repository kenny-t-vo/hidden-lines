"""Layered drawing model with two writers.

  SVG  at print scale, in points: one group per layer, styled once on the group, live text.
       Inkscape reads the groups as layers; in Illustrator run adobe/illustrator/Layers from Drawing.jsx.
  DXF  AutoCAD 2013 at 1:1 in model units: real layers with colour, lineweight and linetype,
       closed polylines, UTF-8 text. Needs ezdxf.
  AI   Illustrator's own document (archkit/ainative.py): its layers and sublayers as layers, each sublayer's
       strokes at its weight and dash in a global swatch named for it; lines and shapes only.

Geometry is in model units, y up. Every visual value comes from the tokens: a layer names what it
holds, its role says how it looks, and the weight follows the drawing's scale band.
"""
import json, math
from .project import load, place, PT_PER_MM, UNIT_MM


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


class Drawing:
    def __init__(self, scale, units='mm', kind='drawing', tokens=None, title='', meta=None, start=None):
        self.t = tokens or load(start)
        self.scale = float(scale)
        self.units = units
        self.kind = kind
        self.title = title
        self.meta = meta or {}
        self.layers = self.t.layers(kind)
        self.ids = [L['id'] for L in self.layers]
        self.ents = {i: [] for i in self.ids}
        self.k = PT_PER_MM * UNIT_MM[units] / self.scale      # model unit -> pt on paper
        self.clip = None                                       # (x0, y0, x1, y1) model; maps set it
        self.knockout = {}                                     # layer id: halo width in pt under each of its labels (svg)
        self.subpaths = {}
        self.subids = {}
        self.subs = {}                                         # (layer id, sublayer): its weight, a band name or pt

    def pt(self, points):
        """a paper length in points, in model units"""
        return points / self.k

    def look(self, lid):
        return self.t.look(self.kind, lid, self.scale)

    def sublayer(self, layer, name, weight):
        """a sublayer of layer for the entities put with sub=name, all at one weight (a band name or pt): a group in the
        layer's SVG group carrying the weight, and data-weight for lint; in the DXF, the entities' own lineweight"""
        if layer not in self.ents:
            raise KeyError(f'unknown layer {layer}; layers come from tokens.json (layers.{self.kind})')
        self.subs[(layer, name)] = weight

    def _put(self, layer, e):
        if layer not in self.ents:
            raise KeyError(f'unknown layer {layer}; layers come from tokens.json (layers.{self.kind})')
        self.ents[layer].append(e)

    # ---- primitives, model coordinates
    def line(self, layer, a, b, **kw):
        self._put(layer, dict(k='pl', pts=[tuple(a), tuple(b)], closed=False, **kw))

    def polyline(self, layer, pts, closed=False, **kw):
        self._put(layer, dict(k='pl', pts=[tuple(p) for p in pts], closed=closed, **kw))

    def polygon(self, layer, rings, **kw):
        """rings[0] is the outline, the rest are holes; every ring is closed"""
        self._put(layer, dict(k='pg', rings=[[tuple(p) for p in r] for r in rings], **kw))

    def rect(self, layer, x, y, w, h, **kw):
        self.polyline(layer, [(x, y), (x + w, y), (x + w, y + h), (x, y + h)], closed=True, **kw)

    def circle(self, layer, c, r, **kw):
        self._put(layer, dict(k='ci', c=tuple(c), r=r, **kw))

    def arc(self, layer, c, r, a0, a1, **kw):
        """degrees, counter-clockwise from +x, from a0 to a1"""
        self._put(layer, dict(k='ar', c=tuple(c), r=r, a0=a0, a1=a1, **kw))

    def text(self, layer, at, s, style='Label', anchor='start', rotate=0.0, **kw):
        self._put(layer, dict(k='tx', at=tuple(at), s=str(s), style=style, anchor=anchor, rotate=rotate, **kw))

    # ---- composites
    def dim(self, a, b, offset, label=None, layer='DIM', tick_pt=2.0, gap_pt=1.5):
        """aligned dimension, offset to the left of a->b (negative for the right)"""
        (ax, ay), (bx, by) = a, b
        L = math.hypot(bx - ax, by - ay)
        if L == 0:
            return
        ux, uy = (bx - ax) / L, (by - ay) / L
        nx, ny = -uy, ux
        p, q = (ax + nx * offset, ay + ny * offset), (bx + nx * offset, by + ny * offset)
        self.line(layer, p, q)
        t = self.pt(tick_pt) / math.sqrt(2)
        for e in (p, q):
            self.line(layer, (e[0] - (ux + nx) * t, e[1] - (uy + ny) * t), (e[0] + (ux + nx) * t, e[1] + (uy + ny) * t))
        g, over = self.pt(gap_pt), self.pt(1.5)
        sgn = 1 if offset >= 0 else -1
        for s, e in ((a, p), (b, q)):
            self.line(layer, (s[0] + nx * g * sgn, s[1] + ny * g * sgn), (e[0] + nx * over * sgn, e[1] + ny * over * sgn))
        ang = math.degrees(math.atan2(uy, ux))
        if ang > 90 or ang <= -90:
            ang += 180
        lift = self.pt(1.8)
        mid = ((p[0] + q[0]) / 2 + nx * lift * sgn, (p[1] + q[1]) / 2 + ny * lift * sgn)
        self.text(layer, mid, label if label is not None else f'{L:.0f}',
                  style=self.t['drawing']['dim'], anchor='middle', rotate=ang)

    def marks(self, x0, x1, top, north_deg=0.0, bar_m=None, layer='MARK'):
        """the house's scale bar and north arrow (archkit/sheet.py, house()) at the sizes of tokens drawing.marks,
        under top (model units): the bar from x0, as long as fits before the arrow (bar_m metres where given and it
        fits), its top drop_pt under top, and the arrow ending at x1; north_deg, the direction of north in degrees
        clockwise from the top of the drawing"""
        try:
            from . import sheet
        except ImportError:
            return
        s = self.t['drawing']['marks']
        d, gap = float(s['north_pt']), float(s['north_gap_pt'])
        room = (x1 - x0) * self.k - gap - d
        longest = min(sheet.max_pt(s) if bar_m is None else bar_m * 72 / 25.4 * 1000 / self.scale * (1 + 1e-9), room)
        a = math.radians(north_deg)
        lines, text = sheet.house(s, self.scale, -float(s['drop_pt']), (math.sin(a), math.cos(a)), longest, start=0.0,
                                  arrow=(x1 - x0) * self.k - d / 2)
        at = lambda x, y: (x0 + self.pt(x), top + self.pt(y))           # house() draws in points from x0, top
        for _, pts, w, closed in lines:
            self.polyline(layer, [at(*p) for p in pts], closed=closed, w_pt=w)
        for it in text:
            self.text(layer, at(it['x'], it['y']), it['text'], style=self.t['drawing']['label'],
                      anchor={'center': 'middle', 'right': 'end'}.get(it['justify'], 'start'),
                      size=it['size'], tracking=it.get('tracking', 0))

    # ---- extents
    def _pts(self, e):
        if e['k'] == 'pl':
            return e['pts']
        if e['k'] == 'pg':
            return [p for r in e['rings'] for p in r]
        if e['k'] in ('ci', 'ar'):
            c, r = e['c'], e['r']
            return [(c[0] - r, c[1] - r), (c[0] + r, c[1] + r)]
        return [e['at']]

    def bounds(self, printing_only=True):
        xs, ys = [], []
        for L in self.layers:
            if printing_only and not self.look(L['id'])['print']:
                continue
            for e in self.ents[L['id']]:
                for p in self._pts(e):
                    xs.append(p[0])
                    ys.append(p[1])
        if self.clip:
            marks = [p for i in self.ids if self.look(i)['role'] in ('anno', 'text', 'nonprint')
                     for e in self.ents[i] for p in self._pts(e)]
            xs = [self.clip[0], self.clip[2]] + [p[0] for p in marks]
            ys = [self.clip[1], self.clip[3]] + [p[1] for p in marks]
        if not xs:
            return (0, 0, 0, 0)
        return (min(xs), min(ys), max(xs), max(ys))

    def size_pt(self, pad_pt=0.0):
        x0, y0, x1, y1 = self.bounds()
        return ((x1 - x0) * self.k + 2 * pad_pt, (y1 - y0) * self.k + 2 * pad_pt)

    # ---- text styling shared by both writers
    def _font(self, st):
        p = self.t.pstyle(st)
        f = self.t['fonts'][p['font']]
        style = p.get('style', 'Regular')
        base = style.replace('Italic', '').strip() or 'Regular'
        weight = {'ExtraLight': 200, 'Light': 300, 'Regular': 400, 'Medium': 500, 'Semibold': 600, 'Bold': 700}.get(base, 400)
        return p, [f['family']] + f.get('fallback', []), weight, ('italic' if 'Italic' in style else 'normal')

    # ---- SVG
    def to_svg(self, path, pad_pt=6.0, canvas=None, origin=None, extra_top=None):
        """canvas=(w, h) pt with origin=(x, y), the page position of the drawing's lower-left, places
        the drawing on a fixed page; otherwise the canvas hugs the drawing with pad_pt around it"""
        x0, y0, x1, y1 = self.bounds(printing_only=False)
        k = self.k
        if canvas:
            W, H = canvas
            ox, oy = origin
        else:
            W, H = (x1 - x0) * k + 2 * pad_pt, (y1 - y0) * k + 2 * pad_pt
            ox, oy = pad_pt, H - pad_pt
        X = lambda x: ox + (x - x0) * k
        Y = lambda y: oy - (y - y0) * k
        hexof = lambda n: self.t.hex(n) if n else 'none'

        def text_svg(e, paint):
            p, fams, weight, slant = self._font(e['style'])
            p = dict(p, size=e.get('size') or p['size'], tracking=e.get('tracking', p.get('tracking', 0)))
            txt = e['s'].upper() if p.get('caps') == 'all' else e['s']
            ls = p.get('tracking', 0) / 1000.0 * p['size']
            x, y = X(e['at'][0]), Y(e['at'][1])
            tr = f' transform="rotate({-e["rotate"]:.2f} {x:.2f} {y:.2f})"' if e['rotate'] else ''
            fam = ', '.join(f"'{f}'" for f in fams)
            return (f'<text x="{x:.2f}" y="{y:.2f}" font-family="{esc(fam)}" font-size="{p["size"]:g}" '
                    f'font-weight="{weight}" font-style="{slant}" letter-spacing="{ls:.3f}" '
                    f'text-anchor="{e["anchor"]}"{paint} data-style="{esc(e["style"])}"{tr}>{esc(txt)}</text>')

        meta = dict(scale=f'1:{self.scale:g}', units=self.units, band=self.t.band(self.scale)['name'], **self.meta)
        out = ['<?xml version="1.0" encoding="UTF-8"?>',
               f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
               f'version="1.1" width="{W:.2f}pt" height="{H:.2f}pt" viewBox="0 0 {W:.2f} {H:.2f}">',
               f'<title>{esc(self.title)}</title>',
               f'<desc>{esc(json.dumps(meta, ensure_ascii=False))}</desc>']
        if extra_top:
            out.append(extra_top)
        if self.clip:
            cx0, cy0, cx1, cy1 = self.clip
            out.append(f'<defs><clipPath id="window"><rect x="{X(cx0):.2f}" y="{Y(cy1):.2f}" '
                       f'width="{(cx1 - cx0) * k:.2f}" height="{(cy1 - cy0) * k:.2f}"/></clipPath></defs>')
        at, clips = len(out), []                               # the knockouts' clips go in a defs here
        for L in self.layers:
            lid = L['id']
            s = self.look(lid)
            attrs = (f' fill="{hexof(s["fill"])}" stroke="{hexof(s["stroke"])}"'
                     + (f' stroke-width="{s["weight"]:g}"' if s['weight'] else '')
                     + ' stroke-linejoin="miter" stroke-miterlimit="10" stroke-linecap="butt" fill-rule="evenodd"')
            if s['dash']:
                attrs += ' stroke-dasharray="' + ' '.join(f'{v:g}' for v in s['dash']) + '"'
            if not s['print']:
                attrs += ' display="none"'
            if self.clip and s['role'] not in ('anno', 'text', 'nonprint'):
                attrs += ' clip-path="url(#window)"'
            out.append(f'<g id="{lid}" inkscape:groupmode="layer" inkscape:label="{lid}" '
                       f'data-role="{s["role"]}" data-title="{esc(s["title"])}"{attrs}>')
            halo = float(self.knockout.get(lid) or 0)
            if halo > 0:                                       # every halo of the layer first, so none covers a label
                paper = hexof(self.t['drawing']['knockout']['color'])
                for e in self.ents[lid]:
                    if e['k'] != 'tx':
                        continue
                    for col, rings in e.get('knock') or [(paper, None)]:     # (hex, rings or None), geo.grounds
                        ko = text_svg(e, f' fill="{col}" stroke="{col}" stroke-width="{2 * halo:g}" '
                                         f'stroke-linejoin="round" data-knockout="halo"')
                        if rings:                              # clipped in a group, so a turned label's clip is not turned
                            clips.append(f'<clipPath id="knockout-{len(clips)}"><path d="'
                                         + ' '.join('M ' + ' L '.join(f'{X(x):.3f},{Y(y):.3f}' for x, y in r) + ' Z' for r in rings)
                                         + '" clip-rule="evenodd"/></clipPath>')
                            ko = f'<g clip-path="url(#knockout-{len(clips) - 1})">{ko}</g>'
                        out.append(ko)
            subs = [n for (l_, n) in self.subs if l_ == lid]
            cur, opened, fragments, taken_ids = None, [], {}, set(self.ids)
            reserved = set(self.subids.values()) | set(self.ids)
            for e in [e for e in self.ents[lid] if e.get('sub') not in subs] + \
                    [e for n in subs for e in self.ents[lid] if e.get('sub') == n]:
                if e.get('sub') != cur:
                    subpath = self.subpaths.get((lid, e['sub']), [(e['sub'], e['sub'])])
                    common = 0
                    while common < min(len(opened), len(subpath) - 1) and opened[common] == subpath[common]:
                        common += 1
                    out.extend('</g>' for _ in opened[common:])
                    opened = opened[:common]
                    cur = e['sub']
                    sw = self.t.weight(self.subs[(lid, cur)], self.scale)
                    raw = L.get('stroke') or self.t['roles'][L['role']].get('stroke') or 'K100'
                    for i, part in enumerate(subpath[common:], common):
                        leaf = i == len(subpath) - 1
                        sid = (self.subids.get((lid, cur)) if leaf else None) or (
                            lid + '-' + ''.join(c if c.isalnum() else '-' for c in '-'.join(p[1] for p in subpath[:i + 1])))
                        if not leaf:
                            while sid in reserved:
                                sid += '-group'
                        fragments[sid] = fragments.get(sid, 0) + 1
                        if fragments[sid] > 1:
                            sid += f'-part-{fragments[sid]}'
                        while sid in taken_ids:
                            sid += '-part'
                        taken_ids.add(sid)
                        attrs_ = (f' data-weight="{esc(self.subs[(lid, cur)])}" '
                                  f'stroke="{hexof(self.t.ink(raw, sw))}" stroke-width="{sw:g}"') if leaf else ''
                        out.append(f'<g id="{sid}" inkscape:groupmode="layer" inkscape:label="{esc(part[0])}"{attrs_}>')
                        opened.append(part)
                own = ''
                if e.get('fill'):
                    own += f' fill="{hexof(e["fill"])}"'
                    if not s['stroke'] and e.get('stroke') != 'none':
                        fw = self.t.weight('fine', self.scale)
                        own += f' stroke="{hexof(self.t.ink("K100", fw))}" stroke-width="{fw:g}"'
                if e.get('stroke') == 'none':                  # a fill alone, on a layer that strokes
                    own += ' stroke="none"'
                elif e.get('stroke'):
                    ew = self.t.weight(e['weight'], self.scale) if e.get('weight') else s['weight']
                    own += f' stroke="{hexof(self.t.ink(e["stroke"], ew))}"'
                if e.get('weight'):
                    own += f' stroke-width="{self.t.weight(e["weight"], self.scale):g}"'
                if e.get('w_pt'):                              # its own weight, inked for that weight (the hairline cap)
                    L_ = self.t.layer(self.kind, lid)
                    raw = e.get('stroke') or L_.get('stroke') or self.t['roles'][L_['role']].get('stroke') or 'K100'
                    own += f' stroke="{hexof(self.t.ink(raw, e["w_pt"]))}" stroke-width="{e["w_pt"]:g}"'
                if e.get('dash'):
                    own += ' stroke-dasharray="' + ' '.join(f'{v:g}' for v in self.t['dashes'][e['dash']]) + '"'
                if e['k'] == 'pl':
                    d = 'M ' + ' L '.join(f'{X(x):.3f},{Y(y):.3f}' for x, y in e['pts'])
                    if e['closed']:
                        d += ' Z'
                    elif not e.get('fill'):
                        own += ' fill="none"'
                    out.append(f'<path d="{d}"{own}/>')
                elif e['k'] == 'pg':
                    d = ' '.join('M ' + ' L '.join(f'{X(x):.3f},{Y(y):.3f}' for x, y in r) + ' Z' for r in e['rings'])
                    out.append(f'<path d="{d}"{own}/>')
                elif e['k'] == 'ci':
                    out.append(f'<circle cx="{X(e["c"][0]):.3f}" cy="{Y(e["c"][1]):.3f}" r="{e["r"] * k:.3f}"{own}/>')
                elif e['k'] == 'ar':
                    a0, a1 = math.radians(e['a0']), math.radians(e['a1'])
                    cx, cy, r = e['c'][0], e['c'][1], e['r']
                    p0 = (X(cx + r * math.cos(a0)), Y(cy + r * math.sin(a0)))
                    p1 = (X(cx + r * math.cos(a1)), Y(cy + r * math.sin(a1)))
                    large = 1 if (e['a1'] - e['a0']) % 360 > 180 else 0
                    out.append(f'<path d="M {p0[0]:.3f},{p0[1]:.3f} A {r * k:.3f} {r * k:.3f} 0 {large} 0 '
                               f'{p1[0]:.3f},{p1[1]:.3f}" fill="none"{own}/>')
                elif e['k'] == 'tx':
                    col = hexof(e.get('color') or self.t.pstyle(e['style']).get('color') or s['fill'] or 'K100')
                    out.append(text_svg(e, f' fill="{col}" stroke="none"' + (f' data-knockout="{halo:g}"' if halo > 0 else '')))
            out.extend('</g>' for _ in opened)
            out.append('</g>')
        if clips:
            out.insert(at, '<defs>' + ''.join(clips) + '</defs>')
        out.append('</svg>\n')
        return place('\n'.join(out), path)

    # ---- Illustrator
    def to_ai(self, path, canvas=None, origin=None):
        """an Illustrator document, placed on the page as to_svg places the drawing, one artboard the page: a layer
        for each layer that holds anything, bottom to top, a sublayer for each of its sublayers, and each sublayer's
        lines in a global K100 swatch named for it (layer and sublayer), so one swatch edit recolours a class and one
        sublayer selection selects it; a K-only colour is a tint of the swatch, any other its own global colour"""
        from . import ainative
        x0, y0, x1, y1 = self.bounds(printing_only=False)
        k = self.k
        if canvas:
            W, H = canvas
            ox, oy = origin
        else:
            W, H = (x1 - x0) * k + 12.0, (y1 - y0) * k + 12.0
            ox, oy = 6.0, H - 6.0
        page = lambda p: (ox + (p[0] - x0) * k, H - oy + (p[1] - y0) * k)          # page points, y up
        w = ainative.Writer(ainative.TEMPLATE, hairline=self.t.hairline)
        w.artboard(self.title or 'drawing', 0.0, 0.0, W, H)

        def paint(name):
            """(black 0 to 1, global colour or None) for a token colour"""
            c = self.t['colors'][name]['cmyk']
            if any(c[:3]):
                w.define(name, [v / 100.0 for v in c])
                return 1.0, name
            return c[3] / 100.0, None
        for n, L in enumerate(self.layers):
            lid = L['id']
            ents = self.ents[lid]
            if not ents:
                continue
            bad = sorted({e['k'] for e in ents} - {'pl', 'pg'})
            if bad:
                raise ValueError(f'to_ai writes lines and shapes; {lid} holds {", ".join(bad)}')
            s = self.look(lid)
            top = w.layer(lid, visible=s['print'], printing=s['print'], rgb=ainative.LAYER_RGB[n % len(ainative.LAYER_RGB)])
            raw = L.get('stroke') or self.t['roles'][L['role']].get('stroke')
            sheets, opened = {}, []
            for e in ents:
                sub = e.get('sub') if (lid, e.get('sub')) in self.subs else None    # as to_svg: no sublayer, the layer
                if sub not in sheets:
                    parent = top
                    subpath = self.subpaths.get((lid, sub), [(sub, sub)]) if sub else []
                    common = 0
                    while common < min(len(opened), len(subpath) - 1) and opened[common][0] == subpath[common]:
                        parent = opened[common][1]
                        common += 1
                    opened = opened[:common]
                    for part in subpath[common:]:
                        parent = w.layer(part[0], parent=parent)
                        opened.append((part, parent))
                    sheets[sub] = parent
                    if sub:
                        sheets[sub].swatch = (self.subids[lid, sub] if len(subpath) > 1 else
                                              f'{lid} {subpath[0][0]}')
                sh = sheets[sub]
                wt = self.t.weight(self.subs[(lid, sub)], self.scale) if sub else \
                    (self.t.weight(e['weight'], self.scale) if e.get('weight') else e.get('w_pt') or s['weight'])
                stroke = None
                if e.get('stroke') != 'none' and (e.get('stroke') or raw) and wt:
                    kk, glob = paint(e.get('stroke') or raw)
                    stroke = dict(w=wt, k=kk, dash=list(self.t['dashes'][e['dash']]) if e.get('dash') else list(s['dash'] or []))
                    if glob:
                        stroke['swatch'] = glob
                fill = None
                if e.get('fill'):
                    c = self.t['colors'][e['fill']]['cmyk']
                    fill = ('k', c[3] / 100.0, None) if not any(c[:3]) else ('c', [v / 100.0 for v in c], 1.0, self.t.hex(e['fill']))
                if e['k'] == 'pl':
                    if e.get('fill') and e['closed']:
                        sh.polygon([[page(p) for p in e['pts']]], fill=fill, stroke=stroke)
                    else:
                        sh.line([page(p) for p in e['pts']], stroke, closed=e['closed'])
                else:
                    sh.polygon([[page(p) for p in r] for r in e['rings']], fill=fill, stroke=stroke)
        return w.save(path, self.title or None)

    # ---- DXF
    def to_dxf(self, path):
        import ezdxf
        from ezdxf.enums import TextEntityAlignment
        from ezdxf import colors as dxfcolors
        valid = [0, 5, 9, 13, 15, 18, 20, 25, 30, 35, 40, 50, 53, 60, 70, 80, 90, 100, 106, 120, 140, 158, 200, 211]
        ezdxf.options.write_fixed_meta_data_for_testing = True   # no time stamps or random ids: one drawing, one file
        doc = ezdxf.new('R2013', setup=False)
        doc.units = {'in': 1, 'ft': 2, 'mm': 4, 'cm': 5, 'm': 6}[self.units]
        doc.header['$MEASUREMENT'] = 1
        doc.header['$LTSCALE'] = 1.0
        doc.header['$LWDISPLAY'] = 1
        doc.header.custom_vars.append('KIT_SCALE', f'{self.scale:g}')
        if self.clip:                                          # the window the SVG clips to, for lint
            doc.header.custom_vars.append('KIT_CLIP', ','.join(f'{v:.17g}' for v in self.clip))
        if self.meta.get('doubles'):                           # a hidden-line drawing's doubles, kept or simplified, for lint
            doc.header.custom_vars.append('KIT_DOUBLES', self.meta['doubles'])
        for name, pat in self.t['dashes'].items():
            if name.startswith('_'):
                continue
            el = [self.pt(v) * (1 if i % 2 == 0 else -1) for i, v in enumerate(pat)]
            doc.linetypes.add(f'KIT_{name.upper()}', pattern=[sum(abs(v) for v in el)] + el, description=name)
        p_sans, fams, _, _ = self._font(self.t['drawing']['label'])
        doc.styles.add('KIT_LABEL', font=fams[0])
        for L in self.layers:
            s = self.look(L['id'])
            ink = s['stroke'] or s['fill'] or 'K100'
            rgb = tuple(int(self.t.hex(ink)[i:i + 2], 16) for i in (1, 3, 5))
            lay = doc.layers.add(L['id'])
            lay.dxf.true_color = dxfcolors.rgb2int(rgb)
            lay.dxf.color = 7 if rgb in ((0, 0, 0), (255, 255, 255)) else 256
            if s['weight']:
                mm = s['weight'] / PT_PER_MM * 100
                lay.dxf.lineweight = min(valid, key=lambda v: abs(v - mm))
            if s['dash_name']:
                lay.dxf.linetype = f'KIT_{s["dash_name"].upper()}'
            if not s['print']:
                lay.dxf.plot = 0
            lay.description = s['title']
        for (lid, sub), path_ in self.subpaths.items():
            name = ' › '.join([lid] + [p[0] for p in path_])
            lay = doc.layers.get(lid)
            leaf = doc.layers.add(name, dxfattribs={k: v for k, v in lay.dxf.all_existing_dxf_attribs().items()
                                                   if k not in ('handle', 'owner', 'name')})
            mm = self.t.weight(self.subs[lid, sub], self.scale) / PT_PER_MM * 100
            leaf.dxf.lineweight = min(valid, key=lambda v: abs(v - mm))
        msp = doc.modelspace()
        for L in self.layers:
            lid = L['id']
            s = self.look(lid)
            fillonly = not s['stroke']
            for e in self.ents[lid]:
                path_ = self.subpaths.get((lid, e.get('sub')))
                a = {'layer': ' › '.join([lid] + [p[0] for p in path_]) if path_ else lid}
                if e.get('sub') is not None:                   # a sublayer's weight, on its entities
                    mm = self.t.weight(self.subs[(lid, e['sub'])], self.scale) / PT_PER_MM * 100
                    a['lineweight'] = min(valid, key=lambda v: abs(v - mm))
                if e['k'] in ('pl', 'pg') and (fillonly and s['role'] in ('field', 'solid') or e.get('stroke') == 'none'):
                    rings = e['rings'] if e['k'] == 'pg' else [e['pts']]
                    h = msp.add_hatch(dxfattribs=a)
                    h.set_solid_fill(color=256)
                    if e.get('fill'):                          # its own colour over the layer's
                        h.dxf.true_color = dxfcolors.rgb2int(tuple(int(self.t.hex(e['fill'])[i:i + 2], 16) for i in (1, 3, 5)))
                    for n, r in enumerate(rings):
                        h.paths.add_polyline_path([(x, y) for x, y in r], is_closed=True, flags=1 if n == 0 else 0)
                elif e['k'] == 'pl':
                    if len(e['pts']) == 2 and not e['closed']:
                        msp.add_line(e['pts'][0], e['pts'][1], dxfattribs=a)
                    else:
                        msp.add_lwpolyline(e['pts'], close=e['closed'], dxfattribs=a)
                elif e['k'] == 'pg':
                    for r in e['rings']:
                        msp.add_lwpolyline(r, close=True, dxfattribs=a)
                elif e['k'] == 'ci':
                    msp.add_circle(e['c'], e['r'], dxfattribs=a)
                elif e['k'] == 'ar':
                    msp.add_arc(e['c'], e['r'], e['a0'] % 360, e['a1'] % 360, dxfattribs=a)
                elif e['k'] == 'tx':
                    p = self.t.pstyle(e['style'])
                    txt = e['s'].upper() if p.get('caps') == 'all' else e['s']
                    t = msp.add_text(txt, height=self.pt((e.get('size') or p['size']) * 0.7),
                                     dxfattribs=dict(a, style='KIT_LABEL', rotation=e['rotate']))
                    t.set_placement(e['at'], align={'start': TextEntityAlignment.LEFT, 'middle': TextEntityAlignment.CENTER,
                                                    'end': TextEntityAlignment.RIGHT}[e['anchor']])
        doc.classes.add_required_classes(doc.dxfversion)
        doc.classes.classes = dict(sorted(doc.classes.classes.items()))   # registered in no fixed order (a set's)
        import io
        buf = io.StringIO()
        doc.write(buf)
        return place(buf.getvalue(), path)


def fit_report(d):
    """does the drawing fit the page's live area at its scale, and which ladder scales would"""
    pg = d.t['page']
    lw = pg['trim_w'] - pg['margin_inside'] - pg['margin_outside']
    lh = pg['trim_h'] - pg['margin_top'] - pg['margin_bottom']
    x0, y0, x1, y1 = d.bounds()
    w_mm, h_mm = (x1 - x0) * UNIT_MM[d.units], (y1 - y0) * UNIT_MM[d.units]
    rows = []
    for s in d.t['scales']:
        wp, hp = w_mm * PT_PER_MM / s['scale'], h_mm * PT_PER_MM / s['scale']
        rows.append((s['scale'], wp, hp, wp <= lw and hp <= lh, s.get('use', '')))
    return dict(live=(lw, lh), size_mm=(w_mm, h_mm), rows=rows)
