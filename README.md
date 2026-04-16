# Collective motion experiments

This folder contains Buzz and ARGoS setups for the collective motion project.

## Available experiments

### Baselines (rule-based)
- `collective_polarized`: baseline polarized flocking
- `collective_milling`: baseline milling behavior
- `collective_conflict`: leaders and dissidents with opposing goals

Shared logic: `collective_common.bzz`.

### Active inference (single controller, switch by parameters)
- `actinf.argos`: unified ARGoS scenario
- `actinf.bzz`: single entry point with a `PRESET` selector
- `actinf_common.bzz`: predictive-coding update (generalised coordinates) + optional CSV logging

`PRESET` values in `actinf.bzz`:
- `0`: polarized-like
- `1`: milling-like

Key parameters in `actinf.bzz`:
- `R0`: interaction range in meters (must match `rab_range` in `actinf.argos`)
- `ETA`: preferred neighbor distance
- `SPEED`, `KA`, `KMU`: motion / action / belief gains
- `MAX_TURN`: clamps turning (prevents in-place spinning)
- Logging: `LOG_POSITIONS`, `LOG_EVERY`, `LOG_DIR`

When logging is enabled, each robot writes a CSV:
- `LOG_DIR/pos_<id>.csv`
- columns: `step,id,x,y,yaw`

## Run

All the ARGoS/Buzz experiment files live in Argos_files. Run from there so relative paths work:

```bash
cd Argos_files
```

### Active inference
Compile:
```bash
bzzc -I . -b actinf.bo -d actinf.bdb actinf.bzz
```

Run with GUI:
```bash
argos3 -c actinf.argos
```

Run faster (no GUI):
```bash
argos3 -z -c actinf.argos
```

If logging is enabled, create the output directory first:
```bash
mkdir -p logs
```

### Baselines
Compile + run the matching pair (example):
```bash
bzzc -I . -b collective_polarized.bo -d collective_polarized.bdb collective_polarized.bzz
argos3 -c collective_polarized.argos
```

## Plot trajectories / short animations from logs

A helper script is provided in Argos_files:
- `plot_trajectories.py`

Examples (run from Argos_files):

Create an output folder:
```bash
mkdir -p results
```

Zoomed-in, high-resolution heatmap around the arena center:
```bash
python3 plot_trajectories.py --logdir logs_milling --mode heatmap --tail 600 \
  --center-radius 3 --bins 300 --dpi 400 --figsize 9 --out results/heatmap_milling.png
```

Final positions only:
```bash
python3 plot_trajectories.py --logdir logs_milling --mode final \
  --center-radius 3 --dpi 300 --figsize 7 --out results/final_milling.png
```

Short animation of the last part of the run:
```bash
python3 plot_trajectories.py --logdir logs_milling --mode anim --tail 300 --stride 2 --fps 30 \
  --center-radius 3 --out results/traj_milling.mp4
```

Notes:
- Use `--tail` to keep the plot/animation short and readable.
- Use a larger `--bins` and higher `--dpi` for sharper heatmaps.
- If you change `LOG_DIR` in `actinf.bzz`, pass that directory name to `--logdir`.
