# Collective motion — active inference experiments

All ARGoS/Buzz files live in `Argos_files/`. **Always run from there** so relative paths resolve:

```bash
cd Argos_files
mkdir -p logs results
```

---

## Experiments

### 1. Baseline (rule-based, Lennard-Jones)

| File | Behaviour |
|---|---|
| `collective_polarized` | Polarized flocking |
| `collective_milling`   | Milling |
| `collective_conflict`  | Leaders vs dissidents |

Shared logic: `collective_common.bzz`.

### 2. Active inference — base model (Heins et al. 2023)

Single controller `actinf.bzz`, switch behaviour by changing `PRESET`:

| PRESET | Behaviour |
|---|---|
| `0` | Polarized-like (low α, low turning) |
| `1` | Milling-like (high α, high turning) |

Key parameters: `SIGMA_Z`, `SIGMA_W`, `S_Z`, `S_W`, `ALPHA`, `KMU`, `KA`, `SPEED`, `MAX_TURN`.

### 3. Active inference — dissident conflict

`actinf_dissident.bzz` — same active inference equations as above, but two subgroups have
opposing goal priors:

- **Majority** (70 %): bottom-right (−45°)
- **Dissidents** (30 %): top-left (135°)

Key parameters: `DISSIDENT_FRAC`, `GOAL_WEIGHT`, `DISS_GOAL_WEIGHT`.

> **Which base regime to use for the dissident experiment?**
> Use the **polarized setting** (PRESET=0 parameters, which is the default in
> `actinf_dissident.bzz`). The conflict between goal directions is most visible
> when the base behaviour has directed motion. Milling adds a circular attractor
> on top of the goal conflict, making results harder to interpret.

---

## Compile & run

### Active inference (base)

```bash
# Edit PRESET in actinf.bzz first (0 = polarized, 1 = milling)
bzzc -I . -b actinf.bo -d actinf.bdb actinf.bzz
argos3 -c actinf.argos          # with GUI
argos3 -z -c actinf.argos       # headless (faster)
```

### Active inference (dissident)

```bash
bzzc -I . -b actinf_dissident.bo -d actinf_dissident.bdb actinf_dissident.bzz
argos3 -c actinf_dissident.argos
```

### Baselines

```bash
bzzc -I . -b collective_polarized.bo -d collective_polarized.bdb collective_polarized.bzz
argos3 -c collective_polarized.argos
```

---

## Plots & videos

The script `plot_trajectories.py` lives one level up (`../plot_trajectories.py`).
Run from `Argos_files/` so log paths resolve correctly.

### Heatmap (white background, specific step range)

```bash
# Milling — steps 200–800
python3 ../plot_trajectories.py --logdir logs_logs --mode heatmap \
  --start-step 200 --end-step 800 \
  --center-radius 3 --bins 300 --dpi 400 --figsize 9 \
  --out results/heatmap_milling.png

# Polarized — last 600 steps
python3 ../plot_trajectories.py --logdir logs --mode heatmap \
  --tail 600 \
  --center-radius 3 --bins 300 --dpi 400 --figsize 9 \
  --out results/heatmap_polarized.png
```

Add `--no-white-bg` to switch back to the dark (inferno) colormap.

Use `--title` to label the plot with the parameters you used:

```bash
python3 plot_trajectories.py --logdir logs/logs_milling --mode heatmap \
  --tail 600 --center-radius 3 --bins 300 --dpi 400 --figsize 9 \
  --title "Milling settings  | α=1.2  N=30" \
  --out results/heatmap_milling.png
```

```bash
python3 plot_trajectories.py --logdir logs/logs_polar --mode heatmap \
  --tail 600 --center-radius 3 --bins 300 --dpi 400 --figsize 9 \
  --title "Polarized settings  | α=0.25  N=30" \
  --out results/heatmap_polar.png
```


### Videos — milling vs polarized

Run ARGoS twice (once with `PRESET=1`, once with `PRESET=0`), saving logs to
separate folders, then:

```bash
# Milling video
python3 plot_trajectories.py --logdir logs/logs_milling --mode anim \
  --tail 0 --stride 2 --fps 30 \
  --center-radius 4 --figsize 6 --dpi 150 \
  --out results/video_milling.mp4

# Polarized video
python3 plot_trajectories.py --logdir logs/logs_polar --mode anim \
  --tail 0 --stride 2 --fps 30 \
  --center-radius 4 --figsize 6 --dpi 150 \
  --out results/video_polarized.mp4


```

### Videos — dissident conflict (with goal arrows)

The `--goal-heading` and `--diss-goal-heading` flags draw arrows from the
arena centre showing each group's objective.  Majority = blue, dissidents = red.

```bash
python3 plot_trajectories.py --logdir logs/logs_dissident_00 --mode anim \
  --tail 0 --stride 2 --fps 30 \
  --center-radius 4 --figsize 6 --dpi 150 \
  --goal-heading -0.785 --diss-goal-heading 2.356 \
  --out results/video_dissident_05.mp4
```

To compare across different dissident fractions, run ARGoS three times
(`DISSIDENT_FRAC` = 0.1, 0.3, 0.5) into separate log folders, then generate
one video per folder with the same command above.

### Order-parameter metrics (polarization & milling score over time)

```bash
python3 ../plot_trajectories.py --logdir logs --mode metrics \
  --tail 0 --dpi 220 \
  --out results/metrics.png \
  --csv results/metrics.csv
```

The CSV has columns `step, polarization, milling, n_agents_used` and can be
opened directly in Excel or LibreOffice.

---

## Log format

Each robot writes `logs/pos_<id>.csv`:

```
step,id,role,x,y,yaw
```

`role`: `0` = majority, `1` = dissident.  Old logs without the `role` column
are still accepted (role defaults to 0).
