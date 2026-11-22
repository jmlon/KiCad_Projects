"""Parametric 3D models for male and female pin headers using build123d."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Literal

from build123d import (
    Align,
    Axis,
    Box,
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
    Rectangle,
    chamfer,
    export_step,
    extrude,
)

import common

STEP_MODELS_DIR = Path(__file__).resolve().parent / "stepModels"

PLASTIC_COLOR = Color(0.12, 0.12, 0.12)
GOLD_PIN_COLOR = Color(0.85, 0.68, 0.25)
TIN_PIN_COLOR = Color(0.80, 0.80, 0.83)


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
) -> Compound:
    """Create a vertical through-hole male pin header of `rows x pins`.

    Pin 1 is located at (X=0, Y=0) with Z=0 at the PCB top surface.
    Pins step along +X by `common.male_pin_pitch` and rows step along +Y.

    Args:
        pins: Number of pins per row.
        rows: Number of rows (default: 1).
        export: When True, exports the STEP model to `./stepModels/`.

    Returns:
        A `Compound` containing the insulator and gold-plated pins.
    """
    _validate_counts(pins, rows)

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
    insulator.color = PLASTIC_COLOR
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

    model_name = f"PinHeader_{rows}x{pins:02d}_P{pitch:.2f}mm_Vertical"
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
) -> Compound:
    """Create a vertical through-hole female pin header (socket) of `rows x pins`.

    Pin 1 is located at (X=0, Y=0) with Z=0 at the PCB top surface.
    Pins step along +X by `common.female_pin_pitch` and rows step along +Y.

    Args:
        pins: Number of pins per row.
        rows: Number of rows (default: 1).
        export: When True, exports the STEP model to `./stepModels/`.

    Returns:
        A `Compound` containing the housing and solder tails.
    """
    _validate_counts(pins, rows)

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
    housing.color = PLASTIC_COLOR
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

    model_name = f"PinSocket_{rows}x{pins:02d}_P{pitch:.2f}mm_Vertical"
    model = Compound(children=[housing, tails_compound], label=model_name)

    if export:
        _export_model(model, f"{model_name}.step")

    return model


def pin_header(
    pins: int,
    header_type: Literal["male", "female"] = "male",
    rows: int = 1,
    export: bool = False,
) -> Compound:
    """Create a male or female pin header of `rows x pins`.

    Args:
        pins: Number of pins per row.
        header_type: `"male"` or `"female"` (default: `"male"`).
        rows: Number of rows (default: 1).
        export: When True, exports the STEP model to `./stepModels/`.

    Returns:
        A `Compound` representing the requested pin header.
    """
    if header_type == "male":
        return male_pin_header(pins=pins, rows=rows, export=export)
    if header_type == "female":
        return female_pin_header(pins=pins, rows=rows, export=export)
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
    )
