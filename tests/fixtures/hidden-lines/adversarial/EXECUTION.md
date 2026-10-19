# regression execution

All commands ran at the worktree root, with `NUMBA_CACHE_DIR` set to `$HOME/.cache/hidden-lines/adversarial-numba`. Python scripts used `uv run --no-project --with numpy,shapely,numba python -B`; drawings ran through `python3 kit.py hidden-lines REQUEST --check CHECKS`, which supplies the kit's remaining dependencies.

| Check | Result |
|---|---|
| Original `run.py --results …/earlier-doubles.json`, before extending the generator | Exit 1: 160 PASS, 3 FAIL, 0 SKIP, all 163 scenes completed. |
| Final `run.py --jobs 4 --results …/results.json` | Exit 1: 586 PASS, 48 FAIL, 0 SKIP; all 634 drawings completed. New cases: 426 PASS, 45 FAIL across 471 drawings. Slowest: 13.536 s. |
| `minimise.py doubles-min-loop-spike-C` | Completed; eight drawings. Every admissible single-vertex deletion from the retained four/seven-vertex loops passes. |
| `minimise.py doubles-rims-2-C --paired` | Completed; 63 drawings, reducing 128 chords per rim to five per rim. |
| `minimise.py doubles-reduced-rim-C` | Completed; ten drawings, reducing the pair to three/four vertices. Remaining vertex deletions unclose or intersect the loops. |
| Independent segment-distance calculation | Maximum lesser-to-heavier distance 0.4284645669291365 pt for the reduced excursion; 0.11818031822256468 pt for the reduced rim. Source lengths 60.94172618366694 and 47.343892731469744 pt. No kit output used. |
| AST parsing `doubles.py`, `minimise.py`, `run.py`, `scenes.py` | Passed. |
| `git diff --check` | Exit 0. |
| `python3 kit.py test` | Exit 1 before hidden-line tests, with the error below. |

The independent distance calculation divides a source segment at every target-foot projection crossing an endpoint. Squared distances to the target's segments are quadratic on each interval; checking interval boundaries and pairwise quadratic intersections gives the exact maximum of their lower envelope, up to floating-point arithmetic.

The main test command failed with:

```text
Google Chrome wrote no PNG for /var/folders/3v/2l8sgr497j924fdl7yngl44h0000gn/T/tmprb4uzxb0/gen/TEST_plan_v1.svg
```

Exploratory command failures, not passing checks:

- A direct `archkit.hidden.build` probe in the three-package environment exited 1: `ModuleNotFoundError: No module named 'scipy'`. All recorded CLI drawings use the kit's dependency bootstrap instead.
- A read-only lookup for `archkit/cli.py` failed: `rg: archkit/cli.py: IO error for operation on archkit/cli.py: No such file or directory (os error 2)`; the dispatcher is in `kit.py`.
- A read-only lookup for `archkit/commands.py` failed: `rg: archkit/commands.py: IO error for operation on archkit/commands.py: No such file or directory (os error 2)`.
- Process inspection failed: `zsh:1: operation not permitted: ps`.
- `/usr/bin/time -l` cannot read `sysctl kern.clockrate` in this sandbox. The existing runner records that error and uses its child-resource fallback; its fallback, not `time -l`, supplies recorded memory.

Exploratory runs were interrupted while reducing scenes or correcting oracles; they are not counted as the final matrix. Pilot files and retained pilot exports were removed. `reduction-*.json` and the paired/single reduction logs retain the minimization evidence. No engine changes, commits, pushes or git-setting changes were made.
