"""The HL command's choices, worked out without Rhino: the roles a layer draws as, a role guessed from a layer's
name, the roles of a drawing's layers with where each came from, the request written from the dialog's choices, the
standard views and a frame round what is drawn, and a fault of the model said in plain words with its fix.
rhino/hidden_lines.py's dialog reads it from beside itself; tests/run.py checks it (group hl)."""
import errno, math, os, re, sys

ROLE_KEY = 'kit.hl.role'         # a layer's user text holding its role
SKIP = 'skip'
# key, as the dialog lists it, what it is for, its group in the request (None: not collected)
ROLES = (
    ('building', 'Building', 'walls, floors, roofs, stairs: cut and outlined',
     dict(layer='DETAIL', profile_layer='OUTLINE', body='building')),
    ('detail', 'Building detail', 'windows, doors, rails, mullions, beams', dict(layer='DETAIL', body='building')),
    ('furniture', 'Furniture', 'furniture, fixtures, counters', dict(layer='FURNITURE')),
    ('texture', 'Texture', 'roof tiles, cladding, brick', dict(layer='TEXTURE')),
    ('context', 'Context', 'neighbouring buildings, streets', dict(layer='CONTEXT')),
    ('ground', 'Ground', 'terrain, base, grass, curbs', dict(layer='CONTEXT', ground=True)),
    ('trees', 'See-through', 'trees and planting: drawn, hide nothing', dict(layer='CONTEXT', hides=False)),
    ('lines', 'Lines on the ground', 'grids, lot lines, door swings', dict(layer='FLOOR')),
    ('hides', 'Hides, not drawn', 'hides what is behind it', dict(draw=False)),
    (SKIP, 'Leave out', 'Make2D drawings, notes, figures', None),
)
LABEL = {k: lab for k, lab, _, _ in ROLES}
# words in a layer's name, whole or with a plural s, in the order tried: the first role with a word in the name wins.
# Leave out is tried over the whole path; the rest over the layer's own name, then its parents' from the nearest.

WORDS = (
    (SKIP, 'make2d hl plan plans axo axon axonometric section elevation layout anno annotation dim dims dimension '
           'text label note figure people person camera clipping drawing 2d poche construction guide arrow '
           'hatch scrap'),
    ('ground', 'ground terrain topo topography landform earth grade base grass lawn curb kerb soil'),
    ('trees', 'tree vegetation planting plant shrub foliage hedge bush greenery'),
    ('texture', 'tile tiling texture cladding shingle siding brick'),
    ('lines', 'line swing grid lot property parcel setback marking contour'),
    ('context', 'context neighbour neighbor neighbouring neighboring surrounding existing adjacent sitebuilding '
                'street city'),
    ('furniture', 'furniture furnishing chair table desk bed sofa couch cabinet shelf shelving casework fixture '
                  'kitchen bedroom bathroom washroom toilet sink counter appliance'),
    ('detail', 'detail facade glass glazing window door mullion frame railing rail handrail balustrade guardrail beam '
               'joist rafter purlin louvre louver trim'),
    ('building', 'building house wall floor floorplate slab roof stair column core elevator shaft structure'),
)
_RX = [(role, re.compile(r'\b(?:%s)(?:s|es)?\b' % '|'.join(re.escape(w) for w in sorted(words.split(), key=len,
       reverse=True)))) for role, words in WORDS]
_PHRASES = {'scale figure': SKIP, 'site element': 'ground'}


def words_of(name):
    """a layer name as lower-case words: 'Roof Tiles' 'roof tiles', 'base/ground' 'base ground', 'GlassDoor' 'glass
    door'"""
    name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
    return ' '.join(re.findall(r'[a-z0-9]+', name.lower()))


def role_of_name(name, roles=None):
    """the first role of WORDS (of roles, when given) with a word in the layer name, or None"""
    w = words_of(name)
    for ph, role in _PHRASES.items():
        if (roles is None or role in roles) and re.search(r'\b%ss?\b' % ph, w):
            return role
    for role, rx in _RX:
        if (roles is None or role in roles) and rx.search(w):
            return role
    return None


def guess(path):
    """the role a layer's full path suggests, or None: Leave out where any part of the path asks for it, else the role
    of its own name, else of its nearest parent's"""
    parts = path.split('::')
    if any(role_of_name(p, (SKIP,)) for p in parts):
        return SKIP
    rest = tuple(k for k, _, _, _ in ROLES if k != SKIP)
    for p in reversed(parts):
        r = role_of_name(p, rest)
        if r:
            return r
    return None


def resolve(paths, stored):
    """{full path: (role, how)} for the layers given, from the roles stored on layers ({full path: role}): how is 'set'
    (stored on the layer), 'parent' (a parent's stored Leave out, or its stored role where the name suggests none),
    'name' (guessed from its name or a parent's; a Leave out word above the nearest parent with a stored role does not
    count, so setting Plans to building draws Plans::Walls) or 'default' (building)"""
    keys = set(LABEL)
    out = {}
    for p in paths:
        if stored.get(p) in keys:
            out[p] = (stored[p], 'set')
            continue
        parts = p.split('::')
        anc = ['::'.join(parts[:i]) for i in range(len(parts) - 1, 0, -1)]   # nearest first
        up = next((a for a in anc if stored.get(a) in keys), None)
        if up and stored[up] == SKIP:
            out[p] = (SKIP, 'parent')
            continue
        below = '::'.join(parts[len(up.split('::')):]) if up else p   # a role kept above settles the names above it
        own = guess(parts[-1]) if guess(below) != SKIP else SKIP
        if own:
            out[p] = (own, 'name')
        elif up:
            out[p] = (stored[up], 'parent')
        elif guess(p):
            out[p] = (guess(p), 'name')
        else:
            out[p] = ('building', 'default')
    return out


def glob_escape(path):
    """a layer path as a pattern for the request's layers that matches it alone"""
    return re.sub(r'([*?\[])', r'[\1]', path)


# depth bands at a quarter and three fifths of how far the subject runs beyond the cut
DEPTH_SHARE = (0.25, 0.6)


def request_from(name, scale, roles, objects=None, cut=None):
    """the request the dialog's choices draw, without its view: a group a role in ROLES' order holding the layers
    given it ({full path: role}), Leave out collecting nothing; objects, ids, the objects drawn; cut, the role whose
    group the clip planes cut (on CUT)"""
    groups = []
    for key, _, _, group in ROLES:
        mine = sorted(p for p, r in roles.items() if r == key)
        if group is None or not mine:
            continue
        g = dict(id=key, layers=[glob_escape(p) for p in mine])
        g.update(group)
        groups.append(g)
    req = dict(id=name, title=name, scale=scale, groups=groups, depth_bands_share=list(DEPTH_SHARE))
    if objects is not None:
        req['objects'] = sorted(objects)
    return with_cut(req, cut) if cut else req


def with_cut(req, gid):
    """the request with group gid on CUT, its profile layer dropped: what a section cuts is drawn as cut"""
    return dict(req, groups=[dict((k, v) for k, v in dict(g, layer='CUT').items() if k != 'profile_layer')
                             if gid in (g['id'], g.get('of')) else g for g in req['groups']])


# key, as the dialog lists it, the way it looks, up the page; Rhino's own views
VIEWS = (
    ('top', 'Top', (0, 0, -1), (0, 1, 0)),
    ('front', 'Front', (0, 1, 0), (0, 0, 1)),
    ('right', 'Right', (-1, 0, 0), (0, 0, 1)),
    ('back', 'Back', (0, -1, 0), (0, 0, 1)),
    ('left', 'Left', (1, 0, 0), (0, 0, 1)),
    ('bottom', 'Bottom', (0, 0, 1), (0, 1, 0)),
    ('sw', 'Southwest isometric', (1, 1, -1), (0, 0, 1)),
    ('se', 'Southeast isometric', (-1, 1, -1), (0, 0, 1)),
    ('ne', 'Northeast isometric', (-1, -1, -1), (0, 0, 1)),
    ('nw', 'Northwest isometric', (1, -1, -1), (0, 0, 1)),
)
SUBJECT = ('building', 'detail', 'furniture', 'texture')   # the roles a frame fits round when any is drawn


def _unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return tuple(x / n for x in v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def axes(direction, up):
    """(right, up the page, the way it looks), unit vectors, as rhino/hidden_lines.py's view_of sets them"""
    d = _unit(direction)
    if math.sqrt(sum(x * x for x in _cross(d, up))) < 1e-9:   # looking straight along up: north up the page
        up = (0, 1, 0)
    r = _unit(_cross(d, up))
    return r, _cross(r, d), d


def frame_round(points, direction, up, pt_per_unit, margin_pt=18.0):
    """(view, frame) of a parallel view looking along direction that holds the points (model units) with margin_pt
    round them on paper, the frame's middle on their middle, the target at their middle depth"""
    r, u, d = axes(direction, up)
    xs, ys, zs = ([_dot(p, a) for p in points] for a in (r, u, d))
    cx, cy, cz = ((min(v) + max(v)) / 2.0 for v in (xs, ys, zs))
    target = [round(cx * r[i] + cy * u[i] + cz * d[i], 6) for i in range(3)]
    w = (max(xs) - min(xs)) * pt_per_unit + 2 * margin_pt
    h = (max(ys) - min(ys)) * pt_per_unit + 2 * margin_pt
    return (dict(direction=list(_unit(direction)), up=list(up), target=target),
            dict(w_pt=round(w, 2), h_pt=round(h, 2)))


def slug(text):
    """a drawing's default name from a view's: 'Section: plane A' 'section-plane-a'"""
    return re.sub(r'[^a-z0-9.]+', '-', text.lower()).strip('-') or 'drawing'


def out_folder(model_path, name, documents):
    """the folder a drawing without a request file goes in: beside the model, in '<model> HL', or for a model never
    saved in documents/HL, documents being the system's Documents folder (OneDrive's, where Windows moved it there)"""
    if model_path:
        stem = os.path.splitext(os.path.basename(model_path))[0]
        return os.path.join(os.path.dirname(model_path), stem + ' HL', name)
    return os.path.join(documents, 'HL', name)


# a fault the export or kit.py hidden-lines reports on an object, as its issue begins: its kind, a few words, what is
# wrong, the fix (rhino/MODELLING.md); in the order the results window lists them
FAULTS = (
    ('invalid', r'invalid (brep|mesh)', 'Invalid object', 'Rhino reports the object as invalid.',
     'Run Check on it, then ExtractSrf and rebuild the bad faces, or rebuild it.'),
    ('open', r'open (polysurface|mesh)', 'Not closed',
     'It is open, so a section cannot fill its cut and it hides nothing through its gaps.',
     'ShowEdges (Naked edges), then Cap or Join. A surface by nature stays one surface.'),
    ('self-crossing-face', r'\d+ faces cross their own', 'Face crosses itself',
     'A face crosses its own boundary: it was extruded from a profile that crosses itself.',
     'Redraw the profile so it does not cross itself and extrude it again.'),
    ('non-manifold', r'\d+ non-manifold|non-manifold mesh', 'Edge shared by 3 faces',
     'An edge is shared by three or more faces.', 'ShowEdges (Non-manifold edges); Explode and join the parts that belong together.'),
    ('inside-out', r'inside out', 'Inside out', 'The solid is turned inside out and reads as a hole.', 'Flip it (Dir).'),
    ('turned', r'faces the same way as', 'Surface faces into the wall', 'It faces into the wall, the same way as the '
     'surface beside it, where a wall\'s two surfaces face away from each other. The drawing reads it facing out.',
     'Flip it (Dir), or join the wall\'s surfaces into a closed solid.'),
    ('runs-into', r'runs into', 'Runs into another solid', 'It runs into another solid, and both are drawn there.',
     'BooleanUnion them if they are one thing, or BooleanDifference one from the other.'),
    ('lies-on', r'lies on', 'Face lies on another', 'A face lies on another facing the same way, and only the earlier '
     'group\'s is drawn.', 'Trim one to the other, or lift the upper one a millimetre.'),
    ('unjoined-edge', r'shares an edge with', 'Unjoined edge', 'It shares an edge with another surface without being joined.',
     'Join them.'),
    ('union-failed', r'union with', 'Parts would not union', 'Its parts would not union into one closed solid, so they '
     'are drawn apart.', 'Close each part, then BooleanUnion them in the model.'),
    ('cut-open', r'the cut by clip plane', 'Cut does not close', 'Its cut by the section does not close.', 'Close the solid.'),
    ('ring-mismatch', r'its ring and its clipped mesh disagree', 'Cut and mesh disagree', 'Its cut by the section and '
     'its mesh\'s cut lie further apart than the mesh\'s own error explains, and the drawing cuts along the mesh there.',
     'Compare the drawn cut with the model there, then Check it and rebuild the face the section crosses, or the solid.'),
    ('nearly-planar', r'\d+ faces nearly planar', 'Face nearly flat', 'A face meant to be flat is a little off flat.',
     'Move the stray points onto the plane, or rebuild the face from planar curves.'),
    ('creased', r'(\d+ faces )?creased inside', 'Face creased inside', 'A face is creased inside, where no line is drawn.',
     'DivideAlongCreases on it.'),
    ('short-edges', r'\d+ edges under', 'Very short edges', 'It has edges shorter than ten tolerances, which print as '
     'strays.', 'Rebuild the outline without the slivers and notches, or MergeEdge the short edges.'),
    ('duplicate', r'duplicate of', 'Possible duplicate', 'It may duplicate another object: their boxes and counts '
     'match within ten tolerances, but their faces were not compared.', 'Compare the two; if they are the same, delete '
     'one (SelDup finds exact ones).'),
    ('curve-in-solids', r'a curve among', 'Curve among solids', 'A curve on a layer of solids is drawn as a line.',
     'Give its layer the role Lines on the ground, or Leave out.'),
    ('both-ways', r'mesh faces point both ways', 'Mesh faces point both ways', 'Its mesh faces point both ways.',
     'UnifyMeshNormals.'),
    ('far', r'more than .* km from the origin', 'Far from the origin', 'It lies far from the origin, where precision '
     'suffers.', 'Move the model near the origin, less a recorded offset.'),
    ('no-mesh', r'no mesh', 'No mesh', 'Rhino could not mesh it.', 'Rebuild it; Check says why.'),
)
GUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')


def plain(issue, kind=None):
    """(kind, a few words, what is wrong, the fix) of an issue string of the report, or of its kind where the report
    gives one; an issue of no kind known is said as written"""
    for k, rx, short, say, fix in FAULTS:
        if kind == k or (kind is None and re.match(rx, issue)):
            return k, short, say, fix
    text = issue[:1].upper() + issue[1:]
    return kind or 'other', text[:40], text + '.', ''


def meant_open(req, layer):
    """whether the request draws layer as a sheet meant to be open: in a group of the ground or on TEXTURE (the ground's
    pieces, roof tiles), where an open polysurface is not a fault"""
    import fnmatch
    g = next((g for g in req.get('groups', []) if any(fnmatch.fnmatchcase(layer, p) for p in g['layers'])
              and not any(fnmatch.fnmatchcase(layer, p) for p in g.get('not_layers', []))), None)
    return bool(g) and (bool(g.get('ground')) or g.get('layer') == 'TEXTURE')


def fault_rows(issues, req=None):
    """the results window's rows from the report's issues ({ids, layer, issue, kind}) or check.json's objects ({ids,
    layer, issues}): a row a kind of fault and a layer, in FAULTS' order, with the objects that have it and any other
    object their issues name, and the issues as written; with the request, an open sheet meant to be open is left out"""
    order = {k: n for n, (k, _, _, _, _) in enumerate(FAULTS)}
    rows, at = [], {}
    for x in issues:
        for issue in ([x['issue']] if 'issue' in x else x.get('issues', [])):
            kind, short, say, fix = plain(issue, x.get('kind'))
            if kind == 'open' and req is not None and meant_open(req, x.get('layer', '')):
                continue
            key = (kind, x.get('layer', ''))
            if key not in at:
                at[key] = dict(kind=kind, layer=key[1], short=short, say=say, fix=fix, objects=[], ids=[], issues=[])
                rows.append(at[key])
            r = at[key]
            if x['ids'][0] not in r['objects']:
                r['objects'].append(x['ids'][0])
            r['ids'] += [g for g in list(x['ids']) + GUID.findall(issue) if g not in r['ids']]
            r['issues'].append(issue)
    return sorted(rows, key=lambda r: (order.get(r['kind'], len(order)), r['layer']))


AREA = ('unresolved cell',)                  # a suspect's measure is in pt2 for these, pt for the rest
ACTION = dict(repaired='The drawing repaired it; the fault stays in the model.',
              removed='The drawing took it out; the fault stays in the model.',
              left='It is left in the drawing as it is.')


def suspect_rows(suspects, layer_of=None):
    """the results window's rows for the report's suspects ({at_pt, model, what, why, ids, kinds, confidence, measure,
    action}): what was left in the drawing first, then repaired, then removed, traced causes before near ones; layer_of,
    an id's layer, names the layer"""
    rank = dict(left=0, repaired=1, removed=2)
    rows = []
    for x in suspects:
        traced = x.get('confidence') == 'traced'
        what = x.get('what', 'artifact')
        m = x.get('measure')
        unit = 'pt2' if what in AREA else 'pt'
        fix = next((f for k in x.get('kinds', []) for kk, _, _, _, f in FAULTS if kk == k), '')
        ids = list(x.get('ids', []))
        rows.append(dict(
            kind='suspect', layer=(layer_of(ids[0]) if layer_of and ids else '') or '',
            short=what[:1].upper() + what[1:] + ('' if traced else ', near a fault'),
            say=('%s%s. %s%s' % ('Caused by: ' if traced else 'Not traced to it, but near an object with a fault: ',
                                 x.get('why', ', '.join(x.get('kinds', []))), ACTION.get(x.get('action'), ''),
                                 '' if m is None else ' (%.2g %s)' % (m, unit))),
            fix=fix, objects=ids[:1], ids=ids, issues=[x.get('why', '')], at_pt=x.get('at_pt'),
            rank=(rank.get(x.get('action'), 3), not traced)))
    return sorted(rows, key=lambda r: r['rank'])


def top_rows(paths, res, count):
    """the streamlined list: a row a top-level layer, [(top, objects under it, its role, how, sublayers of another
    role)], from the resolved roles of the top layers and of the layers holding objects (res, {path: (role, how)}) and
    each layer's count"""
    out, seen = [], []
    for p in paths:
        top = p.split('::')[0]
        if top not in seen:
            seen.append(top)
    for top in seen:
        under = [p for p in paths if p == top or p.startswith(top + '::')]
        role, how = res[top]
        other = sum(1 for p in under if p != top and res[p][0] != role)
        out.append((top, sum(count[p] for p in under), role, how, other))
    return out


BIG = 2000      # objects drawn with nothing selected past which Draw asks first: the model's 3,312 took 43 minutes to export
WEIGHTS = (('house', 'HL weights (recommended)'), ('layers', 'From my layers'), ('single', 'One weight per role'))
WEIGHTS_SAY = dict(
    house='Outlines heaviest, the lines inside them lighter by what they are, at weights the scale sets.',
    layers='Each layer\'s outline at its own print width (Layer panel), the lines inside lighter; a layer with no '
           'width set takes HL\'s.',
    single='Every line of a role at one weight, as Make2D draws, to set after in Illustrator or Rhino.')
LAYER_TREES = (('role', 'By role (recommended)'), ('model', 'As in my model'))
LAYER_TREES_SAY = dict(
    role='Draws by role, then kind of line and distance, on HL\'s layers.',
    model='Draws each line under the layer of your model it came from, by kind of line; prints the same.')
WHY = dict(set='set by you', name='its name', parent='its parent', default='not a name HL knows')


def layer_tree_choice(saved, user):
    keys = [k for k, _ in LAYER_TREES]
    return saved if saved in keys else user if user in keys else 'role'


def layer_tree(data, mode='role', order=None):
    """the Rhino leaves, relative to the drawing root, and each curve's user text and object print attributes.
    Fills keep their kit layer; a merged fill need not belong to a single model layer. In model mode the source layers
    come in the model's order (order, {full path: Rhino's sort index}; a path missing from it after, by name), each
    one's classes in the standard's order."""
    leaves = []
    by_path = {}
    for L in reversed(data['layers']):
        for s in sorted(L['subs'], key=lambda s: sublayer_order(s['name'])):
            role_path = [L['id']] + (s['name'].replace(' › ', '::').split('::') if s['name'] else [])
            weight = s['weight_mm'] if L['print'] else -1.0
            if mode == 'role':
                leaf = dict(path=role_path, ink=L['ink'], weight_mm=weight, dash=L['dash'], dash_model=L['dash_model'],
                            lines=[], fills=s['fills'])
                leaves.append(leaf)
            elif s['fills']:
                leaves.append(dict(path=role_path, ink=L['ink'], weight_mm=weight, dash=L['dash'],
                                   dash_model=L['dash_model'], lines=[], fills=s['fills']))
            for ln in s['lines']:
                obj = data['objects'][ln['source']]
                if mode == 'model':
                    path = obj['layer'].split('::') + [s['kind']]
                    key = tuple(path)
                    if key not in by_path:
                        by_path[key] = dict(path=path, ink=L['ink'], weight_mm=weight, dash=L['dash'],
                                            dash_model=L['dash_model'], lines=[], fills=[])
                        leaves.append(by_path[key])
                    leaf = by_path[key]
                attributes = dict(user_text={'hl.layer': obj['layer'], 'hl.object': ', '.join(obj['ids'])})
                if mode == 'model':
                    attributes.update(weight_mm=weight, ink=L['ink'], dash=L['dash'], dash_model=L['dash_model'])
                leaf['lines'].append(dict(ln, attributes=attributes))
    if mode == 'model':
        order = order or {}

        def key(leaf):
            src = leaf['path'][:-1]
            return ([(order.get('::'.join(src[:i + 1]), len(order)), src[i].lower()) for i in range(len(src))],
                    RANK.index(leaf['path'][-1]) if leaf['path'][-1] in RANK else len(RANK))
        leaves = [leaf for leaf in leaves if not leaf['lines']] + sorted((leaf for leaf in leaves if leaf['lines']), key=key)
    return leaves


def weights_choice(saved, user, widths):
    """the line weights the dialog opens on: the model's saved choice; else From my layers where two or more of the
    layers drawn have print widths set that differ (widths, mm, 0 or less being unset); else the user's last choice in
    any model; else HL's"""
    keys = [k for k, _ in WEIGHTS]
    if saved in keys:
        return saved
    if len(set(round(w, 3) for w in widths if w > 0)) >= 2:
        return 'layers'
    return user if user in keys else 'house'


def why(how, differ=0):
    """the layer list's Why: how a row's role was chosen, and how many sublayers draw in another"""
    return WHY[how] + ('; %d sublayer%s differ%s' % (differ, '' if differ == 1 else 's', 's' if differ == 1 else '')
                       if differ else '')


def unknown_notice(res, paths):
    """a line for the dialog, the command line and the log when layers drawn (paths) take their role by default (res,
    {path: (role, how)}): HL knew none of their names to guess from; None when it knew every one"""
    drawn = [p for p in paths if res[p][0] != SKIP]
    n = sum(1 for p in drawn if res[p][1] == 'default')
    if not n:
        return None
    if n == len(drawn):
        return ('HL recognised none of these layer names, so every layer draws as Building. Set each layer\'s role '
                'under Draws as: Context for neighbours, Ground for terrain, Furniture, See-through for trees.')
    if n == 1:
        return ('HL didn\'t recognise 1 of these layer names, so it draws as Building. If it is context, ground, '
                'furniture or trees, set its role under Draws as.')
    return ('HL didn\'t recognise %d of these layer names, so they draw as Building. If some are context, ground, '
            'furniture or trees, set their role under Draws as.' % n)


def removal(n_roles, choices):
    """(the question before Remove HL's settings from this model, the line after it) for the roles HL kept on n_roles
    layers and, with choices, the dialog's remembered choices; None when the model holds neither"""
    what = (['the role HL kept on 1 layer' if n_roles == 1 else 'the roles HL kept on %d layers' % n_roles]
            if n_roles else []) + (["the dialog's remembered choices"] if choices else [])
    if not what:
        return None
    w = ' and '.join(what)
    return ('Remove %s from this model? The drawings on HL\'s layers stay: delete those yourself if you want them '
            'gone.' % w, 'Removed %s from this model. The drawings on HL\'s layers are as they were.' % w)


def with_lines(req, depth, merge, hidden=False):
    """the request with lines lighter with distance or not (depth: its own depth bands, else DEPTH_SHARE's), lines
    closer than they print merged or kept (merge: simplify_doubles, which the engine takes as false when absent), and
    the lines hidden behind surfaces drawn dashed or not (hidden: show_hidden, false when absent)"""
    out = dict(req)
    if not depth:
        out.pop('depth_bands_share', None)
        out.pop('depth_bands_m', None)
    elif not out.get('depth_bands_share') and not out.get('depth_bands_m'):
        out['depth_bands_share'] = list(DEPTH_SHARE)
    if merge:
        out['simplify_doubles'] = True
    else:
        out.pop('simplify_doubles', None)
    if hidden:
        out['show_hidden'] = True
    else:
        out.pop('show_hidden', None)
    return out


# the files Also save offers: key, the box, the file in a sentence
SAVES = (('ai', 'Illustrator (.ai)', 'an Illustrator file'), ('svg', 'SVG', 'an SVG'), ('dxf', 'DXF', 'a DXF'))


def destination(name, add, parent, folder, home=None, saves=()):
    """where the drawing goes, in a sentence for the dialog: the model, and the files of saves (keys of SAVES)"""
    if home and (folder + os.sep).startswith(home.rstrip(os.sep) + os.sep):
        folder = '~' + folder[len(home.rstrip(os.sep)):]
    said = [w for k, _, w in SAVES if k in saves]
    files = '%s in %s' % (', '.join(said[:-1]) + ' and ' + said[-1] if len(said) > 1 else said[0], folder) if said else ''
    if add:
        return 'Adds the drawing to this model under the layer %s::%s%s.' % (parent, name, ', and saves ' + files
                                                                             if files else '')
    if files:
        return 'Saves %s. Nothing is added to the model.' % files
    return 'Nothing to make: tick Add the drawing to this model, or a file under Also save.'


# what kit.py lint finds in a drawing (archkit/lint.py), in plain words: a few words, what it is, what to do
LINT = dict(
    (k, (short, say, fix)) for k, short, say, fix in (
        ('near-miss', 'Line stops short', 'A line ends just short of another, which prints as a small gap.',
         'Most come from a fault in the model listed here; fix it and draw again, or close the gap in the drawing.'),
        ('open-cut', 'Cut outline open', 'An outline of what the section cuts does not close, so it cannot be filled '
         'or hatched.', 'The solid it cuts is open or faulty (listed here); close it and draw again.'),
        ('stray', 'Short stray line', 'A short piece of line stands free, which prints as a speck.',
         'Delete it in the drawing, or fix the short edges or slivers in the model that make it.'),
        ('duplicate', 'Line drawn twice', 'Two lines lie on each other. It prints as one line.',
         'Delete one in the drawing if it matters, or a duplicate object in the model.'),
        ('double', 'Lines side by side', 'Two lines run under 0.6 pt apart, which prints as one thick line.',
         'Tick Merge close lines and draw again, or delete one in the drawing.'),
        ('weight', 'Line weight off its layer', 'A line\'s weight differs from the weight its layer is drawn at.',
         'HL\'s error, not the model\'s: report it with the drawing\'s folder.'),
        ('colour', 'Colour off the standard', 'A line\'s colour is not one of the house standard\'s.', ''),
        ('label', 'Label crosses a line', 'A label crosses a line.', '')))
LINT_LINE = re.compile(r'^\s*(error|warning)\s+([a-z-]+)\s+(.*)$')
AT = re.compile(r'\((-?[\d.]+), (-?[\d.]+)\)')


def where(row):
    """the results window's Where: the objects a row selects, or the places in the drawing a lint row does"""
    n = len(row['issues']) if row['kind'] == 'lint' else len(row['objects'])
    return ('%d place%s in the drawing' if row['kind'] == 'lint' else '%d object%s') % (n, '' if n == 1 else 's')


def lint_rows(lines, k=None, h_pt=None):
    """the results window's rows for what kit.py lint printed (lines): a row a kind, errors first, each finding once,
    with where each lies in the drawing as added to the model (places, model units), given k (pt per model unit at
    the drawing's scale) and the frame's height (h_pt)"""
    rows, at = [], {}
    for line in lines:
        m = LINT_LINE.match(line)
        if not m:
            continue
        level, kind, text = m.groups()
        if kind not in at:
            short, say, fix = LINT.get(kind, (kind.replace('-', ' ').capitalize(), text, ''))
            at[kind] = dict(kind='lint', level=level, layer=text.split(':')[0], short=short, say=say, fix=fix,
                            objects=[], ids=[], issues=[], places=[])
            rows.append(at[kind])
        r = at[kind]
        if text in r['issues']:
            continue
        r['issues'].append(text)
        p = AT.findall(text)
        if p and k:
            x, y = float(p[-1][0]), float(p[-1][1])
            r['places'].append((x / k, (h_pt - y) / k))
    for r in rows:
        n = len(r['issues'])
        r['short'] += '' if n == 1 else ' (%d)' % n
    return sorted(rows, key=lambda r: r['level'] != 'error')
CLASSES = ('profile', 'base', 'overlap', 'step', 'seam', 'crease', 'line')   # the visible classes; a cut keeps its own


RANK = ('cuts', 'open cuts', 'profiles', 'bases', 'overlaps', 'steps', 'seams', 'creases', 'lines', 'hidden', 'above')
BAND = re.compile(r' (?:under ([\d.]+)|([\d.]+)-[\d.]+|past ([\d.]+)) m$')     # a sublayer's depth band, at its end


def sublayer_order(name):
    """a key ordering a drawing's sublayers in Rhino's layer panel: by group, then class as the standard weights them,
    then distance from near to far; also accepts the old flat metre names"""
    name = name.replace(' › ', '::')
    if '::' in name:
        base, distance = name.split('::', 1)
        words = distance.split(' (', 1)[0].split()
        band = 0 if words[0] == 'near' else float('inf') if words[0] == 'far' else int(words[1]) if len(words) > 1 else 1
        key = sublayer_order(base)
        return (key[0], key[1], band, name)
    m = BAND.search(name)
    band = (0.0 if m.group(1) else float(m.group(2)) if m.group(2) else float('inf')) if m else -1.0
    words = (name[:m.start()] if m else name).split()
    for k in (2, 1):
        if len(words) > k and ' '.join(words[-k:]) in RANK:
            return (' '.join(words[:-k]), RANK.index(' '.join(words[-k:])), band, name)
    own = {'profile': 'profiles', 'base': 'bases', 'overlap': 'overlaps', 'step': 'steps',
           'seam': 'seams', 'crease': 'creases', 'line': 'lines', 'cut': 'cuts'}
    rank = own.get(name, name)
    return (' '.join(words), RANK.index(rank) if rank in RANK else len(RANK), band, name)


def stale_layers(counts, root):
    """the layers under root (counts: {full path: objects on it}) that hold nothing, themselves or under them, deepest
    first: what a drawing run again leaves empty"""
    under = [p for p in counts if p.startswith(root + '::')]
    full = set(p for p in under if counts[p])
    for p in list(full):
        while '::' in p:
            p = p.rsplit('::', 1)[0]
            full.add(p)
    return sorted((p for p in under if p not in full), key=lambda p: -p.count('::'))


def with_weights(req, mode, roles=None, widths=None, band_of=None):
    """the request with its line weights chosen: house, as it is; layers, each layer with a print width set (widths,
    {path: mm}) a group of its own, its role's ({path: group id}) but outlined at that width (`of` naming the role's
    group), its other classes stepping down the house's weights as before, a layer with none keeping its role's house
    weights; single, every visible class of a group at the house weight of its layer (band_of, a token layer id to its
    band name), cuts as they are and no depth bands, as Make2D draws"""
    if mode == 'house':
        return req
    out = dict(req, groups=[dict(g) for g in req['groups']])
    if mode == 'layers':
        groups, ids = [], set(g['id'] for g in out['groups'])
        for g in out['groups']:
            own = sorted(p for p, r in (roles or {}).items() if r == g['id'] and (widths or {}).get(p, 0) > 0)
            groups.append(dict(g, not_layers=list(g.get('not_layers', [])) + [glob_escape(p) for p in own])
                          if own else g)
            for p in own:                              # its own group, named for the drawing's sublayers
                gid = '%s %s' % (g['id'], p.split('::')[-1])
                while gid in ids:
                    gid += "'"
                ids.add(gid)
                groups.append(dict(g, id=gid, of=g['id'], layers=[glob_escape(p)],
                                   profile_weight=round(widths[p] * 72.0 / 25.4, 3)))
        out['groups'] = groups
        return out
    out.pop('depth_bands_share', None)
    out.pop('depth_bands_m', None)
    for g in out['groups']:
        if g.get('draw', True):                        # what a plane cuts is seen beyond it, as hidden.py draws it
            lid = 'BEYOND' if g.get('layer') == 'CUT' else g.get('layer', 'CONTEXT')
            g['weights'] = dict(g.get('weights') or {}, **{c: band_of(lid) for c in CLASSES})
    return out


# the drawing step's peak memory footprint (kit.py hidden-lines --rhino, macOS's default malloc), three runs on each of
# 15 exports: 0.2 GB for small sections to 4.9 GB for a large perspective section (6,837,591 triangles, 116,333
# segments) and 5.3 GB on its exterior (6,196,825, 98,429), on frames of 372 x 444 to 1,340 x 1,500 pt. The least plane
# over each drawing's highest run less 200 bytes a square point of its frame, raised by 0.89 GB, the most a drawing ran
# over the plane fitted to the other 14, and rounded up. With triangles the frame costs most where the subject fills
# it in a section with depth bands by share: the ID buffer, rasterized a tile at a time (hiddenlines/idbuf.py), stays
# under 1 GB, and the bands read a pixel a point, 64 bytes each in a section (hidden.py), so two triangles filling
# 8,000 x 4,800 pt peaked at 4.1 GB (2.6 with MallocLargeCache=0), 96 bytes a square point over frames of a million and
# more, counted as 97; with no triangle nothing is rasterized. Every run of the drawing step since, on the 15 exports
# and on such frames, is at least 0.54 GB under it
GB_BASE, GB_PER_TRIANGLE, GB_PER_SEGMENT, GB_PER_PT2 = 1.4, 0.52e-6, 14e-6, 0.097e-6


def need_gb(triangles, segments, page_pt2):
    """the memory the drawing step needs for an export of triangles and segments on a frame of page_pt2 square points,
    in GB"""
    page = GB_PER_PT2 * page_pt2 if triangles else 0.0
    return GB_BASE + GB_PER_TRIANGLE * triangles + GB_PER_SEGMENT * segments + page


def memory_problem(triangles, segments, w_pt, h_pt, have_gb):
    """a question when the drawing step would need over 0.8 of the computer's memory (have_gb) for a frame of w_pt x
    h_pt, else None; it names the sheet where the sheet takes more of it than the triangles"""
    need = need_gb(triangles, segments, w_pt * h_pt)
    if not have_gb or need <= 0.8 * have_gb:
        return None
    gb = lambda x: ('%.1f' if x < 10 else '%.0f') % x
    sheet = ''
    if triangles and GB_PER_PT2 * w_pt * h_pt > GB_PER_TRIANGLE * triangles:
        sheet = ' on a sheet %.1f by %.1f m' % (w_pt / 72.0 * 0.0254, h_pt / 72.0 * 0.0254)
    return ('This drawing needs about %s GB of memory for its %s triangles%s, and this computer has %s GB. It may run '
            'very slowly or stop. Draw it anyway?' % (gb(need), '{:,}'.format(triangles), sheet, gb(have_gb)))


# what the drawing step prints when the Python or packages HL downloaded are damaged or missing
DAMAGED = re.compile(r'ModuleNotFoundError|No module named|ImportError|DLL load failed|Library not loaded|'
                     r'image not found|cannot open shared object|error: Failed to (fetch|download|install|extract|read)|'
                     r'invalid (ELF|Mach-O)|bad CRC|unexpected end of (data|file)', re.I)


def damaged(text):
    """whether the drawing step's output says its Python or packages are damaged or missing"""
    return bool(DAMAGED.search(text or ''))


REPO = 'https://github.com/kenny-t-vo/hidden-lines'     # HL's public repository, its name set at release
AUTHOR, LICENCE = 'Kenny Vo', 'MIT'
LATEST = REPO.replace('https://github.com/', 'https://api.github.com/repos/') + '/releases/latest'
UPDATE_EVERY = 86400   # s between HL's asks of GitHub for its latest release


def short_version(v):
    """a plug-in's version as people read it, 0.1.3 of 0.1.3.13300 or 0.1.3+13300; None for the kit run from a
    checkout"""
    return '.'.join(str(v).split('+')[0].split('.')[:3]) if v else None


def newer(tag, current):
    """whether a release tag (v1.0.1) is newer than the version running"""
    def key(v):
        return [int(x) for x in re.findall(r'\d+', str(v))[:3]]
    try:
        return bool(tag) and bool(current) and key(tag) > key(current)
    except ValueError:
        return False


def update_due(cache, now):
    """whether HL asks GitHub for its latest release again: a day after it last asked, answered or not, from the
    cache's checked (s since the epoch); a checked in the future, from a clock set wrong, asks again"""
    return not 0 <= now - (cache or {}).get('checked', 0) < UPDATE_EVERY


def issue_url(version, rhino, system):
    """a new issue on HL's repository with the versions filled in, and nothing else"""
    from urllib.parse import quote
    body = 'HL %s\nRhino %s\n%s\n\nWhat happened, and what you expected:\n' % (version or 'from the kit', rhino, system)
    return '%s/issues/new?body=%s' % (REPO, quote(body))


AI_MAX_PT = 16383       # the widest artboard Illustrator takes, 5.78 m
PRINT_SCALES = (5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000)    # the scales the refusal suggests
A0_M = 1.189            # A0's long side, the largest sheet the suggested scale must fit


def far_ones(centres):
    """the ids of objects lying far from the rest, from [(id, (x, y, z))] of their boxes' centres: over ten times the
    middle object's distance from the middle centre, and further than 100 units"""
    if len(centres) < 3:
        return []
    mid = [sorted(c[i] for _, c in centres)[len(centres) // 2] for i in range(3)]
    dist = [(i, math.sqrt(sum((c[k] - mid[k]) ** 2 for k in range(3)))) for i, c in centres]
    typical = sorted(d for _, d in dist)[len(dist) // 2]
    return [i for i, d in dist if d > max(10 * typical, 100.0)]


def frame_problem(w_pt, h_pt, far=0, scale=None):
    """a sentence when the drawing's sheet would be wider than Illustrator takes, with far, the objects lying far from
    the rest, else None; without far objects it says the scale only sizes the paper, and with the drawing's scale it
    suggests the largest of PRINT_SCALES that fits A0"""
    if max(w_pt, h_pt) <= AI_MAX_PT:
        return None
    big = max(w_pt, h_pt) / 72.0 * 0.0254
    size = '%.0f km' % (big / 1000) if big >= 1000 else '%.0f m' % big
    say = 'The drawing would be %s across on paper, past the 5.8 m Illustrator takes. ' % size
    if far:
        one = far == 1
        return say + ('%d object%s far from the rest make%s it so, and %s selected: hide or move %s, or select what to '
                      'draw.' % (far, '' if one else 's', 's' if one else '', 'it is' if one else 'they are',
                                 'it' if one else 'them'))
    fits = [s for s in PRINT_SCALES if scale and s > scale and big * scale / s <= A0_M]
    such = ', such as 1:%d, where it would be %.1f m across' % (fits[0], big * scale / fits[0]) if fits else ''
    return say + ('The scale sets only the line weights and the size on paper of the SVG and Illustrator files: the '
                  'drawing HL adds to Rhino, and its DXF, are at the model\'s true size whatever the scale. Set the '
                  'scale you print at%s, or select what to draw.' % such)


WIN_MAX = 259           # the characters of a Windows path where long paths are not turned on


def long_path(folder, name):
    """a sentence when a file of the drawing would have a path past Windows' 260 characters, else None"""
    n = len(os.path.join(folder, max(name + '-report.json', 'request.json', key=len)))
    if n <= WIN_MAX:
        return None
    return ('The drawing\'s files would have paths of %d characters, past the 260 Windows takes. Choose a shorter '
            'folder under Advanced, Save files in, or a shorter name.' % n)


RESERVED = {'con', 'prn', 'aux', 'nul'} | {'com%d' % i for i in range(1, 10)} | {'lpt%d' % i for i in range(1, 10)}


def name_problem(name):
    """what is wrong with a drawing's name, which goes into file and layer names on Mac and Windows, or None"""
    if not name:
        return 'Give the drawing a name.'
    if len(name) > 80:
        return 'Keep the name under 80 characters: it goes into file names.'
    if not re.match(r'^\w[\w .-]*$', name):
        return 'The name goes into file names: use letters, digits, spaces, dots and dashes.'
    if name[-1] in '. ':
        return 'The name cannot end in a dot or a space: Windows refuses such files.'
    if name.split('.')[0].lower() in RESERVED:
        return '%s is a name Windows keeps for itself: choose another.' % name
    return None


def folder_problem(folder, error, exists=os.path.exists, mac=sys.platform == 'darwin'):
    """a plain sentence for a folder HL cannot write a drawing into, from the error, with what to do"""
    parts = os.path.abspath(folder).split(os.sep)
    if len(parts) > 2 and parts[1] == 'Volumes' and not exists(os.sep.join(parts[:3])):
        return ('The drive %s is not connected, so HL cannot save the drawing in %s. Connect it, or choose another '
                'folder under Advanced, Save files in.' % (parts[2], folder))
    # macOS refuses Rhino a folder it was not allowed (Documents, Desktop, Downloads, a drive) with EPERM; a folder's
    # own permissions give EACCES
    if mac and getattr(error, 'errno', None) == errno.EPERM:
        return ('macOS has not let Rhino save in %s. In System Settings, Privacy & Security, Files & Folders, turn '
                'on that folder under Rhino 8, or choose another folder under Advanced, Save files in.' % folder)
    why = ('it is not allowed to' if isinstance(error, PermissionError)
           else 'the system said: %s' % (getattr(error, 'strerror', None) or error))
    return ('HL cannot save the drawing in %s (%s). Choose another folder under Advanced, Save files in.'
            % (folder, why))
