#!/usr/bin/env python3
"""Quick visualization for ARGoS/Buzz position logs.

Expected log format (one file per robot):
  step,id,x,y,yaw

Examples:
  # Make sure logs exist (Buzz won't create the folder)
  #   mkdir -p logs
  # then run argos3, then:

  python3 plot_trajectories.py --logdir logs --mode heatmap --tail 400 --out heatmap.png
  python3 plot_trajectories.py --logdir logs --mode final --out final_positions.png
  python3 plot_trajectories.py --logdir logs --mode anim --tail 300 --stride 2 --fps 30 --out traj.mp4

Notes:
  - Default arena extent is [-5,5]x[-5,5] (10x10 arena centered at 0).
  - If you changed the arena size, pass --arena-size 10 or --extent.
"""

from __future__ import annotations

import argparse
import csv
import glob
import itertools
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np


def _parse_extent(
    extent_args: List[float] | None,
    arena_size: float,
    center_radius: float | None,
) -> Tuple[float, float, float, float]:
    # Explicit extent has highest priority
    if extent_args is not None and len(extent_args) == 4:
        xmin, xmax, ymin, ymax = map(float, extent_args)
        return xmin, xmax, ymin, ymax
    # Zoom around arena center (0,0)
    if center_radius is not None:
        r = float(center_radius)
        return -r, r, -r, r
    # Default full arena
    half = float(arena_size) / 2.0
    return -half, half, -half, half


@dataclass
class LogPoint:
    step: int
    rid: int
    x: float
    y: float
    yaw: float


def read_logs(logdir: str) -> List[LogPoint]:
    patterns = [os.path.join(logdir, "pos_*.csv"), os.path.join(logdir, "*.csv")]
    files: List[str] = []
    for pat in patterns:
        files.extend(glob.glob(pat))

    # Filter non-files and keep stable order
    files = sorted([f for f in files if os.path.isfile(f)])
    if not files:
        raise FileNotFoundError(
            f"No CSV logs found in '{logdir}'. Expected files like pos_0.csv. "
            f"(Also ensure the directory exists before running ARGoS: mkdir -p {logdir})"
        )

    points: List[LogPoint] = []
    for fp in files:
        with open(fp, "r", newline="") as f:
            reader = csv.reader(f)
            first = next(reader, None)
            if first is None:
                continue
            # Accept both with/without header
            if "step" in ",".join(first).lower():
                rows = reader
            else:
                rows = itertools.chain([first], reader)
            for row in rows:
                if not row:
                    continue
                try:
                    step = int(float(row[0]))
                    rid = int(float(row[1]))
                    x = float(row[2])
                    y = float(row[3])
                    yaw = float(row[4]) if len(row) > 4 else 0.0
                except (ValueError, IndexError):
                    continue
                points.append(LogPoint(step=step, rid=rid, x=x, y=y, yaw=yaw))

    if not points:
        raise ValueError(f"Found CSV files in '{logdir}' but could not parse any rows")
    return points


def select_window(
    points: List[LogPoint],
    start_step: int | None,
    end_step: int | None,
) -> List[LogPoint]:
    if start_step is None and end_step is None:
        return points

    lo = start_step
    hi = end_step
    if lo is None:
        lo = min(p.step for p in points)
    if hi is None:
        hi = max(p.step for p in points)
    if hi < lo:
        raise ValueError(f"Invalid window: end-step ({hi}) < start-step ({lo})")

    return [p for p in points if (p.step >= lo and p.step <= hi)]


def select_tail(points: List[LogPoint], tail: int | None) -> List[LogPoint]:
    if not tail or tail <= 0:
        return points
    max_step = max(p.step for p in points)
    min_step = max_step - tail
    return [p for p in points if p.step >= min_step]


def last_positions(points: List[LogPoint]) -> List[LogPoint]:
    last: Dict[int, LogPoint] = {}
    for p in points:
        cur = last.get(p.rid)
        if cur is None or p.step > cur.step:
            last[p.rid] = p
    return list(last.values())


def plot_heatmap(
    points: List[LogPoint],
    extent: Tuple[float, float, float, float],
    bins: int,
    out: str,
    title: str,
    dpi: int,
    figsize: float,
) -> None:
    import matplotlib.pyplot as plt

    xs = np.array([p.x for p in points], dtype=float)
    ys = np.array([p.y for p in points], dtype=float)
    xmin, xmax, ymin, ymax = extent

    H, xedges, yedges = np.histogram2d(xs, ys, bins=bins, range=[[xmin, xmax], [ymin, ymax]])
    H = H.T  # for imshow

    fig, ax = plt.subplots(figsize=(figsize, figsize), dpi=dpi)
    im = ax.imshow(
        H,
        origin="lower",
        extent=[xmin, xmax, ymin, ymax],
        cmap="inferno",
        interpolation="nearest",
        aspect="equal",
    )
    ax.set_title(title)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="visits")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def plot_final(
    points: List[LogPoint],
    extent: Tuple[float, float, float, float],
    out: str,
    title: str,
    dpi: int,
    figsize: float,
) -> None:
    import matplotlib.pyplot as plt

    pts = last_positions(points)
    xs = np.array([p.x for p in pts], dtype=float)
    ys = np.array([p.y for p in pts], dtype=float)

    xmin, xmax, ymin, ymax = extent
    fig, ax = plt.subplots(figsize=(figsize, figsize), dpi=dpi)
    ax.scatter(xs, ys, s=12, alpha=0.9)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(title)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def animate(
    points: List[LogPoint],
    extent: Tuple[float, float, float, float],
    out: str,
    fps: int,
    stride: int,
    dpi: int,
    figsize: float,
) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation

    # Group by step
    by_step: Dict[int, List[LogPoint]] = {}
    for p in points:
        by_step.setdefault(p.step, []).append(p)
    steps = sorted(by_step.keys())
    if stride and stride > 1:
        steps = steps[::stride]

    # Fix robot ordering for stable colors
    rids = sorted({p.rid for p in points})
    rid_to_idx = {rid: i for i, rid in enumerate(rids)}

    xmin, xmax, ymin, ymax = extent
    fig, ax = plt.subplots(figsize=(figsize, figsize), dpi=dpi)
    scat = ax.scatter([], [], s=10)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")

    def init():
        scat.set_offsets(np.zeros((0, 2)))
        return (scat,)

    def update(i: int):
        step = steps[i]
        frame_pts = by_step.get(step, [])
        # allocate arrays in robot order, only for robots present
        xs = np.array([p.x for p in frame_pts], dtype=float)
        ys = np.array([p.y for p in frame_pts], dtype=float)
        scat.set_offsets(np.c_[xs, ys])
        ax.set_title(f"step={step}  (frame {i+1}/{len(steps)})")
        return (scat,)

    anim = FuncAnimation(fig, update, frames=len(steps), init_func=init, interval=1000 / max(fps, 1), blit=True)

    # Writer depends on your system (ffmpeg for mp4, pillow for gif)
    ext = os.path.splitext(out)[1].lower()
    if ext == ".gif":
        anim.save(out, writer="pillow", fps=fps)
    else:
        anim.save(out, writer="ffmpeg", fps=fps)
    plt.close(fig)


def _group_positions_by_step(points: List[LogPoint]) -> Tuple[List[int], Dict[int, Dict[int, Tuple[float, float, float]]]]:
    """Return (sorted_steps, step->rid->(x,y,yaw))."""
    by_step: Dict[int, Dict[int, Tuple[float, float, float]]] = {}
    for p in points:
        by_step.setdefault(p.step, {})[p.rid] = (p.x, p.y, p.yaw)
    steps = sorted(by_step.keys())
    return steps, by_step


def compute_order_parameters(points: List[LogPoint]) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Compute order parameters from logs.

    Returns arrays (steps, polarization, milling, n_agents_used).

    Definitions (both in [0,1]):
      polarization(t) = ||mean_i vhat_i||
      milling(t)      = |mean_i cross(rhat_i, vhat_i)|

    where rhat_i is position relative to centroid (unit), vhat_i is finite-difference velocity direction (unit).
    """
    steps, by_step = _group_positions_by_step(points)

    prev_pos: Dict[int, Tuple[float, float, int]] = {}  # rid -> (x,y,step)

    pol_list: List[float] = []
    mil_list: List[float] = []
    n_list: List[int] = []
    steps_out: List[int] = []

    for step in steps:
        rids = sorted(by_step[step].keys())
        if not rids:
            continue

        # positions for centroid
        pos = np.array([[by_step[step][rid][0], by_step[step][rid][1]] for rid in rids], dtype=float)
        c = pos.mean(axis=0)

        vhat_rows = []
        rhat_rows = []

        for i, rid in enumerate(rids):
            x, y, _yaw = by_step[step][rid]
            prev = prev_pos.get(rid)
            prev_pos[rid] = (x, y, step)
            if prev is None:
                continue

            x0, y0, step0 = prev
            dx = x - x0
            dy = y - y0
            sp = float(np.hypot(dx, dy))
            if sp <= 1e-9:
                continue

            vhat = np.array([dx, dy], dtype=float) / sp
            r = np.array([x, y], dtype=float) - c
            rn = float(np.hypot(r[0], r[1]))
            if rn <= 1e-9:
                continue
            rhat = r / rn

            vhat_rows.append(vhat)
            rhat_rows.append(rhat)

        n_used = len(vhat_rows)
        if n_used < 3:
            continue

        V = np.stack(vhat_rows, axis=0)
        R = np.stack(rhat_rows, axis=0)

        pol = float(np.linalg.norm(V.mean(axis=0)))
        cross_z = R[:, 0] * V[:, 1] - R[:, 1] * V[:, 0]
        mil = float(np.abs(cross_z.mean()))

        steps_out.append(step)
        pol_list.append(pol)
        mil_list.append(mil)
        n_list.append(n_used)

    return (
        np.array(steps_out, dtype=int),
        np.array(pol_list, dtype=float),
        np.array(mil_list, dtype=float),
        np.array(n_list, dtype=int),
    )


def write_metrics_csv(path: str, steps: np.ndarray, pol: np.ndarray, mil: np.ndarray, n_used: np.ndarray) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["step", "polarization", "milling", "n_agents_used"])
        for s, p, m, n in zip(steps, pol, mil, n_used):
            w.writerow([int(s), float(p), float(m), int(n)])


def plot_metrics(out_png: str, steps: np.ndarray, pol: np.ndarray, mil: np.ndarray, n_used: np.ndarray, title: str, dpi: int) -> None:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=dpi)
    ax.plot(steps, pol, label="polarization (0..1)", lw=2)
    ax.plot(steps, mil, label="milling (0..1)", lw=2)
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel("step")
    ax.set_ylabel("order parameter")
    ax.grid(True, alpha=0.25)
    ax2 = ax.twinx()
    ax2.plot(steps, n_used, label="agents used", color="black", alpha=0.25, lw=1)
    ax2.set_ylabel("agents used")
    ax.set_title(title)
    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines + lines2, labels + labels2, loc="upper right")
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--logdir", default="logs", help="Directory with pos_*.csv")
    ap.add_argument("--mode", choices=["heatmap", "final", "anim", "metrics"], default="heatmap")
    ap.add_argument("--out", default=None, help="Output file (png/gif/mp4)")
    ap.add_argument("--csv", default=None, help="Optional CSV output (used by --mode metrics)")
    ap.add_argument("--start-step", type=int, default=None, help="First step to include (inclusive)")
    ap.add_argument("--end-step", type=int, default=None, help="Last step to include (inclusive)")
    ap.add_argument("--tail", type=int, default=400, help="Keep only last N steps (0 = all)")
    ap.add_argument("--bins", type=int, default=80, help="Heatmap bins per axis")
    ap.add_argument("--dpi", type=int, default=220, help="Figure DPI (higher = more pixels)")
    ap.add_argument("--figsize", type=float, default=6.0, help="Figure size in inches")
    ap.add_argument("--arena-size", type=float, default=10.0, help="Arena side length (meters)")
    ap.add_argument("--extent", type=float, nargs=4, default=None, metavar=("XMIN", "XMAX", "YMIN", "YMAX"))
    ap.add_argument(
        "--center-radius",
        type=float,
        default=None,
        help="If set, zoom around (0,0): extent [-r,r]x[-r,r]",
    )
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--stride", type=int, default=2, help="Use every Nth logged step in animation")
    args = ap.parse_args()

    extent = _parse_extent(args.extent, args.arena_size, args.center_radius)
    points = read_logs(args.logdir)
    points = select_window(points, args.start_step, args.end_step)
    if not points:
        raise SystemExit("No points left after applying --start-step/--end-step window")
    points = select_tail(points, args.tail)

    out = args.out
    if out is None:
        out = {
            "heatmap": "heatmap.png",
            "final": "final_positions.png",
            "anim": "traj.mp4",
            "metrics": "metrics.png",
        }[args.mode]

    window_str = ""
    if args.start_step is not None or args.end_step is not None:
        window_str = f" window=[{args.start_step},{args.end_step}]"

    title = f"{args.mode} from {os.path.basename(os.path.abspath(args.logdir))} (tail={args.tail}){window_str}"

    try:
        if args.mode == "heatmap":
            plot_heatmap(points, extent=extent, bins=args.bins, out=out, title=title, dpi=args.dpi, figsize=args.figsize)
        elif args.mode == "final":
            plot_final(points, extent=extent, out=out, title=title, dpi=args.dpi, figsize=args.figsize)
        elif args.mode == "anim":
            animate(points, extent=extent, out=out, fps=args.fps, stride=args.stride, dpi=args.dpi, figsize=args.figsize)
        else:
            steps, pol, mil, n_used = compute_order_parameters(points)
            if steps.size == 0:
                raise RuntimeError("Not enough data to compute metrics (need >=2 samples per robot and >=3 robots)")
            csv_out = args.csv or os.path.splitext(out)[0] + ".csv"
            write_metrics_csv(csv_out, steps, pol, mil, n_used)
            plot_metrics(out, steps, pol, mil, n_used, title=title, dpi=args.dpi)
            print(csv_out)
    except Exception as e:
        raise SystemExit(f"Failed to generate plot: {e}")

    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
