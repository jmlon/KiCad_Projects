"""3D models for standard USB-C and Micro-USB Type-B receptacles using build123d."""

from __future__ import annotations

import argparse
from pathlib import Path

from build123d import (
    Align,
    Box,
    BuildPart,
    BuildSketch,
    Color,
    Compound,
    Cylinder,
    Locations,
    Mode,
    Part,
    Plane,
    Polygon,
    RectangleRounded,
    export_step,
    extrude,
)

STEP_MODELS_DIR = Path(__file__).resolve().parent / "stepModels"

SHELL_COLOR = Color(0.85, 0.85, 0.88)
PLASTIC_COLOR = Color(0.15, 0.15, 0.15)
GOLD_CONTACT_COLOR = Color(0.90, 0.75, 0.25)

# USB-C receptacle dimensions (mm)
USB_C_WIDTH = 8.8
USB_C_HEIGHT = 3.2
USB_C_DEPTH = 7.4
USB_C_OUTER_RADIUS = 1.0
USB_C_HOLE_WIDTH = 7.8
USB_C_HOLE_HEIGHT = 2.25
USB_C_HOLE_RADIUS = 0.75
USB_C_HOLE_DEPTH = 4.8
USB_C_TONGUE_WIDTH = 6.2
USB_C_TONGUE_DEPTH = 4.2
USB_C_TONGUE_HEIGHT = 0.45
USB_C_TONGUE_RADIUS = 0.18
USB_C_TONGUE_Y_OFFSET = 1.8

# Micro-USB Type-B receptacle dimensions (mm) — Sunrom Part# 4653
MICRO_USB_SHELL_W = 7.40
MICRO_USB_SHELL_H = 2.45
MICRO_USB_SHELL_D = 5.47
MICRO_USB_WALL_THICK = 0.30
MICRO_USB_FRONT_LEG_PITCH = 7.15
MICRO_USB_FRONT_LEG_Y = 2.74
MICRO_USB_FRONT_LEG_W = 0.85
MICRO_USB_FRONT_LEG_THICK = 0.35
MICRO_USB_FRONT_LEG_DEPTH = 0.90
MICRO_USB_REAR_LEG_PITCH = 4.85
MICRO_USB_REAR_LEG_DEPTH = 0.70
MICRO_USB_CUTOUT_PITCH = 4.80
MICRO_USB_TONGUE_W = 3.45
MICRO_USB_TONGUE_THICK = 0.55
MICRO_USB_TONGUE_D = 3.80
MICRO_USB_PIN_PITCH = 0.65
MICRO_USB_PIN_WIDTH = 0.30
MICRO_USB_TOTAL_D = 6.09

# Mini-USB Type-B receptacle dimensions (mm)
MINI_USB_SHELL_W = 7.70
MINI_USB_SHELL_BOT_W = 6.70
MINI_USB_SHELL_H = 4.00
MINI_USB_SHELL_D = 7.85
MINI_USB_WALL_THICK = 0.30
MINI_USB_TAB_SPAN = 9.90
MINI_USB_TAB_W = 1.20
MINI_USB_TAB_Y1 = 3.05
MINI_USB_TAB_Y2 = 6.85
MINI_USB_PEG_DIST = 4.40
MINI_USB_PEG_Y = 6.05
MINI_USB_PEG_DIA = 0.70
MINI_USB_PEG_DEPTH = 1.00
MINI_USB_PIN_PITCH = 0.80
MINI_USB_PIN_WIDTH = 0.30
MINI_USB_TOTAL_D = 8.50


def _export_model(model: Compound, filename: str) -> Path:
    STEP_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = STEP_MODELS_DIR / filename
    export_step(model, str(output_path))
    return output_path


def _rounded_box_y(
    width: float,
    depth: float,
    height: float,
    radius: float,
    y_start: float = 0.0,
    z_center: float | None = None,
) -> Part:
    """Create a box with rounded corners in XZ, extruded along +Y.

    Centered in X around 0, spanning Y from `y_start` to `y_start + depth`,
    and Z centered at `z_center` (default `height / 2`, so Z in `[0, height]`).
    """
    zc = height / 2 if z_center is None else z_center
    # Plane.XZ has x_dir=+X, y_dir=+Z, z_dir=-Y, so offset(-y_start) puts the
    # sketch at Y = y_start and extrude(amount=-depth) extrudes along +Y.
    with BuildPart() as builder:
        with BuildSketch(Plane.XZ.offset(-y_start)), Locations((0, zc)):
            RectangleRounded(width, height, radius)
        extrude(amount=-depth)

    assert builder.part is not None
    return builder.part


def usb_c(export: bool = False) -> Compound:
    """Create a USB Type-C receptacle 3D model.

    Coordinate convention:
    - Centered in X (`[-4.4, +4.4]`).
    - Front mating opening at `Y = 0` facing `-Y`, body extending along `+Y`
      to `Y = 7.4`.
    - Bottom surface resting on `Z = 0`, top at `Z = 3.2`.

    Args:
        export: When True, exports `./stepModels/USB_C_Receptacle.step`.

    Returns:
        A `Compound` containing the metallic shell and internal contact tongue.
    """
    with BuildPart() as shell_builder:
        with BuildSketch(Plane.XZ), Locations((0, USB_C_HEIGHT / 2)):
            RectangleRounded(USB_C_WIDTH, USB_C_HEIGHT, USB_C_OUTER_RADIUS)
        extrude(amount=-USB_C_DEPTH)

        with (
            BuildSketch(Plane.XZ.offset(0.01)),
            Locations((0, USB_C_HEIGHT / 2)),
        ):
            RectangleRounded(
                USB_C_HOLE_WIDTH,
                USB_C_HOLE_HEIGHT,
                USB_C_HOLE_RADIUS,
            )
        extrude(amount=-USB_C_HOLE_DEPTH, mode=Mode.SUBTRACT)

    assert shell_builder.part is not None
    shell = shell_builder.part
    shell.color = SHELL_COLOR
    shell.label = "Shell"

    tongue = _rounded_box_y(
        width=USB_C_TONGUE_WIDTH,
        depth=USB_C_TONGUE_DEPTH,
        height=USB_C_TONGUE_HEIGHT,
        radius=USB_C_TONGUE_RADIUS,
        y_start=USB_C_TONGUE_Y_OFFSET,
        z_center=USB_C_HEIGHT / 2,
    )
    tongue.color = PLASTIC_COLOR
    tongue.label = "Tongue"

    model_name = "USB_C_Receptacle"
    model = Compound(children=[shell, tongue], label=model_name)

    if export:
        _export_model(model, f"{model_name}.step")

    return model


def _build_micro_usb_shell() -> Part:
    """Build the beveled metallic shell with through-hole legs and top cutouts."""
    w = MICRO_USB_SHELL_W
    h = MICRO_USB_SHELL_H
    d = MICRO_USB_SHELL_D
    wall = MICRO_USB_WALL_THICK
    bot_w = w - 1.5
    mid_h = h * 0.45

    outer_pts = [
        (-w / 2, h),
        (w / 2, h),
        (w / 2, mid_h),
        (bot_w / 2, 0.0),
        (-bot_w / 2, 0.0),
        (-w / 2, mid_h),
    ]
    inner_pts = [
        (-(w / 2 - wall), h - wall),
        (w / 2 - wall, h - wall),
        (w / 2 - wall, mid_h),
        (bot_w / 2 - wall, wall),
        (-(bot_w / 2 - wall), wall),
        (-(w / 2 - wall), mid_h),
    ]

    with BuildPart() as shell_builder:
        # Main beveled trapezoidal shell (Y in [0, d])
        with BuildSketch(Plane.XZ):
            Polygon(*outer_pts, align=None)
            Polygon(*inner_pts, align=None, mode=Mode.SUBTRACT)
        extrude(amount=-d)

        # Front through-hole support legs (7.15 mm pitch, 0.90 mm below PCB)
        leg_h = MICRO_USB_FRONT_LEG_DEPTH + h * 0.55
        for side in (-1, 1):
            x_leg = side * MICRO_USB_FRONT_LEG_PITCH / 2
            with Locations(
                (x_leg, MICRO_USB_FRONT_LEG_Y, -MICRO_USB_FRONT_LEG_DEPTH)
            ):
                Box(
                    MICRO_USB_FRONT_LEG_THICK,
                    MICRO_USB_FRONT_LEG_W,
                    leg_h,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                )

        # Rear through-hole support legs (4.85 mm pitch, 0.70 mm below PCB)
        rear_leg_h = MICRO_USB_REAR_LEG_DEPTH + h * 0.55
        for side in (-1, 1):
            x_rear = side * MICRO_USB_REAR_LEG_PITCH / 2
            with Locations(
                (x_rear, d - wall / 2, -MICRO_USB_REAR_LEG_DEPTH)
            ):
                Box(
                    MICRO_USB_FRONT_LEG_THICK,
                    0.60,
                    rear_leg_h,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                )

        # Two top locking cutouts (4.80 mm pitch)
        for side in (-1, 1):
            x_cut = side * MICRO_USB_CUTOUT_PITCH / 2
            with Locations((x_cut, 1.80, h - wall - 0.05)):
                Box(
                    0.90,
                    1.10,
                    wall + 0.15,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )

    assert shell_builder.part is not None
    shell = shell_builder.part
    shell.color = SHELL_COLOR
    shell.label = "Shell"
    return shell


def _build_micro_usb_housing() -> Part:
    """Build the internal black plastic housing and central contact tongue."""
    w = MICRO_USB_SHELL_W
    h = MICRO_USB_SHELL_H
    d = MICRO_USB_SHELL_D
    wall = MICRO_USB_WALL_THICK

    with BuildPart() as housing_builder:
        # Rear base housing block
        with Locations((0.0, d - 1.2, wall)):
            Box(
                w - 2 * wall - 0.3,
                1.2,
                h - 2 * wall,
                align=(Align.CENTER, Align.MIN, Align.MIN),
            )

        # Central contact tongue
        with Locations((0.0, d - 1.2 - MICRO_USB_TONGUE_D, 1.05)):
            Box(
                MICRO_USB_TONGUE_W,
                MICRO_USB_TONGUE_D,
                MICRO_USB_TONGUE_THICK,
                align=(Align.CENTER, Align.MIN, Align.MIN),
            )

    assert housing_builder.part is not None
    housing = housing_builder.part
    housing.color = PLASTIC_COLOR
    housing.label = "Housing"
    return housing


def _build_micro_usb_contacts() -> Compound:
    """Build the 5 gold-plated signal/power contacts and rear SMT solder tails."""
    d = MICRO_USB_SHELL_D
    tail_len = MICRO_USB_TOTAL_D - d + 0.35
    pin_parts: list[Part] = []

    for i in range(-2, 3):
        x_pos = i * MICRO_USB_PIN_PITCH
        with BuildPart() as pin_builder:
            # Contact strip on top of mating tongue
            with Locations(
                (
                    x_pos,
                    d - 1.2 - MICRO_USB_TONGUE_D + 0.2,
                    1.05 + MICRO_USB_TONGUE_THICK,
                )
            ):
                Box(
                    MICRO_USB_PIN_WIDTH,
                    MICRO_USB_TONGUE_D - 0.4,
                    0.08,
                    align=(Align.CENTER, Align.MIN, Align.MIN),
                )
            # Rear SMT solder tail reaching Y = 6.09 mm on Z = 0
            with Locations((x_pos, MICRO_USB_TOTAL_D - tail_len, 0.0)):
                Box(
                    MICRO_USB_PIN_WIDTH,
                    tail_len,
                    0.25,
                    align=(Align.CENTER, Align.MIN, Align.MIN),
                )
        assert pin_builder.part is not None
        pin_parts.append(pin_builder.part)

    contacts = Compound(children=pin_parts, label="Contacts")
    contacts.color = GOLD_CONTACT_COLOR
    return contacts


def micro_usb(export: bool = False) -> Compound:
    """Create a Micro-USB Type-B receptacle 3D model (Sunrom 4653 footprint).

    Coordinate convention:
    - Centered in X (`X = 0`, shell width 7.40 mm, front leg pitch 7.15 mm).
    - Front mating opening at `Y = 0` facing `-Y`, shell extending along `+Y`
      to `Y = 5.47` (rear SMT solder tails to `Y = 6.09`).
    - Bottom of the shell resting on `Z = 0`, top at `Z = 2.45`, with front
      through-hole support legs (`0.90 mm` below `Z = 0` at `Y = 2.74`) and
      rear support legs (`4.85 mm` pitch, `0.70 mm` below `Z = 0`).

    Args:
        export: When True, exports `./stepModels/Micro_USB_B_Receptacle.step`.

    Returns:
        A `Compound` containing the shell, plastic housing, and gold contacts.
    """
    shell = _build_micro_usb_shell()
    housing = _build_micro_usb_housing()
    contacts = _build_micro_usb_contacts()

    model_name = "Micro_USB_B_Receptacle"
    model = Compound(children=[shell, housing, contacts], label=model_name)

    if export:
        _export_model(model, f"{model_name}.step")

    return model


def _build_mini_usb_shell() -> Part:
    """Build the stepped Mini-USB Type-B metallic shell with 4 SMT ground tabs."""
    w = MINI_USB_SHELL_W
    bot_w = MINI_USB_SHELL_BOT_W
    h = MINI_USB_SHELL_H
    d = MINI_USB_SHELL_D
    wall = MINI_USB_WALL_THICK
    step_z1 = 1.45
    step_z2 = 1.95

    outer_pts = [
        (-w / 2, h),
        (w / 2, h),
        (w / 2, step_z2),
        (bot_w / 2, step_z1),
        (bot_w / 2, 0.0),
        (-bot_w / 2, 0.0),
        (-bot_w / 2, step_z1),
        (-w / 2, step_z2),
    ]
    inner_pts = [
        (-(w / 2 - wall), h - wall),
        (w / 2 - wall, h - wall),
        (w / 2 - wall, step_z2 - 0.12),
        (bot_w / 2 - wall, step_z1 - 0.12),
        (bot_w / 2 - wall, wall),
        (-(bot_w / 2 - wall), wall),
        (-(bot_w / 2 - wall), step_z1 - 0.12),
        (-(w / 2 - wall), step_z2 - 0.12),
    ]

    with BuildPart() as shell_builder:
        # Hollow stepped shell body (Y in [0, d])
        with BuildSketch(Plane.XZ):
            Polygon(*outer_pts, align=None)
            Polygon(*inner_pts, align=None, mode=Mode.SUBTRACT)
        extrude(amount=-d)

        # 4 side SMT ground mounting tabs (total span 9.90 mm, Y = 3.05 & 6.85)
        tab_outer_x = MINI_USB_TAB_SPAN / 2
        tab_inner_x = bot_w / 2 - 0.1
        tab_len_x = tab_outer_x - tab_inner_x
        tab_center_x = (tab_inner_x + tab_outer_x) / 2
        for side in (-1, 1):
            for y_tab in (MINI_USB_TAB_Y1, MINI_USB_TAB_Y2):
                # Flat SMT foot resting on Z = 0
                with Locations((side * tab_center_x, y_tab, 0.0)):
                    Box(
                        tab_len_x,
                        MINI_USB_TAB_W,
                        wall,
                        align=(Align.CENTER, Align.CENTER, Align.MIN),
                    )
                # Vertical leg joining the side wall down to the foot
                with Locations((side * (bot_w / 2), y_tab, 0.0)):
                    Box(
                        wall,
                        MINI_USB_TAB_W,
                        step_z1 + 0.2,
                        align=(Align.CENTER, Align.CENTER, Align.MIN),
                    )

    assert shell_builder.part is not None
    shell = shell_builder.part
    shell.color = SHELL_COLOR
    shell.label = "Shell"
    return shell


def _build_mini_usb_housing() -> Part:
    """Build the internal black plastic housing, tongue, and locating pegs."""
    w = MINI_USB_SHELL_W
    h = MINI_USB_SHELL_H
    d = MINI_USB_SHELL_D
    wall = MINI_USB_WALL_THICK

    with BuildPart() as housing_builder:
        # Rear insulator base block inside the back of the shell
        with Locations((0.0, d - 1.65, wall)):
            Box(
                MINI_USB_SHELL_BOT_W - 2 * wall,
                1.65,
                h - 2 * wall,
                align=(Align.CENTER, Align.MIN, Align.MIN),
            )

        # Central horizontal contact tongue inside the mating cavity
        tongue_w = min(4.60, w - 2 * wall - 1.5)
        tongue_d = 4.80
        tongue_h = 0.90
        with Locations((0.0, d - 1.65 - tongue_d, 1.75)):
            Box(
                tongue_w,
                tongue_d,
                tongue_h,
                align=(Align.CENTER, Align.MIN, Align.MIN),
            )

        # Two bottom plastic locating pegs (Ø0.70 mm, 4.40 mm pitch, Y = 6.05)
        for x_peg in (-MINI_USB_PEG_DIST / 2, MINI_USB_PEG_DIST / 2):
            with Locations((x_peg, MINI_USB_PEG_Y, -MINI_USB_PEG_DEPTH)):
                Cylinder(
                    radius=MINI_USB_PEG_DIA / 2,
                    height=MINI_USB_PEG_DEPTH + wall,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                )

    assert housing_builder.part is not None
    housing = housing_builder.part
    housing.color = PLASTIC_COLOR
    housing.label = "Housing"
    return housing


def _build_mini_usb_contacts() -> Compound:
    """Build the 5 gold-plated signal/power contacts and rear SMT solder tails."""
    d = MINI_USB_SHELL_D
    tail_len = MINI_USB_TOTAL_D - d + 0.35
    pin_parts: list[Part] = []

    for i in range(-2, 3):
        x_pos = i * MINI_USB_PIN_PITCH
        with BuildPart() as pin_builder:
            # Contact strip on top of mating tongue
            with Locations((x_pos, d - 1.65 - 4.40, 2.65)):
                Box(
                    MINI_USB_PIN_WIDTH,
                    4.40,
                    0.10,
                    align=(Align.CENTER, Align.MIN, Align.MIN),
                )
            # Rear SMT solder tail extending to Y = 8.50 mm on Z = 0
            with Locations((x_pos, MINI_USB_TOTAL_D - tail_len, 0.0)):
                Box(
                    MINI_USB_PIN_WIDTH,
                    tail_len,
                    0.25,
                    align=(Align.CENTER, Align.MIN, Align.MIN),
                )
        assert pin_builder.part is not None
        pin_parts.append(pin_builder.part)

    contacts = Compound(children=pin_parts, label="Contacts")
    contacts.color = GOLD_CONTACT_COLOR
    return contacts


def mini_usb(export: bool = False) -> Compound:
    """Create a Mini-USB Type-B surface-mount receptacle 3D model.

    Coordinate convention:
    - Centered in X (`X = 0`, shell width 7.70 mm, mounting tab span 9.90 mm).
    - Front mating opening at `Y = 0` facing `-Y`, shell extending along `+Y`
      to `Y = 7.85` (rear SMT solder tails to `Y = 8.50`).
    - Bottom of the shell and SMT tabs resting on `Z = 0`, top at `Z = 4.00`,
      with two `Ø0.70 mm` locating pegs (`4.40 mm` pitch at `Y = 6.05`)
      extending `1.00 mm` into `Z < 0`.

    Args:
        export: When True, exports `./stepModels/Mini_USB_B_Receptacle.step`.

    Returns:
        A `Compound` containing the shell, plastic housing, and gold contacts.
    """
    shell = _build_mini_usb_shell()
    housing = _build_mini_usb_housing()
    contacts = _build_mini_usb_contacts()

    model_name = "Mini_USB_B_Receptacle"
    model = Compound(children=[shell, housing, contacts], label=model_name)

    if export:
        _export_model(model, f"{model_name}.step")

    return model


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate 3D STEP models for USB receptacles."
    )
    parser.add_argument(
        "connector",
        choices=("usb-c", "micro-usb", "mini-usb"),
        help="USB connector type to generate.",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export the generated model to ./stepModels/.",
    )
    args = parser.parse_args()

    if args.connector == "usb-c":
        usb_c(export=args.export)
    elif args.connector == "micro-usb":
        micro_usb(export=args.export)
    elif args.connector == "mini-usb":
        mini_usb(export=args.export)
