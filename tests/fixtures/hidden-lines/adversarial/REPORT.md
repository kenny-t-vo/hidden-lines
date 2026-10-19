# Adversarial hidden-line scenes

## regression's rules

At `1288142`, the new constructions break the dropped-piece report and C's whole-run/loop and convergence rules, without changes to the engine. The failures below use expected answers calculated from source coordinates, triangle sections, pinhole projection and polygon distance bounds. A/B measurements for C's constructions are observations, not verdicts.

| Failure | Construction and expected answer | Measured answer | Suspected pass (each a guess) |
|---|---|---|---|
| Last stroke removed: `doubles-min-last-stroke-{A,B,C}` | One 0.08 pt segment, no mesh. Below the 0.2 pt floor: no ink, a stray reason, and an empty drawing or concise rejection. Deleting it receives the accepted empty-scene diagnostic. | No SVG or report; `ValueError: linestrings: Input operand 0 does not have enough dimensions (has 1, gufunc core with signature (i, d),-> requires 2)`. | `hiddenlines/hidden.py:273`: the drawn-source tree is constructed from an empty list. |
| Sub-pixel occlusion: `doubles-occluder-*` | One front triangle and one rear segment. At z=0, the triangle occupies exactly [-w/2,w/2]; the checked interior is hidden, and two long outside controls must remain. | 19/48 drawings contain 0.01–0.19 pt forbidden rear ink (limit 0.002 pt). At w=0.04, phase=0, A/B/C each draw 0.03 pt. | `hiddenlines/idbuf.py:386` and `:423`: pixel visibility and line sampling miss the sub-pixel interval. |
| Wrong reason: `doubles-occluder-0.24-phase{0,0.0625}-{A,B}` | The 0.24 pt rear interval is behind the triangle, so its reason must be behind a face; all front edges are visible. | Front boundary missing: 0 pt within 0.075 pt. Rear ink: 0 pt, but `model.dropped` calls 0.2 pt a thin face; `unexplained_pt` remains 0. | `hiddenlines/idbuf.py:386` misses the occlusion, then `hiddenlines/hidden.py:2960` takes the rear line as a thin face. |
| C bypassed by end cleanup: `doubles-min-hair-C` | Two parallel segments, 2 and 4 pt long, 0.418464567 pt apart. Subtract half the 0.15/0.10 pt strokes: 0.103528 mm white, over C's 0.1 mm; keep the lesser whole. | A/B/C lesser coverage: 0/0/0%; C removes 0 doubles, then `hair taken whole` removes 2.000 pt. | `hiddenlines/hidden.py:3314`: near-end cleanup uses near_pt after C rejected the double. |
| Convergence: `doubles-converge-1-C`, `doubles-min-convergence-C` | Two segments meet exactly. The former approaches at 1 degree over 15 pt; the primitive-minimal latter at 8 degrees over 2 pt. Both must reach their meeting along their own source. | A/B/C lesser coverage: 0/0/0%. The long case loses 15 pt to doubles; the short case loses 2.020 pt as a hair/stub. | C's branch at `hiddenlines/hidden.py:2509` lacks the convergence test of A/B; the short case is cleanup at `:3192`. |
| Whole-loop maximum missed: `doubles-reduced-loop-C` | Two disjoint loops, four and seven vertices, no faces. One 0.04 pt inward excursion exceeds C's centre threshold by 0.02 pt; keep the entire lesser loop. | A/B/C lesser coverage: 0/100/0%. C reports 60.9 pt dropped from the 60.941726 pt source, although its maximum gap is 0.428464567 pt. | `hiddenlines/hidden.py:2533`: maximum over samples, rather than every source stretch, misses the excursion. |
| Close rim retained: `doubles-reduced-rim-C` | Two disjoint closed polylines, three and four vertices, no faces. Maximum centre gap is 0.118180318 pt, below the 0.408464567 pt threshold; remove it whole. | A/B/C retained lesser ink: 0/46.82/47.07 pt (C expected 0), from a 47.343893 pt source. | `hiddenlines/hidden.py:2511` and `:2810`: grid-created junctions split a model loop into runs and landing tests keep parts. |

`reduced-*.json` are coordinate generators loaded by `doubles.py`. `minimise.py` recalculates its construction oracle after every deletion; it never derives the expectation from the drawing. Euclidean buffers are bracketed by 0.00001 pt, exceeding their polygonal approximation error. The loop's seven admissible single-vertex deletions all pass. The rim was reduced first by paired chord deletion, then individual vertices. Further vertex deletions unclose or intersect those loops, changing the whole-loop construction into junction runs; no exhaustive minimum over that different construction is claimed. Deleting either complete loop is also tested. The two-segment witnesses and the one-triangle/one-segment occlusion witnesses are primitive-minimal. The 45 failing variants map to these witnesses in `failure-minima.json`; `results.json` retains every measure. Broad variants are not claimed to be coordinate minima.

### Earlier scenes

All 163 earlier scenes reran: 160 pass, three fail, unchanged against the run captured at this task's start (`earlier-doubles.json`). The failures remain `min-crossing-0.04-phase{0,0.0625,0.1875}`, each with 0.02 pt of forbidden rear ink. Against the older saved `fix2.json`, `closed-box-0.59-heavy1` changed from fail to pass (longest gap 5.6 to 0 pt). Eight passing skin checks, `skins-{out,in,same,mixed}-rot{0,1}`, changed their reported length from 260.8 to 260.78 pt; `earlier-changes.json` lists every name and measure.

### Families that held

All 114 held-to-model drawings pass the 0.075 pt source-distance checks; the worst drawn vertex is 0.019 pt off a source. No case invokes `paths_to_node`, so that fallback is not exercised. All 108 smooth drawings pass, including 72 strict non-duplicate cases (worst vertex 0.009582 pt from source). Visible controls, strays above 0.2 pt, section/clip/frame-edge controls, C's inset-frame thresholds and the tested partly-near junction run hold.

Equal weights use group priority. Smooth-source checks also measure continuous off-source length and the worst drawn vertex against construction polylines, beyond the report's 0.25 pt sampling.

### Reproduce

```sh
NUMBA_CACHE_DIR="$HOME/.cache/hidden-lines/adversarial-numba" \
uv run --no-project --with numpy,shapely,numba python -B \
  tests/fixtures/hidden-lines/adversarial/run.py --jobs 4 \
  --results tests/fixtures/hidden-lines/adversarial/results.json
```

The final run exits 1: 634 drawings, 586 PASS, 48 FAIL, 0 SKIP (471 new: 426 PASS, 45 FAIL). The slowest drawing takes 13.536 s. The new cases produce 456 reports, six accepted empty-scene rejections and nine crashes. Every completed new report has off_pt=unexplained_pt=0; the four wrong-reason cases show why that is insufficient. `--keep` retains each request, export, SVG, report, checks, report assertions, A/B observations and geometric reason. Every drawing has a 60 s process-group timeout; the suite remains outside `tests/run.py`. Reductions use `minimise.py doubles-min-loop-spike-C`, and `minimise.py doubles-rims-2-C --paired` followed by `minimise.py doubles-reduced-rim-C`, under the same uv command.

`python3 kit.py test` exited 1 before hidden-line tests: `Google Chrome wrote no PNG for /var/folders/3v/2l8sgr497j924fdl7yngl44h0000gn/T/tmprb4uzxb0/gen/TEST_plan_v1.svg`. Other command failures and the distance proof are in `EXECUTION.md`. No commit was made under the worker's no-commit instruction.

---

The sections below are the earlier report, retained as the record of that run.

The suite finds lost lines around the 0.6 pt threshold, sub-pixel occluders seen through, rooms absorbed into surface cuts, blind recesses promoted to opening outlines, unreported ring/mesh disagreement, and input tracebacks.

## Drawing failures

Expected geometry is calculated before drawing: an independent camera basis and pinhole projection, explicit segment equations, and triangle intersections with the section plane. `scenes.py` supplies every construction and its reason; each run writes its request, mesh export, `checks.json` in `check_notes` format, and `expected.txt` into a temporary folder. `results.json` records every check, including its numeric measure. The additional mismatch assertion inspects the report, not the drawing oracle.

| Failure and original scenes | Small construction and measured result | Suspected pass (a guess) |
|---|---|---|
| Threshold reversal: `shell-0.59-split*`, `arches-0.61`, failing `min-pair-*` and `min-arc-*` | `min-pair-0.59-deg0-len1.9`: two segments 0.59 pt apart remain two, with the required single line at 0% of probes. `min-pair-0.61-deg15-len2.1`: two segments 0.61 pt apart become one at every probe. The arch reduces to `min-arc-1-chords`: two corresponding straight chords 0.609816 pt apart; the outer chord has a 1.4 pt gap. | `hiddenlines/hidden.py:895`, snap rounding before the doubles decision at `:2016`, with subsequent thin-face/line-end cleanup at `:2184`. |
| Occlusion: `min-crossing-0.04-phase*`, `min-crossing-0.12-phase*` | Two triangles suffice: a front sliver crosses a rear triangle's horizontal top edge. Barycentric interpolation puts the checked interval inside the front triangle. Expected rear ink is zero, with 0.002 pt allowance; measured ink is 0.02 or 0.06 pt at all four phases. The 0.24 pt versions pass. | `hiddenlines/idbuf.py:382` sampling and `:258` conditional fallback can miss the sliver. At phase 0.125, face processing splits an edge, but `hiddenlines/hidden.py:2382` reports a 0.1 pt “run on to meet”: cleanup can reopen the hidden gap. |
| Rooms: `skins-in-rot*`, `skins-same-rot*`, `min-room-fixed0` | Two nested triangular skins, one triangle per section side, plus one background triangle. The inner ring's expected gap is at most 0.15 pt; the measured gap is 183.2 pt. The rectangular same-facing versions hide 100% of a room-centred witness and retain zero inner cut-boundary ink. `cuts.unresolved` is empty. | `hiddenlines/hidden.py:436`, outward-normal votes accepting the room cell as solid. |
| Recesses: `recess-0.02`, `recess-0.2`, `min-recess-blind1` | A triangular blind recess takes thirteen triangles: six front, six reveal, one back. Its 0.02 m step requires the fine crease weight, 0.10 pt at 1:100; the rim is drawn at 0.25 pt, so coverage at the required weight is 0%. | `hiddenlines/idbuf.py:473`, planar-face opening detection, promoted to profile at `hiddenlines/hidden.py:1055` without checking whether the recess ends at a back face. |
| Cap disagreement: `cap-ring-mismatch`, `min-cap-mismatch1` | One tetrahedron, the smallest closed triangular solid, has a known triangular section; only its supplied ring is narrowed by half. Expected base coverage is at least 98%; measured coverage is 56%, at 0.80 pt. No mismatch issue is reported. | `hiddenlines/hidden.py:869` and `:1487`, supplied rings accepted without comparison to the clipped mesh. |

The recess expectation applies the sub-0.5 m step rule to a blind pocket. The rules do not explicitly say whether the opening-rim exception also includes blind pockets, so those three weight failures are conditional on that interpretation.

The reductions retain the construction's semantic primitives. Deleting either near line, removing the crossing's front triangle, removing the inner room skin, or removing the recess's back triangle gives the corresponding passing `control-*` or `min-recess-blind0` case; reversing the inner room skin gives passing `min-room-fixed1`. The tetrahedron with its correct ring passes. These are primitive-minimal witnesses, not a claim of exhaustive minimization over arbitrary coordinates. The broader angle, phase and triangulation variants remain to show each fault's extent.

## Robustness

`min-edge-on` reduces both slab crashes to one nondegenerate triangle seen edge-on. It raises `IndexError: index 0 is out of bounds for axis 0 with size 0`; deleting it gives the accepted empty-scene diagnostic. Guess: `hiddenlines/hidden.py:995` indexes an empty projected-triangle array inside `np.where`.

Zero geometry already suffices for four malformed-input failures: missing groups raises `KeyError: 'groups'`; missing frame raises `KeyError: 'frame'`; malformed scale raises `ValueError: could not convert string to float: 'wrong'`; an undersized binary raises `ValueError: buffer is smaller than requested size`. Each includes a traceback. Guesses: request access at `hiddenlines/hidden.py:519`, `:535`, `:532`, and binary decoding at `:183`, respectively.

Empty input and invalid visibility receive clear rejections. Zero-area triangles, duplicated vertices/faces, inconsistent winding, non-manifold edges, coordinates translated by 10^6 m, and simultaneous geometry/denominator scaling at 0.001, 100 and 10^9 pass, without hangs.

## Performance and execution

From the repository root:

```sh
NUMBA_CACHE_DIR="$HOME/.cache/hidden-lines/adversarial-numba" \
uv run --no-project --with numpy,shapely,numba python -B \
  tests/fixtures/hidden-lines/adversarial/run.py \
  --results tests/fixtures/hidden-lines/adversarial/results.json
```

The runner exits 1 for drawing failures; it does not join `tests/run.py`. `--only REGEXP` selects scenes; `--keep` retains all exports and checks. Every child has a 60 s process-group timeout.

| Scene | Seconds | Peak RSS (MiB) |
|---|---:|---:|
| `triangles-100000` | 3.373 | 292.7 |
| `triangles-1000000` | 5.887 | 1243.3 |
| `objects-10000` | 11.741 | 466.1 |

Times are wall time for the CLI, including dependency startup and checking, excluding scene generation; memory is peak child RSS. `/usr/bin/time -l` was attempted for every drawing but fails here with `time: sysctl kern.clockrate: Operation not permitted`; the runner records that restriction and falls back to `getrusage(RUSAGE_CHILDREN)`. These are not successful `time -l` memory readings.

The 10,000-object profile (`profile.json`, separate instrumented run) takes 12.6 s: `mesh_edges` consumes 6.23 s cumulative, including 10,000 `openings` calls at 4.09 s and welding at 0.82 s. The raster-buffer constructor takes 0.52 s; per-object edge/opening extraction dominates.

`python3 kit.py test` exits 1 before reaching hidden-line tests: `Google Chrome wrote no PNG for /var/folders/3v/2l8sgr497j924fdl7yngl44h0000gn/T/tmpdjmvb334/gen/TEST_plan_v1.svg`. The standalone suite completes with 121 passing scenes, 42 failing scenes (including three interpretation-dependent recess cases), and no timeouts.

## Families that held

Both triangulations of plates converging at 0.5°, 1°, 2°, 5° and 10° pass, including translated, shifted-phase and perspective variants. Books, fin caps, the tested closed rectangles beside another line, and all notch checks pass. Correctly oriented surface walls, the cavity, foundation union and open ground above a basement pass. Vertical sub-pixel occlusion witnesses, grazing faces, coincident faces, host offsets, and door/window rims in four directions with parallel and perspective projection pass. Passing probes do not establish visibility between all samples.
