#!/usr/bin/env python3
"""Quick visualization for ARGoS/Buzz position logs.

Expected log format (one file per robot):
  step,id,role,x,y,yaw        (new format — role 0=majority 1=dissident)
  step,id,x,y,yaw             (old format — role defaults to 0)

Examples:
  python3 plot_trajectories.py --logdir logs --mode heatmap --tail 400 --out heatmap.png
  python3 plot_trajectories.py --logdir logs --mode anim --tail 300 --stride 2 --fps 30 --out traj.mp4
  python3 plot_trajectories.py --logdir logs --mode anim --tail 300 \
      --goal-heading -0.785 --diss-goal-heading 2.356 --out dissident.mp4
"""

from __future__ import annotations

import argparse
import csv
import glob
import itertools
import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


def _parse_extent(
    extent_args: Optional[List[float]],
    arena_size: float,
    center_radius: Optional[float],
) -> Tuple[float, float, float, float]:
    if extent_args is not None and len(extent_args) == 4:
        xmin, xmax, ymin, ymax = map(float, extent_args)
        return xmin, xmax, ymin, ymax
    if center_radius is not None:
        r = float(center_radius)
        return -r, r, -r, r
    half = float(arena_size) / 2.0
    return -half, half, -half, half


@dataclass
class LogPoint:
    step: int
    rid: int
    role: int   # 0 = uninformed, 1 = leader, 2 = dissident
    x: float
    y: float
    yaw: float


def read_logs(logdir: str) -> List[LogPoint]:
    patterns = [os.path.join(logdir, "pos_*.csv"), os.path.join(logdir, "*.csv")]
    files: List[str] = []
    for pat in patterns:
        files.extend(glob.glob(pat))
    files = sorted([f for f in files if os.path.isfile(f)])
    if not files:
        raise FileNotFoundError(
            f"No CSV logs found in '{logdir}'. Expected files like pos_0.csv. "
            f"(mkdir -p {logdir} before running ARGoS)"
        )

    points: List[LogPoint] = []
    for fp in files:
        with open(fp, "r", newline="") as f:
            reader = csv.reader(f)
            first = next(reader, None)
            if first is None:
                continue
            if "step" in ",".join(first).lower():
                rows = reader
                has_role = "role" in ",".join(first).lower()
            else:
                rows = itertools.chain([first], reader)
                has_role = len(first) >= 6
            for row in rows:
                if not row:
                    continue
                try:
                    if has_role:
                        # step,id,role,x,y,yaw
                        step = int(float(row[0]))
                        rid  = int(float(row[1]))
                        role = int(float(row[2]))
                        x    = float(row[3])
                        y    = float(row[4])
                        yaw  = float(row[5]) if len(row) > 5 else 0.0
                    else:
                        # step,id,x,y,yaw
                        step = int(float(row[0]))
                        rid  = int(float(row[1]))
                        role = 0
                        x    = float(row[2])
                        y    = float(row[3])
                        yaw  = float(row[4]) if len(row) > 4 else 0.0
                except (ValueError, IndexError):
                    continue
                points.append(LogPoint(step=step, rid=rid, role=role, x=x, y=y, yaw=yaw))

    if not points:
        raise ValueError(f"Found CSV files in '{logdir}' but could not parse any rows")
    return points


def select_window(
    points: List[LogPoint],
    start_step: Optional[int],
    end_step: Optional[int],
) -> List[LogPoint]:
    if start_step is None and end_step is None:
        return points
    lo = start_step if start_step is not None else min(p.step for p in points)
    hi = end_step   if end_step   is not None else max(p.step for p in points)
    if hi < lo:
        raise ValueError(f"Invalid window: end-step ({hi}) < start-step ({lo})")
    return [p for p in points if lo <= p.step <= hi]


def select_tail(points: List[LogPoint], tail: Optional[int]) -> List[LogPoint]:
    if not tail or tail <= 0:
        return points
    max_step = max(p.step for p in points)
    return [p for p in points if p.step >= max_step - tail]


def last_positions(points: List[LogPoint]) -> List[LogPoint]:
    last: Dict[int, LogPoint] = {}
    for p in points:
        cur = last.get(p.rid)
        if cur is None or p.step > cur.step:
            last[p.rid] = p
    return list(last.values())


# ---------------------------------------------------------------------------
# Heatmap
# ---------------------------------------------------------------------------

def plot_heatmap(
    points: List[LogPoint],
    extent: Tuple[float, float, float, float],
    bins: int,
    out: str,
    title: str,
    dpi: int,
    figsize: float,
    white_bg: bool = True,
) -> None:
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors

    xs = np.array([p.x for p in points], dtype=float)
    ys = np.array([p.y for p in points], dtype=float)
    xmin, xmax, ymin, ymax = extent

    H, xedges, yedges = np.histogram2d(xs, ys, bins=bins,
                                        range=[[xmin, xmax], [ymin, ymax]])
    H = H.T

    if white_bg:
        cmap = plt.cm.get_cmap("YlOrRd").copy()
        cmap.set_under("white")
        vmin = 0.5   # bins with 0 visits appear white
    else:
        cmap = "inferno"
        vmin = None

    fig, ax = plt.subplots(figsize=(figsize, figsize), dpi=dpi)
    ax.set_facecolor("white")
    im = ax.imshow(
        H,
        origin="lower",
        extent=[xmin, xmax, ymin, ymax],
        cmap=cmap,
        vmin=vmin,
        interpolation="nearest",
        aspect="equal",
    )
    ax.set_title(title)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="visits")
    fig.tight_layout()
    fig.savefig(out, facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Final positions
# ---------------------------------------------------------------------------

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
    has_roles = any(p.role != 0 for p in pts)

    xmin, xmax, ymin, ymax = extent
    fig, ax = plt.subplots(figsize=(figsize, figsize), dpi=dpi)

    if has_roles:
        uninf = [p for p in pts if p.role == 0]
        lead  = [p for p in pts if p.role == 1]
        dis   = [p for p in pts if p.role == 2]
        if uninf:
            ax.scatter([p.x for p in uninf], [p.y for p in uninf],
                       s=18, color="gray",    label="uninformed", alpha=0.7, zorder=3)
        if lead:
            ax.scatter([p.x for p in lead], [p.y for p in lead],
                       s=18, color="steelblue", label="leader",  alpha=0.9, zorder=3)
        if dis:
            ax.scatter([p.x for p in dis], [p.y for p in dis],
                       s=18, color="tomato",  label="dissident", alpha=0.9, zorder=3)
        ax.legend(loc="upper right", fontsize=8)
    else:
        ax.scatter([p.x for p in pts], [p.y for p in pts],
                   s=12, alpha=0.9, zorder=3)

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(title)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    fig.tight_layout()
    fig.savefig(out, facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Animation
# ---------------------------------------------------------------------------

def _follow_center(
    pts: List[LogPoint],
    follow_n: Optional[int],
) -> Tuple[float, float]:
    """Centroid of all robots, or of the follow_n closest to the initial centroid."""
    if not pts:
        return 0.0, 0.0
    xs = np.array([p.x for p in pts], dtype=float)
    ys = np.array([p.y for p in pts], dtype=float)
    cx, cy = xs.mean(), ys.mean()
    if follow_n is None or follow_n >= len(pts):
        return float(cx), float(cy)
    dists = np.hypot(xs - cx, ys - cy)
    idx = np.argsort(dists)[:follow_n]
    return float(xs[idx].mean()), float(ys[idx].mean())


def animate(
    points: List[LogPoint],
    extent: Tuple[float, float, float, float],
    out: str,
    fps: int,
    stride: int,
    dpi: int,
    figsize: float,
    goal_heading: Optional[float] = None,
    diss_goal_heading: Optional[float] = None,
    view: str = "arena",
    follow_radius: float = 5.0,
    follow_n: Optional[int] = None,
) -> None:
    """
    view modes:
      'arena'  — fixed window from --extent / --arena-size (default).
      'follow' — camera tracks the swarm centroid; window half-width = follow_radius.
                 follow_n: if set, track centroid of the N closest robots only
                 (useful to ignore scattered outliers).
    """
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.animation import FuncAnimation

    by_step: Dict[int, List[LogPoint]] = {}
    for p in points:
        by_step.setdefault(p.step, []).append(p)
    steps = sorted(by_step.keys())
    if stride and stride > 1:
        steps = steps[::stride]

    has_roles = any(p.role != 0 for p in points)
    following  = (view == "follow")

    xmin, xmax, ymin, ymax = extent
    fig, ax = plt.subplots(figsize=(figsize, figsize), dpi=dpi)

    COLOR_UNINF = "#aaaaaa"
    COLOR_LEAD  = "#3a86ff"
    COLOR_DISS  = "#ff3a3a"

    # Adaptive dot size: render robots at ~3× Khepera IV body diameter (14 cm)
    # so they are visible regardless of follow_radius or arena_size.
    # matplotlib scatter s = area in points².  1 point = figsize*72 / window_m metres.
    window_m   = 2 * follow_radius if following else max(xmax - xmin, ymax - ymin)
    pts_per_m  = figsize * 72 / window_m
    dot        = int((3.0 * 0.14 * pts_per_m) ** 2)   # 3× robot diameter
    dot        = max(dot, 8)                           # floor so arena view isn't invisible

    if has_roles:
        scat_uninf = ax.scatter([], [], s=dot,     color=COLOR_UNINF, zorder=2, label="uninformed")
        scat_maj   = ax.scatter([], [], s=dot,     color=COLOR_LEAD,  zorder=3, label="leader")
        scat_dis   = ax.scatter([], [], s=dot,     color=COLOR_DISS,  zorder=3, label="dissident")
    else:
        scat_uninf = None
        scat_maj   = ax.scatter([], [], s=dot, color=COLOR_LEAD, zorder=3)
        scat_dis   = None

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")

    if not following:
        # Static goal arrows centered in the fixed window
        acx, acy = (xmin + xmax) / 2, (ymin + ymax) / 2
        arrow_r  = (xmax - xmin) * 0.35
        if goal_heading is not None:
            ax.annotate("", xy=(acx + arrow_r * math.cos(goal_heading),
                                acy + arrow_r * math.sin(goal_heading)),
                        xytext=(acx, acy),
                        arrowprops=dict(arrowstyle="-|>", color=COLOR_LEAD, lw=2))
        if diss_goal_heading is not None:
            ax.annotate("", xy=(acx + arrow_r * math.cos(diss_goal_heading),
                                acy + arrow_r * math.sin(diss_goal_heading)),
                        xytext=(acx, acy),
                        arrowprops=dict(arrowstyle="-|>", color=COLOR_DISS, lw=2))

    if has_roles:
        handles = [
            mpatches.Patch(color=COLOR_UNINF, label="uninformed"),
            mpatches.Patch(color=COLOR_LEAD,  label="leader"),
            mpatches.Patch(color=COLOR_DISS,  label="dissident"),
        ]
        ax.legend(handles=handles, loc="upper right", fontsize=8)

    title_obj = ax.set_title("")

    def _set_offsets(scat, pts_list):
        if pts_list:
            scat.set_offsets(np.c_[[p.x for p in pts_list], [p.y for p in pts_list]])
        else:
            scat.set_offsets(np.zeros((0, 2)))

    def init():
        scat_maj.set_offsets(np.zeros((0, 2)))
        if scat_uninf is not None:
            scat_uninf.set_offsets(np.zeros((0, 2)))
        if scat_dis is not None:
            scat_dis.set_offsets(np.zeros((0, 2)))
        return (scat_maj,) + ((scat_uninf,) if scat_uninf else ()) + ((scat_dis,) if scat_dis else ())

    def update(i: int):
        step       = steps[i]
        frame_pts  = by_step.get(step, [])
        uninf_pts  = [p for p in frame_pts if p.role == 0]
        lead_pts   = [p for p in frame_pts if p.role == 1]
        dis_pts    = [p for p in frame_pts if p.role == 2]
        draw_maj   = lead_pts if has_roles else frame_pts

        _set_offsets(scat_maj, draw_maj)
        if scat_uninf is not None:
            _set_offsets(scat_uninf, uninf_pts)
        if scat_dis is not None:
            _set_offsets(scat_dis, dis_pts)

        if following and frame_pts:
            fcx, fcy = _follow_center(frame_pts, follow_n)
            r = follow_radius
            ax.set_xlim(fcx - r, fcx + r)
            ax.set_ylim(fcy - r, fcy + r)   # square window → no aspect conflict

        title_obj.set_text(f"step={step}  ({i+1}/{len(steps)})"
                           + (f"  [follow r={follow_radius}m"
                              + (f" n={follow_n}" if follow_n else "") + "]"
                              if following else ""))
        artists = (scat_maj,) + ((scat_uninf,) if scat_uninf else ()) \
                              + ((scat_dis,)   if scat_dis   else ()) \
                              + (title_obj,)
        return artists

    # blit=False required for follow mode (axis limits change each frame)
    anim = FuncAnimation(fig, update, frames=len(steps),
                         init_func=init, interval=1000 / max(fps, 1),
                         blit=not following)
    ext = os.path.splitext(out)[1].lower()
    if ext == ".gif":
        anim.save(out, writer="pillow", fps=fps)
    else:
        anim.save(out, writer="ffmpeg", fps=fps)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Order parameters
# ---------------------------------------------------------------------------

def _group_positions_by_step(
    points: List[LogPoint],
) -> Tuple[List[int], Dict[int, Dict[int, Tuple[float, float, float]]]]:
    by_step: Dict[int, Dict[int, Tuple[float, float, float]]] = {}
    for p in points:
        by_step.setdefault(p.step, {})[p.rid] = (p.x, p.y, p.yaw)
    return sorted(by_step.keys()), by_step


def compute_order_parameters(
    points: List[LogPoint],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    steps, by_step = _group_positions_by_step(points)
    prev_pos: Dict[int, Tuple[float, float, int]] = {}
    pol_list: List[float] = []
    mil_list: List[float] = []
    n_list: List[int] = []
    steps_out: List[int] = []

    for step in steps:
        rids = sorted(by_step[step].keys())
        if not rids:
            continue
        pos = np.array([[by_step[step][rid][0], by_step[step][rid][1]] for rid in rids])
        c = pos.mean(axis=0)
        vhat_rows, rhat_rows = [], []
        for rid in rids:
            x, y, _yaw = by_step[step][rid]
            prev = prev_pos.get(rid)
            prev_pos[rid] = (x, y, step)
            if prev is None:
                continue
            x0, y0, _ = prev
            sp = math.hypot(x - x0, y - y0)
            if sp <= 1e-9:
                continue
            vhat = np.array([(x - x0) / sp, (y - y0) / sp])
            r = np.array([x, y]) - c
            rn = math.hypot(r[0], r[1])
            if rn <= 1e-9:
                continue
            vhat_rows.append(vhat)
            rhat_rows.append(r / rn)

        if len(vhat_rows) < 3:
            continue
        V = np.stack(vhat_rows)
        R = np.stack(rhat_rows)
        pol = float(np.linalg.norm(V.mean(axis=0)))
        cross_z = R[:, 0] * V[:, 1] - R[:, 1] * V[:, 0]
        steps_out.append(step)
        pol_list.append(pol)
        mil_list.append(float(np.abs(cross_z.mean())))
        n_list.append(len(vhat_rows))

    return (
        np.array(steps_out, dtype=int),
        np.array(pol_list,  dtype=float),
        np.array(mil_list,  dtype=float),
        np.array(n_list,    dtype=int),
    )


def write_metrics_csv(
    path: str, steps: np.ndarray, pol: np.ndarray, mil: np.ndarray, n_used: np.ndarray
) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["step", "polarization", "milling", "n_agents_used"])
        for s, p, m, n in zip(steps, pol, mil, n_used):
            w.writerow([int(s), float(p), float(m), int(n)])


def plot_metrics(
    out_png: str,
    steps: np.ndarray,
    pol: np.ndarray,
    mil: np.ndarray,
    n_used: np.ndarray,
    title: str,
    dpi: int,
) -> None:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=dpi)
    ax.plot(steps, pol, label="polarization", lw=2)
    ax.plot(steps, mil, label="milling",      lw=2)
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel("step")
    ax.set_ylabel("order parameter")
    ax.grid(True, alpha=0.25)
    ax2 = ax.twinx()
    ax2.plot(steps, n_used, color="black", alpha=0.2, lw=1, label="agents used")
    ax2.set_ylabel("agents used")
    ax.set_title(title)
    lines, labels = ax.get_legend_handles_labels()
    l2, lb2 = ax2.get_legend_handles_labels()
    ax.legend(lines + l2, labels + lb2, loc="upper right")
    fig.tight_layout()
    fig.savefig(out_png, facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--logdir",       default="logs")
    ap.add_argument("--mode",         choices=["heatmap", "final", "anim", "metrics"], default="heatmap")
    ap.add_argument("--out",          default=None)
    ap.add_argument("--csv",          default=None)
    ap.add_argument("--start-step",   type=int,   default=None)
    ap.add_argument("--end-step",     type=int,   default=None)
    ap.add_argument("--tail",         type=int,   default=400)
    ap.add_argument("--bins",         type=int,   default=80)
    ap.add_argument("--dpi",          type=int,   default=220)
    ap.add_argument("--figsize",      type=float, default=6.0)
    ap.add_argument("--arena-size",   type=float, default=10.0)
    ap.add_argument("--extent",       type=float, nargs=4, default=None,
                    metavar=("XMIN", "XMAX", "YMIN", "YMAX"))
    ap.add_argument("--center-radius",type=float, default=None)
    ap.add_argument("--fps",          type=int,   default=30)
    ap.add_argument("--stride",       type=int,   default=2)
    ap.add_argument("--title",         default=None,
                    help="Custom plot title (overrides the auto-generated one)")
    ap.add_argument("--no-white-bg",  action="store_true",
                    help="Use dark (inferno) colormap instead of white-background heatmap")
    # Goal arrows for dissident animation
    ap.add_argument("--goal-heading",      type=float, default=None,
                    help="Majority goal heading in radians (draws arrow in animation)")
    ap.add_argument("--diss-goal-heading", type=float, default=None,
                    help="Dissident goal heading in radians (draws arrow in animation)")
    # Camera / view mode
    ap.add_argument("--view", choices=["arena", "follow"], default="arena",
                    help="arena=fixed window (default), follow=track swarm centroid")
    ap.add_argument("--follow-radius", type=float, default=5.0,
                    help="Half-width of follow window in metres (--view follow)")
    ap.add_argument("--follow-n", type=int, default=None,
                    help="Track centroid of the N closest robots; omit to use all")
    args = ap.parse_args()

    extent = _parse_extent(args.extent, args.arena_size, args.center_radius)
    points = read_logs(args.logdir)
    points = select_window(points, args.start_step, args.end_step)
    if not points:
        raise SystemExit("No points left after applying step window")
    points = select_tail(points, args.tail)

    out = args.out or {
        "heatmap": "heatmap.png",
        "final":   "final_positions.png",
        "anim":    "traj.mp4",
        "metrics": "metrics.png",
    }[args.mode]

    window_str = ""
    if args.start_step is not None or args.end_step is not None:
        window_str = f" steps=[{args.start_step},{args.end_step}]"
    auto_title = (f"{args.mode} · {os.path.basename(os.path.abspath(args.logdir))}"
                  f"  tail={args.tail}{window_str}")
    title = args.title if args.title is not None else auto_title

    try:
        if args.mode == "heatmap":
            plot_heatmap(points, extent=extent, bins=args.bins, out=out,
                         title=title, dpi=args.dpi, figsize=args.figsize,
                         white_bg=not args.no_white_bg)
        elif args.mode == "final":
            plot_final(points, extent=extent, out=out,
                       title=title, dpi=args.dpi, figsize=args.figsize)
        elif args.mode == "anim":
            animate(points, extent=extent, out=out, fps=args.fps,
                    stride=args.stride, dpi=args.dpi, figsize=args.figsize,
                    goal_heading=args.goal_heading,
                    diss_goal_heading=args.diss_goal_heading,
                    view=args.view,
                    follow_radius=args.follow_radius,
                    follow_n=args.follow_n)
        else:
            steps, pol, mil, n_used = compute_order_parameters(points)
            if steps.size == 0:
                raise RuntimeError("Not enough data (need >=2 samples per robot, >=3 robots)")
            csv_out = args.csv or os.path.splitext(out)[0] + ".csv"
            write_metrics_csv(csv_out, steps, pol, mil, n_used)
            plot_metrics(out, steps, pol, mil, n_used, title=title, dpi=args.dpi)
            print(csv_out)
    except Exception as e:
        raise SystemExit(f"Failed: {e}")

    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
