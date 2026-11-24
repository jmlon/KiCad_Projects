"""Parametric 3D models for IoT breakout modules composed of a PCB and pin headers."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Literal

from build123d import (
    Align,
    Box,
    BuildPart,
    BuildSketch,
    Color,
    Compound,
    Location,
    Locations,
    Plane,
    Shape,
    Text,
    export_step,
    extrude,
)

import common
from pcb import ColorSpec, module_pcb
from pinHeaders import (
    PLASTIC_COLOR as HEADER_PLASTIC_COLOR,
)
from pinHeaders import (
    TIN_PIN_COLOR,
    angled_male_pin_header,
    male_pin_header,
)
from usbConnectors import (
    MICRO_USB_FRONT_LEG_PITCH,
    MICRO_USB_FRONT_LEG_Y,
    MICRO_USB_REAR_LEG_PITCH,
    MICRO_USB_SHELL_D,
    MICRO_USB_WALL_THICK,
    MINI_USB_PEG_DIST,
    MINI_USB_PEG_Y,
    micro_usb,
    mini_usb,
    usb_c,
)

FtdiUsbType = Literal["mini", "micro", "usb-c", "mini-usb", "micro-usb"]

SILKSCREEN_COLOR = Color(0.95, 0.95, 0.93)
IC_BODY_COLOR = Color(0.12, 0.12, 0.13)
IC_MARKING_COLOR = Color(0.75, 0.75, 0.78)

STEP_MODELS_DIR = Path(__file__).resolve().parent / "stepModels"


def iot_module(
    name: str,
    pcb_width: float,
    pcb_length: float,
    pins_per_row: int,
    header_rows: Literal[1, 2] = 1,
    pcb_thickness: float = common.pcb_width_16,
    pcb_color: ColorSpec = "green",
    header_color: ColorSpec = "black",
    edge_offset: float = 1.5,
    row_spacing: float | None = None,
    corner_radius: float = 0.0,
    export: bool = False,
) -> Compound:
    """Compose a rectangular IoT breakout module from a PCB and 1 or 2 pin headers.

    Pin 1 of the first header row is at `(X=0, Y=0, Z=0)` where `Z=0` is the
    bottom of the pin header insulator (top of a mating female socket or
    carrier PCB). Each male header is oriented with its 5.7 mm mating posts
    pointing downward (`Z < 0`) and its 3.0 mm solder tails passing upward
    through the module PCB (`Z = 2.5 .. 2.5 + pcb_thickness`).

    Args:
        name: Module name (also used as the STEP file stem when exporting).
        pcb_width: PCB dimension along X (parallel to the header row) in mm.
        pcb_length: PCB dimension along Y in mm.
        pins_per_row: Number of pins per header row.
        header_rows: Number of parallel single-row headers (`1` or `2`).
        pcb_thickness: PCB thickness in mm (default: `common.pcb_width_16`).
        pcb_color: PCB solder-mask color (default: `"green"`).
        header_color: Pin header insulator color (default: `"black"`).
        edge_offset: Distance from the PCB near edge to row 1 pin centers in mm.
        row_spacing: Center-to-center Y spacing between rows when
            `header_rows == 2` (default: `pcb_length - 2 * edge_offset`).
        corner_radius: Optional PCB corner fillet radius in mm.
        export: When True, exports `./stepModels/{name}.step`.

    Returns:
        A `Compound` containing the PCB and pin header(s).
    """
    if header_rows not in (1, 2):
        raise ValueError(f"header_rows must be 1 or 2, got {header_rows}")

    pitch = common.male_pin_pitch
    ins_height = common.male_pin_insulation_height

    pin_center_x = (pins_per_row - 1) * pitch / 2
    pcb_center_x = pin_center_x
    pcb_center_y = pcb_length / 2 - edge_offset

    if header_rows == 1:
        row_y_positions = [0.0]
    else:
        spacing = (
            row_spacing
            if row_spacing is not None
            else pcb_length - 2 * edge_offset
        )
        if spacing <= 0:
            raise ValueError(f"row_spacing must be > 0, got {spacing}")
        row_y_positions = [0.0, spacing]

    hole_diameter = common.female_solder_hole_diameter
    holes = [
        (i * pitch - pcb_center_x, y_row - pcb_center_y, hole_diameter)
        for y_row in row_y_positions
        for i in range(pins_per_row)
    ]

    board = module_pcb(
        width=pcb_width,
        length=pcb_length,
        thickness=pcb_thickness,
        color=pcb_color,
        corner_radius=corner_radius,
        holes=holes,
        name="PCB",
    ).moved(Location((pcb_center_x, pcb_center_y, ins_height)))

    base_header = male_pin_header(
        pins=pins_per_row,
        rows=1,
        color=header_color,
    )

    # Flip each header 180 deg around X so the insulator stays at Z=[0, 2.5],
    # the 3.0 mm solder tails pass upward through the PCB, and the 5.7 mm
    # mating pins point downward below Z=0.
    headers = []
    for idx, y_row in enumerate(row_y_positions, start=1):
        hdr = base_header.moved(Location((0, y_row, ins_height), (180, 0, 0)))
        hdr.label = f"PinHeader_{idx}" if header_rows == 2 else "PinHeader"
        headers.append(hdr)

    model = Compound(children=[board, *headers], label=name)

    if export:
        STEP_MODELS_DIR.mkdir(parents=True, exist_ok=True)
        export_step(model, str(STEP_MODELS_DIR / f"{name}.step"))

    return model


def bmp180(
    pcb_color: ColorSpec = "purple",
    header_color: ColorSpec = "black",
    export: bool = False,
) -> Compound:
    """Create a BMP180 (GY-68) pressure sensor breakout module.

    Composed of a 10.3 x 13.0 x 1.6 mm PCB and a 4-pin male header along the
    short (10.3 mm) edge.

    Args:
        pcb_color: PCB solder-mask color (default: `"purple"`).
        header_color: Pin header insulator color (default: `"black"`).
        export: When True, exports `./stepModels/BMP180.step`.

    Returns:
        A `Compound` representing the BMP180 module.
    """
    return iot_module(
        name="BMP180",
        pcb_width=10.3,
        pcb_length=13.0,
        pins_per_row=4,
        header_rows=1,
        pcb_thickness=common.pcb_width_16,
        pcb_color=pcb_color,
        header_color=header_color,
        export=export,
    )


def _build_pin_labels(
    labels: tuple[str, ...],
    pitch: float,
    y_start: float,
    z_top: float,
    font_size: float = 1.35,
    thickness: float = 0.08,
) -> Compound:
    """Build raised white silkscreen labels aligned with each pin along +X."""
    label_parts: list[Shape] = []
    for idx, text in enumerate(labels):
        with BuildPart() as text_builder:
            with BuildSketch(Plane.XY):
                Text(text, font_size=font_size, align=(Align.MIN, Align.CENTER))
            extrude(amount=thickness)
        assert text_builder.part is not None
        part = text_builder.part.moved(
            Location((idx * pitch, y_start, z_top), (0, 0, -90))
        )
        part.color = SILKSCREEN_COLOR
        part.label = f"Label_{text}"
        label_parts.append(part)

    labels_compound = Compound(children=label_parts, label="PinLabels")
    labels_compound.color = SILKSCREEN_COLOR
    return labels_compound


def _build_ft232rl_ic(center_x: float, center_y: float, z_top: float) -> Compound:
    """Build an SSOP-28 FT232RL IC package with gull-wing leads and marking."""
    body_w = 5.3
    body_l = 10.2
    body_h = 1.75
    standoff = 0.1
    lead_span = 7.8
    lead_pitch = 0.65
    leads_per_side = 14
    lead_w = 0.28
    lead_h = 0.22
    lead_len = (lead_span - body_w) / 2

    with (
        BuildPart() as body_builder,
        Locations((center_x, center_y, z_top + standoff)),
    ):
        Box(
            body_w,
            body_l,
            body_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        )
    assert body_builder.part is not None
    body = body_builder.part
    body.color = IC_BODY_COLOR
    body.label = "IC_Body"

    y_first = center_y - (leads_per_side - 1) * lead_pitch / 2
    lead_locations = [
        (
            center_x + side * (body_w / 2 + lead_len / 2),
            y_first + i * lead_pitch,
            z_top,
        )
        for side in (-1, 1)
        for i in range(leads_per_side)
    ]
    with BuildPart() as leads_builder, Locations(lead_locations):
        Box(
            lead_len + 0.2,
            lead_w,
            lead_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        )
    assert leads_builder.part is not None
    leads = leads_builder.part
    leads.color = TIN_PIN_COLOR
    leads.label = "IC_Leads"

    with BuildPart() as mark_builder:
        with BuildSketch(Plane.XY):
            Text("FT232RL", font_size=1.6, align=(Align.CENTER, Align.CENTER))
        extrude(amount=0.06)
    assert mark_builder.part is not None
    marking = mark_builder.part.moved(
        Location((center_x, center_y, z_top + standoff + body_h), (0, 0, -90))
    )
    marking.color = IC_MARKING_COLOR
    marking.label = "IC_Marking"

    return Compound(children=[body, leads, marking], label="FT232RL")


def ftdi(
    pcb_color: ColorSpec = "red",
    header_color: ColorSpec = "black",
    usb_connector: FtdiUsbType = "mini",
    export: bool = False,
) -> Compound:
    """Create an FTDI FT232RL USB-to-TTL serial breakout module.

    Composed of an `18.20 x 36.00 x 1.6 mm` PCB, a 1x6 right-angle (angled)
    male pin header (`GND`, `CTS`, `VCC`, `TXD`, `RXD`, `DTR`), silkscreen pin
    labels, a 3-pin 3.3V/5V voltage selector jumper with shunt, an FT232RL
    SSOP-28 IC, 2x9 side breakout holes, and a selectable USB receptacle
    (`mini`, `micro`, or `usb-c`) on the opposite short edge.

    Coordinate convention:
    - Pin 1 (`GND`) solder tail enters the PCB at `(X=0, Y=0)`.
    - Header pins step along `+X` by `2.54 mm` (`GND`, `CTS`, `VCC`, `TXD`,
      `RXD`, `DTR`), with the 90-degree bent mating pins extending along `+Y`.
    - Bottom of the PCB rests on `Z=0`, top at `Z=1.6 mm`.
    - The USB receptacle sits on top of the PCB at the `-Y` edge with its
      mating opening facing `-Y`.

    Args:
        pcb_color: PCB solder-mask color (default: `"red"`).
        header_color: Pin header insulator color (default: `"black"`).
        usb_connector: USB receptacle type: `"mini"` / `"mini-usb"` (default),
            `"micro"` / `"micro-usb"`, or `"usb-c"`.
        export: When True, exports `./stepModels/FTDI_<USB>.step`.

    Returns:
        A `Compound` representing the FTDI FT232RL module.
    """
    usb_key = usb_connector.strip().lower()
    if usb_key in ("mini", "mini-usb"):
        usb_kind = "mini"
        usb_label = "Mini_USB"
    elif usb_key in ("micro", "micro-usb"):
        usb_kind = "micro"
        usb_label = "Micro_USB"
    elif usb_key == "usb-c":
        usb_kind = "usb-c"
        usb_label = "USB_C"
    else:
        raise ValueError(
            f"Unsupported usb_connector {usb_connector!r}; "
            "expected 'mini', 'micro', or 'usb-c'."
        )

    pcb_width = 18.20
    pcb_length = 36.00
    pcb_thickness = common.pcb_width_16
    pitch = common.male_pin_pitch
    pin_labels = ("GND", "CTS", "VCC", "TXD", "RXD", "DTR")
    num_pins = len(pin_labels)

    pcb_center_x = (num_pins - 1) * pitch / 2  # 6.35 mm
    # Align PCB +Y edge flush with the outer face of the angled header insulator
    # (bend_clearance 1.5 + ins_depth 2.5 = 4.0 mm from solder tails at Y=0).
    pcb_y_max = 1.5 + common.male_pin_insulation_height  # 4.0 mm
    pcb_y_min = pcb_y_max - pcb_length  # -32.0 mm
    pcb_center_y = (pcb_y_min + pcb_y_max) / 2  # -14.0 mm
    z_top = pcb_thickness

    usb_overhang = 0.8
    usb_y_front = pcb_y_min - usb_overhang  # -32.8 mm

    jumper_y = -6.5
    jumper_x0 = pcb_center_x - pitch  # 3 pins centered at pcb_center_x

    # Collect through-holes (relative to PCB center)
    hole_dia = common.female_solder_hole_diameter
    holes: list[tuple[float, float, float]] = [
        # 1x6 angled header holes
        (i * pitch - pcb_center_x, 0.0 - pcb_center_y, hole_dia)
        for i in range(num_pins)
    ]
    # 3-pin voltage selector jumper holes
    holes.extend(
        (jumper_x0 + i * pitch - pcb_center_x, jumper_y - pcb_center_y, hole_dia)
        for i in range(3)
    )
    # 2x9 side breakout pads at 15.24 mm (0.6") row spacing
    side_x_offsets = (-7.62, 7.62)
    holes.extend(
        (sx, (-2.0 - k * pitch) - pcb_center_y, hole_dia)
        for sx in side_x_offsets
        for k in range(9)
    )
    # USB mounting/locating holes (when required by the connector)
    if usb_kind == "mini":
        peg_y_rel = (usb_y_front + MINI_USB_PEG_Y) - pcb_center_y
        holes.extend(
            (side * MINI_USB_PEG_DIST / 2, peg_y_rel, 0.85) for side in (-1, 1)
        )
    elif usb_kind == "micro":
        front_leg_y_rel = (usb_y_front + MICRO_USB_FRONT_LEG_Y) - pcb_center_y
        rear_leg_y_rel = (
            usb_y_front + MICRO_USB_SHELL_D - MICRO_USB_WALL_THICK / 2
        ) - pcb_center_y
        holes.extend(
            (side * MICRO_USB_FRONT_LEG_PITCH / 2, front_leg_y_rel, 0.95)
            for side in (-1, 1)
        )
        holes.extend(
            (side * MICRO_USB_REAR_LEG_PITCH / 2, rear_leg_y_rel, 0.75)
            for side in (-1, 1)
        )

    board = module_pcb(
        width=pcb_width,
        length=pcb_length,
        thickness=pcb_thickness,
        color=pcb_color,
        holes=holes,
        name="PCB",
    ).moved(Location((pcb_center_x, pcb_center_y, 0.0)))

    header = angled_male_pin_header(
        pins=num_pins,
        rows=1,
        color=header_color,
    ).moved(Location((0.0, 0.0, z_top)))
    header.label = "PinHeader"

    labels = _build_pin_labels(
        labels=pin_labels,
        pitch=pitch,
        y_start=-1.0,
        z_top=z_top,
    )

    # 3-pin 3.3V/5V voltage selector header + shunt cap
    jumper_hdr = male_pin_header(
        pins=3,
        rows=1,
        color=header_color,
    ).moved(Location((jumper_x0, jumper_y, z_top)))
    jumper_hdr.label = "JumperHeader"

    with (
        BuildPart() as shunt_builder,
        Locations(
            (
                pcb_center_x + pitch / 2,
                jumper_y,
                z_top + common.male_pin_insulation_height,
            )
        ),
    ):
        Box(
            2 * pitch,
            common.male_pin_insulation_width,
            5.8,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        )
    assert shunt_builder.part is not None
    shunt = shunt_builder.part
    shunt.color = HEADER_PLASTIC_COLOR
    shunt.label = "JumperShunt"

    voltage_jumper = Compound(
        children=[jumper_hdr, shunt], label="VoltageJumper"
    )

    ic = _build_ft232rl_ic(center_x=pcb_center_x, center_y=-14.5, z_top=z_top)

    if usb_kind == "mini":
        usb_base = mini_usb()
    elif usb_kind == "micro":
        usb_base = micro_usb()
    else:
        usb_base = usb_c()
    usb = usb_base.moved(Location((pcb_center_x, usb_y_front, z_top)))
    usb.label = usb_label

    name = f"FTDI_{usb_label}"
    model = Compound(
        children=[board, header, labels, voltage_jumper, ic, usb],
        label=name,
    )

    if export:
        STEP_MODELS_DIR.mkdir(parents=True, exist_ok=True)
        export_step(model, str(STEP_MODELS_DIR / f"{name}.step"))

    return model


def max98357a(
    pcb_color: ColorSpec = "purple",
    header_color: ColorSpec = "yellow",
    export: bool = False,
) -> Compound:
    """Create a MAX98357A I2S 3W Class-D mono amplifier breakout module.

    Composed of a `17.7 x 18.9 x 1.6 mm` rounded-corner PCB, a 1x7 vertical
    male pin header (`LRC`, `BCLK`, `DIN`, `GAIN`, `SD`, `GND`, `Vin`),
    two corner mounting holes, two speaker output terminal holes (`-` / `+`),
    a QFN-16 MAX98357A IC, and white silkscreen labels.

    Coordinate convention:
    - Pin 1 (`LRC`) is at `(X=0, Y=0, Z=0)` with `Z=0` at the bottom of the
      header insulator (top surface of the host/carrier PCB).
    - Header pins step along `+X` by `2.54 mm`, with 5.7 mm mating posts
      extending downward (`Z < 0`) and 3.0 mm solder tails passing upward
      through the PCB (`Z = 2.5 .. 4.1 mm`).

    Args:
        pcb_color: PCB solder-mask color (default: `"purple"`).
        header_color: Pin header insulator color (default: `"yellow"`).
        export: When True, exports `./stepModels/MAX98357A.step`.

    Returns:
        A `Compound` representing the MAX98357A breakout module.
    """
    pcb_width = 17.7
    pcb_length = 18.9
    pcb_thickness = common.pcb_width_16
    corner_radius = 1.5
    edge_offset = 2.0
    pitch = common.male_pin_pitch
    ins_height = common.male_pin_insulation_height

    pin_labels = ("LRC", "BCLK", "DIN", "GAIN", "SD", "GND", "Vin")
    num_pins = len(pin_labels)

    pcb_center_x = (num_pins - 1) * pitch / 2  # 7.62 mm
    pcb_center_y = pcb_length / 2 - edge_offset  # 7.45 mm
    z_top = ins_height + pcb_thickness  # 4.1 mm

    # Through-holes relative to PCB center
    hole_dia = common.female_solder_hole_diameter
    holes: list[tuple[float, float, float]] = [
        # 1x7 pin header holes along Y = 0
        (i * pitch - pcb_center_x, 0.0 - pcb_center_y, hole_dia)
        for i in range(num_pins)
    ]
    # Two top-corner mounting holes (Ø2.5 mm)
    holes.extend(
        (side * 6.35, 14.3 - pcb_center_y, 2.5) for side in (-1, 1)
    )
    # Two speaker output terminal holes (Ø1.5 mm, 3.5 mm pitch)
    holes.extend(
        (side * 1.75, 13.5 - pcb_center_y, 1.5) for side in (-1, 1)
    )

    board = module_pcb(
        width=pcb_width,
        length=pcb_length,
        thickness=pcb_thickness,
        color=pcb_color,
        corner_radius=corner_radius,
        holes=holes,
        name="PCB",
    ).moved(Location((pcb_center_x, pcb_center_y, ins_height)))

    header = male_pin_header(
        pins=num_pins,
        rows=1,
        color=header_color,
    ).moved(Location((0.0, 0.0, ins_height), (180, 0, 0)))
    header.label = "PinHeader"

    # MAX98357A QFN-16 IC (3.0 x 3.0 x 0.75 mm)
    with BuildPart() as ic_builder, Locations((pcb_center_x, 5.5, z_top)):
        Box(3.0, 3.0, 0.75, align=(Align.CENTER, Align.CENTER, Align.MIN))
    assert ic_builder.part is not None
    ic = ic_builder.part
    ic.color = IC_BODY_COLOR
    ic.label = "MAX98357A_IC"

    # Staggered white silkscreen pin labels + module title + speaker polarity
    silk_items: list[tuple[str, str, float, float, float]] = [
        (
            f"Label_{text}",
            text,
            idx * pitch,
            1.35 if idx % 2 == 0 else -1.35,
            0.95,
        )
        for idx, text in enumerate(pin_labels)
    ]
    silk_items.extend(
        [
            ("Label_Title", "MAX98357A", pcb_center_x, 9.5, 1.5),
            ("Label_Minus", "-", pcb_center_x - 3.9, 13.5, 1.6),
            ("Label_Plus", "+", pcb_center_x + 3.9, 13.5, 1.6),
        ]
    )

    label_parts: list[Shape] = []
    for part_label, text, lx, ly, fsize in silk_items:
        with BuildPart() as text_builder:
            with BuildSketch(Plane.XY):
                Text(text, font_size=fsize, align=(Align.CENTER, Align.CENTER))
            extrude(amount=0.08)
        assert text_builder.part is not None
        part = text_builder.part.moved(Location((lx, ly, z_top)))
        part.color = SILKSCREEN_COLOR
        part.label = part_label
        label_parts.append(part)

    labels = Compound(children=label_parts, label="Labels")
    labels.color = SILKSCREEN_COLOR

    name = "MAX98357A"
    model = Compound(children=[board, header, ic, labels], label=name)

    if export:
        STEP_MODELS_DIR.mkdir(parents=True, exist_ok=True)
        export_step(model, str(STEP_MODELS_DIR / f"{name}.step"))

    return model


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate 3D STEP models for IoT breakout modules."
    )
    parser.add_argument(
        "module",
        choices=("bmp180", "ftdi", "max98357a"),
        help="IoT module to generate.",
    )
    parser.add_argument(
        "--pcb-color",
        default=None,
        help=(
            "Override PCB solder-mask color (green, purple, blue, red, black, "
            "white, yellow, CSS color, or #RRGGBB)."
        ),
    )
    parser.add_argument(
        "--header-color",
        default=None,
        help="Override pin header plastic color (default depends on module).",
    )
    parser.add_argument(
        "--usb",
        choices=("mini", "micro", "usb-c"),
        default="mini",
        help="USB connector type for modules with USB (default: mini).",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export the generated model to ./stepModels/.",
    )
    args = parser.parse_args()

    if args.module == "bmp180":
        bmp180(
            pcb_color=args.pcb_color if args.pcb_color is not None else "purple",
            header_color=(
                args.header_color if args.header_color is not None else "black"
            ),
            export=args.export,
        )
    elif args.module == "ftdi":
        ftdi(
            pcb_color=args.pcb_color if args.pcb_color is not None else "red",
            header_color=(
                args.header_color if args.header_color is not None else "black"
            ),
            usb_connector=args.usb,
            export=args.export,
        )
    elif args.module == "max98357a":
        max98357a(
            pcb_color=args.pcb_color if args.pcb_color is not None else "purple",
            header_color=(
                args.header_color if args.header_color is not None else "yellow"
            ),
            export=args.export,
        )
