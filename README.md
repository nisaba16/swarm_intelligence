# Collective motion experiments

This folder contains Buzz and ARGoS setups for the collective motion project.

## Available experiments
- `collective_polarized`: baseline polarized flocking
- `collective_milling`: baseline milling behavior
- `collective_conflict`: leaders and dissidents with opposing goals

## Run
1. Compile the Buzz controller:
   - `bzzc <file>.bzz -b <file>.bo -d <file>.bdb`
2. Launch the matching ARGoS scenario:
   - `collective_polarized.argos`
   - `collective_milling.argos`
   - `collective_conflict.argos`

## Notes
- `collective_common.bzz` contains the shared controller logic.
- The role proportions and motion weights are set in each wrapper script.
- `barrier.bzz` and `shapeform.bzz` are kept as earlier reference experiments.


Plot trajectories

```
python3 plot_trajectories.py --logdir logs_milling --mode heatmap --tail 600 \
  --center-radius 3 --bins 300 --dpi 400 --figsize 9 --out results/heatmap_zoom_hi_milling.png

python3 plot_trajectories.py --logdir logs_polar --mode heatmap --tail 600 \
  --center-radius 3 --bins 300 --dpi 400 --figsize 9 --out results/heatmap_zoom_hi_polarize.png
```

```
python3 plot_trajectories.py --logdir logs_millin --mode anim --tail 1000 --stride 2 --fps 20 --out results/traj_slow_polarized.mp4

python3 plot_trajectories.py --logdir logs_polar --mode anim --tail 1000 --stride 2 --fps 20 --out results/traj_slow_polarized.mp4
```