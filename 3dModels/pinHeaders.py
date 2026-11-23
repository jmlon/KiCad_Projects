"""Parametric 3D models for male and female pin headers using build123d."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Literal

from build123d import (
    Align,
    Axis,
    Box,
    BuildLine,
    BuildPart,
    BuildSketch,
    Color,
    Compound,
    GridLocations,
    Location,
    Locations,
    Mode,
    Part,
    Plane,
    Polyline,
    Rectangle,
    chamfer,
    export_step,
    extrude,
    fillet,
    sweep,
)

import common

STEP_MODELS_DIR = Path(__file__).resolve().parent / "stepModels"

PLASTIC_COLOR = Color(0.12, 0.12, 0.12)
GOLD_PIN_COLOR = Color(0.85, 0.68, 0.25)
TIN_PIN_COLOR = Color(0.80, 0.80, 0.83)

HEADER_COLORS: dict[str, Color] = {
    "black": PLASTIC_COLOR,
    "white": Color(0.92, 0.92, 0.90),
    "red": Color(0.75, 0.12, 0.12),
    "blue": Color(0.12, 0.30, 0.72),
    "green": Color(0.14, 0.52, 0.22),
    "yellow": Color(0.88, 0.72, 0.10),
    "orange": Color(0.88, 0.42, 0.08),
    "gray": Color(0.45, 0.47, 0.50),
    "grey": Color(0.45, 0.47, 0.50),
}

ColorSpec = str | Color | tuple[float, float, float]


def _resolve_color(color: ColorSpec) -> tuple[Color, str]:
    """Resolve a color specification into a `(Color, filename_suffix)` pair.

    Default `"black"` returns an empty suffix so standard black headers keep
    the canonical KiCad filename. Other colors return a suffix like `"_Red"`
    or `"_FF4400"`.
    """
    if isinstance(color, Color):
        if tuple(color) == tuple(PLASTIC_COLOR):
            return color, ""
        r, g, b = (round(c * 255) for c in tuple(color)[:3])
        return color, f"_{r:02X}{g:02X}{b:02X}"

    if isinstance(color, tuple):
        if len(color) != 3:
            raise ValueError(f"RGB color tuple must have 3 values, got {color}")
        resolved = Color(*color)
        r, g, b = (round(c * 255) for c in color)
        return resolved, f"_{r:02X}{g:02X}{b:02X}"

    key = color.strip().lower()
    if key in HEADER_COLORS:
        suffix = "" if key == "black" else f"_{key.capitalize()}"
        return HEADER_COLORS[key], suffix

    hex_str = key.lstrip("#")
    if len(hex_str) == 6 and all(c in "0123456789abcdef" for c in hex_str):
        rf = int(hex_str[0:2], 16) / 255.0
        gf = int(hex_str[2:4], 16) / 255.0
        bf = int(hex_str[4:6], 16) / 255.0
        return Color(rf, gf, bf), f"_{hex_str.upper()}"

    # Fall back to build123d's CSS color name support (e.g. "purple", "cyan")
    try:
        resolved = Color(key)
    except ValueError as exc:
        valid = ", ".join(k for k in HEADER_COLORS if k != "grey")
        raise ValueError(
            f"Unsupported color {color!r}. Use one of ({valid}), "
            "a CSS color name, a #RRGGBB hex string, an RGB tuple, or a Color."
        ) from exc
    return resolved, f"_{key.capitalize()}"


def _validate_counts(pins: int, rows: int) -> None:
    if pins < 1:
        raise ValueError(f"pins must be >= 1, got {pins}")
    if rows < 1:
        raise ValueError(f"rows must be >= 1, got {rows}")


def _export_model(model: Compound, filename: str) -> Path:
    STEP_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = STEP_MODELS_DIR / filename
    export_step(model, str(output_path))
    return output_path


def _build_male_pin() -> Part:
    """Build a single square male header pin centered in XY.

    Z = 0 is the bottom of the plastic insulator (PCB top surface).
    The solder tail extends below Z = 0 by `male_pin_length_over_insulator`
    (3.0 mm), and the mating post extends above the insulator by the remaining
    pin length (`male_pin_height - male_pin_insulation_height - 3.0` = 5.7 mm).
    """
    pin_size = common.male_pin_tickness
    pin_height = common.male_pin_height
    z_bottom = -common.male_pin_length_over_insulator
    tip_chamfer = min(0.15, pin_size * 0.25)

    with BuildPart() as pin_builder:
        with Locations((0, 0, z_bottom)):
            Box(
                pin_size,
                pin_size,
                pin_height,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
            )
        top_and_bottom_edges = pin_builder.edges().filter_by_position(
            Axis.Z, z_bottom, z_bottom, inclusive=(True, True)
        ) + pin_builder.edges().filter_by_position(
            Axis.Z,
            z_bottom + pin_height,
            z_bottom + pin_height,
            inclusive=(True, True),
        )
        chamfer(top_and_bottom_edges, length=tip_chamfer)

    assert pin_builder.part is not None
    return pin_builder.part


def male_pin_header(
    pins: int,
    rows: int = 1,
    export: bool = False,
    color: ColorSpec = "black",
) -> Compound:
    """Create a vertical through-hole male pin header of `rows x pins`.

    Pin 1 is located at (X=0, Y=0) with Z=0 at the PCB top surface.
    Pins step along +X by `common.male_pin_pitch` and rows step along +Y.

    Args:
        pins: Number of pins per row.
        rows: Number of rows (default: 1).
        export: When True, exports the STEP model to `./stepModels/`.
        color: Plastic insulator color name (e.g. `"black"`, `"red"`, `"blue"`),
            `#RRGGBB` hex string, RGB float tuple, or `build123d.Color`
            (default: `"black"`).

    Returns:
        A `Compound` containing the insulator and gold-plated pins.
    """
    _validate_counts(pins, rows)
    plastic_color, color_suffix = _resolve_color(color)

    pitch = common.male_pin_pitch
    ins_height = common.male_pin_insulation_height
    ins_width = (rows - 1) * pitch + common.male_pin_insulation_width
    ins_length = pins * pitch

    center_x = (pins - 1) * pitch / 2
    center_y = (rows - 1) * pitch / 2

    # Plastic insulator with breakaway V-notches between pins
    notch_size = 0.4
    with BuildPart() as insulator_builder:
        with Locations((center_x, center_y, 0)):
            Box(
                ins_length,
                ins_width,
                ins_height,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
            )
        if pins > 1:
            notch_locations = [
                Location(
                    ((i + 0.5) * pitch, center_y + y_sign * (ins_width / 2), 0),
                    (0, 0, 45),
                )
                for i in range(pins - 1)
                for y_sign in (-1, 1)
            ]
            with Locations(notch_locations):
                Box(
                    notch_size,
                    notch_size,
                    ins_height,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )

    assert insulator_builder.part is not None
    insulator = insulator_builder.part
    insulator.color = plastic_color
    insulator.label = "Insulator"

    # Metal pins
    single_pin = _build_male_pin()
    pin_parts = [
        single_pin.moved(Location((i * pitch, r * pitch, 0)))
        for r in range(rows)
        for i in range(pins)
    ]
    pins_compound = Compound(children=pin_parts, label="Pins")
    pins_compound.color = GOLD_PIN_COLOR

    model_name = (
        f"PinHeader_{rows}x{pins:02d}_P{pitch:.2f}mm_Vertical{color_suffix}"
    )
    model = Compound(children=[insulator, pins_compound], label=model_name)

    if export:
        _export_model(model, f"{model_name}.step")

    return model


def _build_angled_male_pin(
    y_tail: float,
    z_bend: float,
    y_tip: float,
) -> Part:
    """Build a single 90-degree bent square male header pin at `X = 0`.

    The solder tail extends vertically downward from `(0, y_tail, z_bend)` to
    `(0, y_tail, -male_pin_length_over_insulator)`, bends 90 degrees with a
    smooth radius into `+Y`, and extends horizontally to `(0, y_tip, z_bend)`.
    """
    pin_size = common.male_pin_tickness
    z_bottom = -common.male_pin_length_over_insulator
    bend_radius = 0.8
    tip_chamfer = min(0.15, pin_size * 0.25)

    with BuildPart() as pin_builder:
        with BuildLine() as path:
            wire = Polyline(
                (0, y_tail, z_bottom),
                (0, y_tail, z_bend),
                (0, y_tip, z_bend),
            )
            fillet(wire.vertices()[1], radius=bend_radius)
        with BuildSketch(Plane.XY.offset(z_bottom)), Locations((0, y_tail)):
            Rectangle(pin_size, pin_size)
        sweep(path=path.line)

        bottom_edges = pin_builder.edges().filter_by_position(
            Axis.Z, z_bottom, z_bottom, inclusive=(True, True)
        )
        front_edges = pin_builder.edges().filter_by_position(
            Axis.Y, y_tip, y_tip, inclusive=(True, True)
        )
        chamfer(bottom_edges + front_edges, length=tip_chamfer)

    assert pin_builder.part is not None
    return pin_builder.part


def angled_male_pin_header(
    pins: int,
    rows: int = 1,
    export: bool = False,
    color: ColorSpec = "black",
) -> Compound:
    """Create a right-angle (horizontal) through-hole male pin header of `rows x pins`.

    Pin 1 solder tail enters the PCB at `(X=0, Y=0, Z=0)`. Pins step along `+X`
    by `common.male_pin_pitch` and additional rows step along `+Y`. The plastic
    insulator rests on `Z=0`, solder tails extend into `Z < 0`, and the bent
    mating posts extend horizontally along `+Y`.

    Args:
        pins: Number of pins per row.
        rows: Number of rows (default: 1).
        export: When True, exports the STEP model to `./stepModels/`.
        color: Plastic insulator color name, `#RRGGBB` hex string, RGB float
            tuple, or `build123d.Color` (default: `"black"`).

    Returns:
        A `Compound` containing the insulator and gold-plated angled pins.
    """
    _validate_counts(pins, rows)
    plastic_color, color_suffix = _resolve_color(color)

    pitch = common.male_pin_pitch
    ins_depth = common.male_pin_insulation_height  # 2.5 mm along +Y
    ins_height = (rows - 1) * pitch + common.male_pin_insulation_width  # Z
    ins_length = pins * pitch  # X

    bend_clearance = 1.5
    ins_y_start = (rows - 1) * pitch + bend_clearance
    mating_length = (
        common.male_pin_height
        - common.male_pin_insulation_height
        - common.male_pin_length_over_insulator
    )
    y_tip = ins_y_start + ins_depth + mating_length

    center_x = (pins - 1) * pitch / 2
    center_y = ins_y_start + ins_depth / 2

    # Plastic insulator resting on Z=0 with breakaway V-notches between pins
    notch_size = 0.4
    with BuildPart() as insulator_builder:
        with Locations((center_x, center_y, 0)):
            Box(
                ins_length,
                ins_depth,
                ins_height,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
            )
        if pins > 1:
            notch_locations = [
                Location(
                    ((i + 0.5) * pitch, center_y, z_face),
                    (0, 45, 0),
                )
                for i in range(pins - 1)
                for z_face in (0.0, ins_height)
            ]
            with Locations(notch_locations):
                Box(
                    notch_size,
                    ins_depth,
                    notch_size,
                    align=(Align.CENTER, Align.CENTER, Align.CENTER),
                    mode=Mode.SUBTRACT,
                )

    assert insulator_builder.part is not None
    insulator = insulator_builder.part
    insulator.color = plastic_color
    insulator.label = "Insulator"

    # Metal 90-degree bent pins: inner row (closest to insulator) bends lowest
    pin_parts: list[Part] = []
    for r in range(rows):
        y_tail = r * pitch
        z_bend = common.male_pin_insulation_width / 2 + (rows - 1 - r) * pitch
        row_pin = _build_angled_male_pin(
            y_tail=y_tail, z_bend=z_bend, y_tip=y_tip
        )
        for i in range(pins):
            pin_parts.append(row_pin.moved(Location((i * pitch, 0, 0))))

    pins_compound = Compound(children=pin_parts, label="Pins")
    pins_compound.color = GOLD_PIN_COLOR

    model_name = (
        f"PinHeader_{rows}x{pins:02d}_P{pitch:.2f}mm_Horizontal{color_suffix}"
    )
    model = Compound(children=[insulator, pins_compound], label=model_name)

    if export:
        _export_model(model, f"{model_name}.step")

    return model


def _build_female_solder_tail() -> Part:
    """Build a single female header solder tail centered in XY."""
    tail_width = common.male_pin_tickness
    tail_thickness = 0.4
    tail_length = common.female_solder_tail_length
    embed_depth = 0.5
    z_bottom = -tail_length
    tip_chamfer = 0.12

    with BuildPart() as tail_builder:
        with Locations((0, 0, z_bottom)):
            Box(
                tail_width,
                tail_thickness,
                tail_length + embed_depth,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
            )
        bottom_edges = tail_builder.edges().filter_by_position(
            Axis.Z, z_bottom, z_bottom, inclusive=(True, True)
        )
        chamfer(bottom_edges, length=tip_chamfer)

    assert tail_builder.part is not None
    return tail_builder.part


def female_pin_header(
    pins: int,
    rows: int = 1,
    export: bool = False,
    color: ColorSpec = "black",
) -> Compound:
    """Create a vertical through-hole female pin header (socket) of `rows x pins`.

    Pin 1 is located at (X=0, Y=0) with Z=0 at the PCB top surface.
    Pins step along +X by `common.female_pin_pitch` and rows step along +Y.

    Args:
        pins: Number of pins per row.
        rows: Number of rows (default: 1).
        export: When True, exports the STEP model to `./stepModels/`.
        color: Plastic housing color name (e.g. `"black"`, `"red"`, `"blue"`),
            `#RRGGBB` hex string, RGB float tuple, or `build123d.Color`
            (default: `"black"`).

    Returns:
        A `Compound` containing the housing and solder tails.
    """
    _validate_counts(pins, rows)
    plastic_color, color_suffix = _resolve_color(color)

    pitch = common.female_pin_pitch
    housing_height = common.female_housing_height
    housing_width = (rows - 1) * pitch + common.female_housing_width
    housing_length = pins * pitch

    center_x = (pins - 1) * pitch / 2
    center_y = (rows - 1) * pitch / 2

    socket_opening = common.female_solder_hole_diameter
    socket_depth = min(6.0, housing_height - 1.5)
    lead_in_depth = 0.3
    lead_in_size = socket_opening + 2 * lead_in_depth

    with BuildPart() as housing_builder:
        with Locations((center_x, center_y, 0)):
            Box(
                housing_length,
                housing_width,
                housing_height,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
            )
        # Socket pockets
        with (
            BuildSketch(Plane.XY.offset(housing_height)),
            Locations((center_x, center_y)),
            GridLocations(pitch, pitch, pins, rows),
        ):
            Rectangle(socket_opening, socket_opening)
        extrude(amount=-socket_depth, mode=Mode.SUBTRACT)

        # Chamfered lead-in funnel at the top of each socket
        with (
            BuildSketch(Plane.XY.offset(housing_height)),
            Locations((center_x, center_y)),
            GridLocations(pitch, pitch, pins, rows),
        ):
            Rectangle(lead_in_size, lead_in_size)
        extrude(amount=-lead_in_depth, taper=45, mode=Mode.SUBTRACT)

    assert housing_builder.part is not None
    housing = housing_builder.part
    housing.color = plastic_color
    housing.label = "Housing"

    # Solder tails
    single_tail = _build_female_solder_tail()
    tail_parts = [
        single_tail.moved(Location((i * pitch, r * pitch, 0)))
        for r in range(rows)
        for i in range(pins)
    ]
    tails_compound = Compound(children=tail_parts, label="SolderTails")
    tails_compound.color = TIN_PIN_COLOR

    model_name = (
        f"PinSocket_{rows}x{pins:02d}_P{pitch:.2f}mm_Vertical{color_suffix}"
    )
    model = Compound(children=[housing, tails_compound], label=model_name)

    if export:
        _export_model(model, f"{model_name}.step")

    return model


def pin_header(
    pins: int,
    header_type: Literal["male", "female"] = "male",
    rows: int = 1,
    export: bool = False,
    color: ColorSpec = "black",
    orientation: Literal["vertical", "horizontal", "angled"] = "vertical",
) -> Compound:
    """Create a male or female pin header of `rows x pins`.

    Args:
        pins: Number of pins per row.
        header_type: `"male"` or `"female"` (default: `"male"`).
        rows: Number of rows (default: 1).
        export: When True, exports the STEP model to `./stepModels/`.
        color: Plastic housing/insulator color (default: `"black"`).
        orientation: `"vertical"` (default), `"horizontal"`, or `"angled"`
            (right-angle; supported for male headers).

    Returns:
        A `Compound` representing the requested pin header.
    """
    if orientation not in ("vertical", "horizontal", "angled"):
        raise ValueError(
            "orientation must be 'vertical', 'horizontal', or 'angled', "
            f"got {orientation!r}"
        )

    if header_type == "male":
        if orientation == "vertical":
            return male_pin_header(
                pins=pins, rows=rows, export=export, color=color
            )
        return angled_male_pin_header(
            pins=pins, rows=rows, export=export, color=color
        )
    if header_type == "female":
        if orientation != "vertical":
            raise ValueError(
                "Angled/horizontal orientation is only supported for male "
                "pin headers."
            )
        return female_pin_header(
            pins=pins, rows=rows, export=export, color=color
        )
    raise ValueError(
        f"header_type must be 'male' or 'female', got {header_type!r}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate 3D STEP models for male or female pin headers."
    )
    parser.add_argument("pins", type=int, help="Number of pins per row.")
    parser.add_argument(
        "--type",
        dest="header_type",
        choices=("male", "female"),
        default="male",
        help="Pin header gender (default: male).",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=1,
        help="Number of rows (default: 1).",
    )
    parser.add_argument(
        "--orientation",
        choices=("vertical", "horizontal", "angled"),
        default="vertical",
        help=(
            "Pin header orientation: vertical (default) or "
            "horizontal/angled (90-degree bent male header)."
        ),
    )
    parser.add_argument(
        "--color",
        default="black",
        help=(
            "Plastic housing color name (black, white, red, blue, green, "
            "yellow, orange, gray, or CSS color) or #RRGGBB hex "
            "(default: black)."
        ),
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export the generated model to ./stepModels/.",
    )
    args = parser.parse_args()
    pin_header(
        pins=args.pins,
        header_type=args.header_type,
        rows=args.rows,
        export=args.export,
        color=args.color,
        orientation=args.orientation,
    )
