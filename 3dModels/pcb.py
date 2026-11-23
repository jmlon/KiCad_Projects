"""Parametric 3D models for rectangular module PCBs using build123d."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from build123d import (
    Align,
    Axis,
    Box,
    BuildPart,
    Color,
    Cylinder,
    Locations,
    Mode,
    Part,
    export_step,
    fillet,
)

import common

STEP_MODELS_DIR = Path(__file__).resolve().parent / "stepModels"

PCB_COLORS: dict[str, Color] = {
    "green": Color(0.08, 0.38, 0.16),
    "purple": Color(0.28, 0.12, 0.42),
    "blue": Color(0.08, 0.24, 0.54),
    "red": Color(0.65, 0.10, 0.12),
    "black": Color(0.10, 0.10, 0.11),
    "white": Color(0.90, 0.90, 0.88),
    "yellow": Color(0.85, 0.70, 0.10),
}

ColorSpec = str | Color | tuple[float, float, float]


def resolve_pcb_color(color: ColorSpec) -> tuple[Color, str]:
    """Resolve a PCB color specification into `(Color, filename_suffix)`.

    Supports preset names (`green`, `purple`, `blue`, `red`, `black`, `white`,
    `yellow`), CSS color names, `#RRGGBB` hex strings, RGB float tuples, or
    `build123d.Color` instances.
    """
    if isinstance(color, Color):
        r, g, b = (round(c * 255) for c in tuple(color)[:3])
        return color, f"_{r:02X}{g:02X}{b:02X}"

    if isinstance(color, tuple):
        if len(color) != 3:
            raise ValueError(f"RGB color tuple must have 3 values, got {color}")
        resolved = Color(*color)
        r, g, b = (round(c * 255) for c in color)
        return resolved, f"_{r:02X}{g:02X}{b:02X}"

    key = color.strip().lower()
    if key in PCB_COLORS:
        return PCB_COLORS[key], f"_{key.capitalize()}"

    hex_str = key.lstrip("#")
    if len(hex_str) == 6 and all(c in "0123456789abcdef" for c in hex_str):
        rf = int(hex_str[0:2], 16) / 255.0
        gf = int(hex_str[2:4], 16) / 255.0
        bf = int(hex_str[4:6], 16) / 255.0
        return Color(rf, gf, bf), f"_{hex_str.upper()}"

    try:
        resolved = Color(key)
    except ValueError as exc:
        valid = ", ".join(PCB_COLORS)
        raise ValueError(
            f"Unsupported PCB color {color!r}. Use one of ({valid}), "
            "a CSS color name, a #RRGGBB hex string, an RGB tuple, or a Color."
        ) from exc
    return resolved, f"_{key.capitalize()}"


def module_pcb(
    width: float,
    length: float,
    thickness: float = common.pcb_width_16,
    color: ColorSpec = "green",
    corner_radius: float = 0.0,
    holes: Sequence[tuple[float, float, float]] | None = None,
    export: bool = False,
    name: str | None = None,
) -> Part:
    """Create a rectangular PCB centered in XY with Z from 0 to `thickness`.

    Args:
        width: PCB dimension along X in mm.
        length: PCB dimension along Y in mm.
        thickness: PCB thickness along Z in mm (default: `common.pcb_width_16`).
        color: Solder-mask color preset (`"green"`, `"purple"`, etc.), CSS
            color name, `#RRGGBB` hex string, RGB float tuple, or `Color`
            (default: `"green"`).
        corner_radius: Optional vertical corner fillet radius in mm.
        holes: Optional sequence of `(x, y, diameter)` through-holes in mm,
            relative to the PCB center.
        export: When True, exports the STEP model to `./stepModels/`.
        name: Optional model/file stem name when exporting.

    Returns:
        A `Part` representing the PCB.
    """
    if width <= 0 or length <= 0 or thickness <= 0:
        raise ValueError(
            f"PCB dimensions must be > 0, got ({width}, {length}, {thickness})"
        )
    if corner_radius < 0:
        raise ValueError(f"corner_radius must be >= 0, got {corner_radius}")
    if corner_radius >= min(width, length) / 2:
        raise ValueError(
            f"corner_radius ({corner_radius}) must be < half the smallest side"
        )

    pcb_color, color_suffix = resolve_pcb_color(color)

    with BuildPart() as pcb_builder:
        Box(
            width,
            length,
            thickness,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        )
        if corner_radius > 0:
            vertical_edges = pcb_builder.edges().filter_by(Axis.Z)
            fillet(vertical_edges, radius=corner_radius)
        if holes:
            for hx, hy, diameter in holes:
                if diameter <= 0:
                    raise ValueError(
                        f"Hole diameter must be > 0, got {diameter}"
                    )
                with Locations((hx, hy, 0)):
                    Cylinder(
                        radius=diameter / 2,
                        height=thickness,
                        align=(Align.CENTER, Align.CENTER, Align.MIN),
                        mode=Mode.SUBTRACT,
                    )

    assert pcb_builder.part is not None
    board = pcb_builder.part
    board.color = pcb_color
    board.label = name or "PCB"

    if export:
        STEP_MODELS_DIR.mkdir(parents=True, exist_ok=True)
        stem = name or f"PCB_{width:g}x{length:g}mm{color_suffix}"
        export_step(board, str(STEP_MODELS_DIR / f"{stem}.step"))

    return board


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a 3D STEP model for a rectangular module PCB."
    )
    parser.add_argument("width", type=float, help="PCB width (X) in mm.")
    parser.add_argument("length", type=float, help="PCB length (Y) in mm.")
    parser.add_argument(
        "--thickness",
        type=float,
        default=common.pcb_width_16,
        help=f"PCB thickness in mm (default: {common.pcb_width_16}).",
    )
    parser.add_argument(
        "--color",
        default="green",
        help=(
            "PCB solder-mask color (green, purple, blue, red, black, white, "
            "yellow, CSS color, or #RRGGBB; default: green)."
        ),
    )
    parser.add_argument(
        "--corner-radius",
        type=float,
        default=0.0,
        help="Optional corner fillet radius in mm (default: 0).",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export the generated model to ./stepModels/.",
    )
    args = parser.parse_args()
    module_pcb(
        width=args.width,
        length=args.length,
        thickness=args.thickness,
        color=args.color,
        corner_radius=args.corner_radius,
        export=args.export,
    )
