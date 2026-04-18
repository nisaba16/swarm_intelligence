# Collective motion — active inference experiments

All ARGoS/Buzz files live in `Argos_files/`. **Always run from there** so relative paths resolve:

```bash
cd Argos_files
mkdir -p logs results
```

---

## Workflow for one experiment

1. Create `logs/` inside `Argos_files/` if it does not exist
2. Run ARGoS from `Argos_files/` — position logs are written to `Argos_files/logs/`
3. Move logs to a named folder: `mv logs logs_milling` (or copy)
4. Run `plot_trajectories.py` pointing at that folder

```
project/
├── Argos_files/
│     ├── actinf.argos
│     ├── actinf.bzz
│     ├── actinf_common.bzz
│     ├── actinf_dissident.argos
│     ├── actinf_dissident.bzz
│     ├── collective_common.bzz
│     └── logs/               ← ARGoS writes here
├── logs/
│     ├── logs_milling/
│     ├── logs_polar/
│     └── logs_dissident_XX/
├── results/
├── plot_trajectories.py
└── README.md
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
| `0` | Polarized |
| `1` | Milling |
| `2` | Disordered |

**Implementation note:** `ai_vel` and `dFdv` are computed in the **global frame** to match
the Julia reference implementation. Body-frame RAB azimuths are rotated by `+yaw` before
accumulating the gradient. Steering angle = `desired_global_heading − current_yaw`.

**Physical note:** the paper uses point particles. The Khepera IV has a 14 cm body, so
`ETA` (preferred neighbour distance) must be > 2 × 0.14 m = 0.28 m. Currently `ETA = 0.5 m`.

**Tuning guide** (phase diagram Fig 2B of Heins et al. 2023):

| Parameter | More polarized | More milling |
|---|---|---|
| `SIGMA_Z` (= 1/Γ_z) | decrease | increase |
| `S_Z` (= λ_z) | decrease | increase |
| `ALPHA` | decrease | increase |
| `KA` | decrease | increase |

### 3. Active inference — dissident conflict

`actinf_dissident.bzz` — three roles, assigned deterministically by robot ID:

| Role | IDs | Goal |
|---|---|---|
| Dissident | `0 .. dissident_count` | Target B: top-left (135°) |
| Leader | `dissident_count .. informed_count` | Target A: bottom-right (−45°) |
| Uninformed | rest | Social term only (no goal) |

Key parameters in `actinf_dissident.bzz`:

```
N_ROBOTS       = 30
INFORMED_FRAC  = 0.5   # fraction of robots that are informed (leaders + dissidents)
DISSIDENT_FRAC = 0.33  # fraction of *informed* robots that are dissidents
GOAL_WEIGHT    = 0.25  # weight of goal vector relative to social term
```

To sweep dissident proportion while keeping informed count fixed, vary only `DISSIDENT_FRAC`:
`0.0` (all leaders), `0.33`, `0.5`, `0.67`, `1.0` (all dissidents).

---

## Compile & run

### Active inference (base)

```bash
# Edit PRESET in actinf.bzz first (0 = polarized, 1 = milling, 2 = disordered)
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

## Log format

Each robot writes one CSV file: `logs/pos_<id>.csv`

```
step,id,role,x,y,yaw
```

| Column | Type | Description |
|---|---|---|
| `step` | int | Simulation tick (logged every `LOG_EVERY` ticks, default 5) |
| `id` | int | Robot ID (0-based) |
| `role` | int | `0` = uninformed, `1` = leader, `2` = dissident |
| `x`, `y` | float | Position in metres (global frame, arena centred at 0,0) |
| `yaw` | float | Heading in radians (global frame, 0 = +x axis) |

Old logs without the `role` column are still accepted (role defaults to 0).

---

## Plots & videos

`plot_trajectories.py` lives one level up. Run from `Argos_files/` or pass full paths.

### Animation

```bash
python3 ../plot_trajectories.py --logdir logs --mode anim \
  --tail 0 --stride 2 --fps 30 \
  --figsize 6 --dpi 150 \
  --out results/video.mp4
```

### Heatmap

```bash
python3 ../plot_trajectories.py --logdir logs --mode heatmap \
  --tail 600 --bins 300 --dpi 400 --figsize 9 \
  --title "Milling | α=1.2 N=30" \
  --out results/heatmap.png
```

Add `--no-white-bg` to switch to the dark (inferno) colormap.
Use `--start-step` / `--end-step` to restrict to a time window.

### Dissident animation (with goal arrows)

```bash
python3 ../plot_trajectories.py --logdir logs --mode anim \
  --tail 0 --stride 2 --fps 30 \
  --figsize 6 --dpi 150 \
  --goal-heading -0.785 --diss-goal-heading 2.356 \
  --out results/video_dissident.mp4
```

Colours: uninformed = gray, leaders = blue, dissidents = red.
Arrows show each group's goal direction from the arena centre.

### Order-parameter metrics

```bash
python3 ../plot_trajectories.py --logdir logs --mode metrics \
  --tail 0 --dpi 220 \
  --out results/metrics.png \
  --csv results/metrics.csv
```

CSV columns: `step, polarization, milling, n_agents_used`.
