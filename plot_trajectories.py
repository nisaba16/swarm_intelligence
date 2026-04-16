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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--logdir", default="logs", help="Directory with pos_*.csv")
    ap.add_argument("--mode", choices=["heatmap", "final", "anim"], default="heatmap")
    ap.add_argument("--out", default=None, help="Output file (png/gif/mp4)")
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
    points = select_tail(points, args.tail)

    out = args.out
    if out is None:
        out = {
            "heatmap": "heatmap.png",
            "final": "final_positions.png",
            "anim": "traj.mp4",
        }[args.mode]

    title = f"{args.mode} from {os.path.basename(os.path.abspath(args.logdir))} (tail={args.tail})"

    try:
        if args.mode == "heatmap":
            plot_heatmap(points, extent=extent, bins=args.bins, out=out, title=title, dpi=args.dpi, figsize=args.figsize)
        elif args.mode == "final":
            plot_final(points, extent=extent, out=out, title=title, dpi=args.dpi, figsize=args.figsize)
        else:
            animate(points, extent=extent, out=out, fps=args.fps, stride=args.stride, dpi=args.dpi, figsize=args.figsize)
    except Exception as e:
        raise SystemExit(f"Failed to generate plot: {e}")

    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
