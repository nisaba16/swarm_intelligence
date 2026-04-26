#!/usr/bin/env python3
"""Rule-based baseline figure: 3-panel trajectory + order-parameter plot.

Produces a publication figure with two rows:
  Row 1 — trajectory plots (polarized | milling | conflict)
  Row 2 — polarization & milling order parameters over time (one per scenario)

Run after each ARGoS experiment.  Each scenario writes its own log dir:
  Argos_files/logs_polarized/   collective_polarized.argos
  Argos_files/logs_milling/     collective_milling.argos
  Argos_files/logs_conflict/    collective_conflict.argos

Usage:
  python3 plot_rule_based.py
  python3 plot_rule_based.py --logbase Argos_files --out fig2.pdf --tail 600
  python3 plot_rule_based.py --no-metrics
"""

from __future__ import annotations

import argparse
import math
import os
import sys

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

# Re-use parsers and order-parameter code from the shared script.
sys.path.insert(0, os.path.dirname(__file__))
from plot_trajectories import (
    LogPoint,
    compute_order_parameters,
    read_logs,
    select_tail,
)

COLOR_LEAD  = "#3a86ff"
COLOR_DISS  = "#ff3a3a"
COLOR_NEUT  = "#aaaaaa"
ALPHA_LINE  = 0.25
LW          = 0.6

SCENARIOS = ["polarized", "milling", "conflict"]
TITLES    = ["(a) Polarized", "(b) Milling", "(c) Conflict"]


def _role_color(role: int) -> str:
    if role == 1:
        return COLOR_LEAD
    if role == 2:
        return COLOR_DISS
    return COLOR_NEUT


def draw_trajectories(
    ax: plt.Axes,
    points: list[LogPoint],
    extent: tuple[float, float, float, float],
    title: str,
    tail: int,
    goal_heading: float | None = None,
    diss_heading: float | None = None,
) -> None:
    pts = select_tail(points, tail)

    by_robot: dict[int, list[LogPoint]] = {}
    for p in pts:
        by_robot.setdefault(p.rid, []).append(p)

    for robot_pts in by_robot.values():
        robot_pts.sort(key=lambda p: p.step)
        role  = robot_pts[-1].role
        color = _role_color(role)
        xs = [p.x for p in robot_pts]
        ys = [p.y for p in robot_pts]
        ax.plot(xs, ys, color=color, lw=LW, alpha=ALPHA_LINE, zorder=2)
        ax.plot(xs[-1], ys[-1], "o", color=color, ms=2.5, alpha=0.85, zorder=3)

    xmin, xmax, ymin, ymax = extent
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal", adjustable="box")
    ax.set_facecolor("white")
    ax.set_title(title, fontsize=9, fontweight="bold")
    ax.set_xlabel("x (m)", fontsize=7)
    ax.set_ylabel("y (m)", fontsize=7)
    ax.tick_params(labelsize=6)

    if goal_heading is not None:
        cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
        r = (xmax - xmin) * 0.3
        ax.annotate("", xy=(cx + r * math.cos(goal_heading),
                             cy + r * math.sin(goal_heading)),
                    xytext=(cx, cy),
                    arrowprops=dict(arrowstyle="-|>", color=COLOR_LEAD, lw=1.5))
    if diss_heading is not None:
        cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
        r = (xmax - xmin) * 0.3
        ax.annotate("", xy=(cx + r * math.cos(diss_heading),
                             cy + r * math.sin(diss_heading)),
                    xytext=(cx, cy),
                    arrowprops=dict(arrowstyle="-|>", color=COLOR_DISS, lw=1.5))


def draw_metrics(
    ax: plt.Axes,
    points: list[LogPoint],
    title: str,
) -> None:
    steps, pol, mil, _ = compute_order_parameters(points)
    if steps.size == 0:
        ax.text(0.5, 0.5, "insufficient data", transform=ax.transAxes,
                ha="center", va="center", fontsize=7, color="gray")
        return
    ax.plot(steps, pol, lw=1.5, color="#3a86ff", label="polarization")
    ax.plot(steps, mil, lw=1.5, color="#ff6b35", label="milling",      ls="--")
    ax.set_ylim(-0.02, 1.05)
    ax.set_xlabel("step", fontsize=7)
    ax.set_ylabel("order param.", fontsize=7)
    ax.tick_params(labelsize=6)
    ax.grid(True, alpha=0.2)
    ax.set_title(title, fontsize=8)
    ax.legend(fontsize=6, loc="upper right")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--logbase",    default="Argos_files",
                    help="Directory containing the logs_* subdirectories")
    ap.add_argument("--tail",       type=int,   default=500,
                    help="Tail N steps for trajectory plots (0=all)")
    ap.add_argument("--arena-size", type=float, default=29.0,
                    help="Arena side length in metres (sets plot extent)")
    ap.add_argument("--extent",     type=float, nargs=4, default=None,
                    metavar=("XMIN", "XMAX", "YMIN", "YMAX"))
    ap.add_argument("--out",        default="fig_rule_based.pdf")
    ap.add_argument("--dpi",        type=int,   default=220)
    ap.add_argument("--no-metrics", action="store_true",
                    help="Skip order-parameter row (trajectories only)")
    # Goal arrows for conflict panel
    ap.add_argument("--goal-heading",      type=float, default=0.0,
                    help="Leader goal heading in radians (default 0 = east)")
    ap.add_argument("--diss-goal-heading", type=float, default=math.pi,
                    help="Dissident goal heading in radians (default π = west)")
    args = ap.parse_args()

    if args.extent:
        extent = tuple(args.extent)
    else:
        h = args.arena_size / 2
        extent = (-h, h, -h, h)

    # Each scenario has its own original arena size
    EXTENTS = {
        "polarized": (-3.5, 3.5, -3.5, 3.5),
        "milling":   (-3.5, 3.5, -3.5, 3.5),
        "conflict":  (-5.0, 5.0, -5.0, 5.0),
    }

    nrows  = 1 if args.no_metrics else 2
    fig, axes = plt.subplots(
        nrows, 3,
        figsize=(4.5 * 3, 4.0 * nrows),
        dpi=args.dpi,
        squeeze=False,
    )
    fig.patch.set_facecolor("white")

    any_ok = False
    for col, (scenario, title) in enumerate(zip(SCENARIOS, TITLES)):
        logdir = os.path.join(args.logbase, f"logs_{scenario}")
        ax_traj = axes[0][col]
        sc_extent = args.extent if args.extent else EXTENTS[scenario]

        try:
            pts = read_logs(logdir)
        except (FileNotFoundError, ValueError) as e:
            for row in range(nrows):
                axes[row][col].text(
                    0.5, 0.5, f"No logs:\n{logdir}",
                    transform=axes[row][col].transAxes,
                    ha="center", va="center", fontsize=7, color="gray",
                )
                axes[row][col].set_title(title, fontsize=9, fontweight="bold")
            continue

        any_ok = True

        goal  = args.goal_heading      if scenario == "conflict" else None
        diss  = args.diss_goal_heading if scenario == "conflict" else None
        draw_trajectories(ax_traj, pts, sc_extent, title,
                          tail=args.tail,
                          goal_heading=goal,
                          diss_heading=diss)

        if not args.no_metrics:
            draw_metrics(axes[1][col], pts, title="")
        extent = sc_extent  # suppress unused-variable warning

    # Shared legend
    handles = [
        mpatches.Patch(color=COLOR_LEAD, label="leader"),
        mpatches.Patch(color=COLOR_DISS, label="dissident"),
        mpatches.Patch(color=COLOR_NEUT, label="neutral"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3,
               fontsize=8, frameon=True, bbox_to_anchor=(0.5, 0.0))

    fig.suptitle("Rule-based collective motion baselines", fontsize=11, y=1.01)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(args.out, facecolor="white", bbox_inches="tight")
    plt.close(fig)

    if not any_ok:
        print("Warning: no logs found in any scenario directory. "
              "Run the ARGoS experiments first.", file=sys.stderr)
        return 1

    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
