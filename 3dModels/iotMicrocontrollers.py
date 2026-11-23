"""3D models for commonly used IoT microcontrollers using build123d."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from build123d import (
    Align,
    Box,
    BuildPart,
    BuildSketch,
    Color,
    Compound,
    Cylinder,
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
from pinHeaders import TIN_PIN_COLOR, male_pin_header
from usbConnectors import PLASTIC_COLOR, SHELL_COLOR, micro_usb, mini_usb, usb_c

STEP_MODELS_DIR = Path(__file__).resolve().parent / "stepModels"

SILKSCREEN_COLOR = Color(0.95, 0.95, 0.93)
IC_BODY_COLOR = Color(0.12, 0.12, 0.13)
RED_LED_COLOR = Color(0.85, 0.12, 0.12)
BLUE_LED_COLOR = Color(0.12, 0.45, 0.90)

UsbType = Literal["usb-c", "micro-usb", "mini-usb", "none"]
BoardEdge = Literal["-x", "+x", "-y", "+y"]


def iot_microcontroller(
    name: str,
    pcb_width: float,
    pcb_length: float,
    pins_per_row: int,
    row_spacing: float,
    pin1_x_offset: float,
    pin1_y_offset: float,
    usb_connector: UsbType = "usb-c",
    usb_overhang: float = 1.4,
    usb_edge: BoardEdge = "-x",
    usb_offsets: Sequence[float] = (0.0,),
    pcb_thickness: float = common.pcb_width_16,
    pcb_color: ColorSpec = "green",
    header_color: ColorSpec = "black",
    corner_radius: float = 0.0,
    extra_holes: Sequence[tuple[float, float, float]] | None = None,
    extras: Sequence[Shape] | None = None,
    export: bool = False,
) -> Compound:
    """Compose a dual-row IoT microcontroller board from PCB, headers, and USB.

    Follows KiCad coordinate conventions:
    - Pin 1 of row 1 is at `(X=0, Y=0, Z=0)` with `Z=0` at the bottom of the
      header insulator (top surface of the host/carrier PCB).
    - Pins step along `+X` by `common.male_pin_pitch` and row 2 sits at
      `Y = row_spacing`.
    - Male headers are oriented with 5.7 mm mating posts extending downward
      (`Z < 0`) and 3.0 mm solder tails passing upward through the PCB
      (`Z = 2.5 .. 2.5 + pcb_thickness`).
    - The optional USB receptacle(s) are mounted on the top surface of the PCB
      (`Z = 2.5 + pcb_thickness`) along the selected edge.

    Args:
        name: Model name (and STEP filename stem when exporting).
        pcb_width: PCB dimension along X (parallel to header rows) in mm.
        pcb_length: PCB dimension along Y in mm.
        pins_per_row: Number of pins per header row.
        row_spacing: Center-to-center Y distance between the two header rows in mm.
        pin1_x_offset: Distance from the PCB `-X` edge to Pin 1 center in mm.
        pin1_y_offset: Distance from the PCB `-Y` edge to Row 1 pin centers in mm.
        usb_connector: USB receptacle type (`"usb-c"`, `"micro-usb"`, or `"none"`).
        usb_overhang: How far the USB connector protrudes past the PCB edge in mm.
        usb_edge: PCB edge where the USB connector is mounted (`"-x"`, `"+x"`,
            `"-y"`, or `"+y"`).
        usb_offsets: Offsets (in mm) along `usb_edge` relative to the PCB center
            for placing one or more USB receptacles (default: `(0.0,)`).
        pcb_thickness: PCB thickness in mm (default: `common.pcb_width_16`).
        pcb_color: PCB solder-mask color (default: `"green"`).
        header_color: Pin header insulator color (default: `"black"`).
        corner_radius: Optional PCB corner fillet radius in mm.
        extra_holes: Optional additional `(x, y, diameter)` through-holes in
            mm, relative to the PCB center (e.g., corner mounting holes).
        extras: Optional additional board-mounted shapes in world coordinates.
        export: When True, exports `./stepModels/{name}.step`.

    Returns:
        A `Compound` containing the PCB, both pin headers, optional USB
        connector(s), and any extra components.
    """
    if row_spacing <= 0:
        raise ValueError(f"row_spacing must be > 0, got {row_spacing}")

    pitch = common.male_pin_pitch
    ins_height = common.male_pin_insulation_height

    pcb_x_min = -pin1_x_offset
    pcb_x_max = pcb_x_min + pcb_width
    pcb_y_min = -pin1_y_offset
    pcb_y_max = pcb_y_min + pcb_length
    pcb_center_x = (pcb_x_min + pcb_x_max) / 2
    pcb_center_y = (pcb_y_min + pcb_y_max) / 2

    row_y_positions = (0.0, row_spacing)
    hole_diameter = common.female_solder_hole_diameter
    holes = [
        (i * pitch - pcb_center_x, y_row - pcb_center_y, hole_diameter)
        for y_row in row_y_positions
        for i in range(pins_per_row)
    ]
    if extra_holes:
        holes.extend(extra_holes)

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

    headers: list[Compound] = []
    for idx, y_row in enumerate(row_y_positions, start=1):
        hdr = base_header.moved(Location((0, y_row, ins_height), (180, 0, 0)))
        hdr.label = f"PinHeader_{idx}"
        headers.append(hdr)

    children: list[Shape] = [board, *headers]

    if usb_connector != "none":
        if usb_connector == "usb-c":
            usb_model = usb_c()
            usb_base_label = "USB_C"
        elif usb_connector == "micro-usb":
            usb_model = micro_usb()
            usb_base_label = "Micro_USB"
        elif usb_connector == "mini-usb":
            usb_model = mini_usb()
            usb_base_label = "Mini_USB"
        else:
            raise ValueError(
                f"Unsupported usb_connector {usb_connector!r}; "
                "expected 'usb-c', 'micro-usb', 'mini-usb', or 'none'."
            )

        z_top = ins_height + pcb_thickness
        multi_usb = len(usb_offsets) > 1
        for idx, offset in enumerate(usb_offsets, start=1):
            if usb_edge == "-x":
                usb_loc = Location(
                    (pcb_x_min - usb_overhang, pcb_center_y + offset, z_top),
                    (0, 0, -90),
                )
            elif usb_edge == "+x":
                usb_loc = Location(
                    (pcb_x_max + usb_overhang, pcb_center_y + offset, z_top),
                    (0, 0, 90),
                )
            elif usb_edge == "-y":
                usb_loc = Location(
                    (pcb_center_x + offset, pcb_y_min - usb_overhang, z_top),
                    (0, 0, 0),
                )
            elif usb_edge == "+y":
                usb_loc = Location(
                    (pcb_center_x + offset, pcb_y_max + usb_overhang, z_top),
                    (0, 0, 180),
                )
            else:
                raise ValueError(
                    f"Unsupported usb_edge {usb_edge!r}; "
                    "expected '-x', '+x', '-y', or '+y'."
                )

            positioned_usb = usb_model.moved(usb_loc)
            positioned_usb.label = (
                f"{usb_base_label}_{idx}" if multi_usb else usb_base_label
            )
            children.append(positioned_usb)

    if extras:
        children.extend(extras)

    model = Compound(children=children, label=name)

    if export:
        STEP_MODELS_DIR.mkdir(parents=True, exist_ok=True)
        export_step(model, str(STEP_MODELS_DIR / f"{name}.step"))

    return model


def esp32_c3(
    pcb_color: ColorSpec = "green",
    header_color: ColorSpec = "black",
    export: bool = False,
) -> Compound:
    """Create an ESP32-C3 (SuperMini) microcontroller board 3D model.

    Composed of a `22.8 x 18.0 x 1.6 mm` PCB, two parallel 1x8 male pin headers
    (2.54 mm pitch, 15.10 mm row spacing), white silkscreen pin labels along
    both rows, and a USB-C receptacle on the `-X` short edge overhanging by
    1.4 mm.

    Coordinate convention (KiCad standard):
    - Pin 1 of Row 1 (`5`) is at `(X=0, Y=0, Z=0)`; pins step along `+X`
      (`5`, `6`, `7`, `8`, `9`, `10`, `20`, `21`).
    - Row 2 sits at `Y = 15.10 mm` (`5V`, `GND`, `3V3`, `4`, `3`, `2`, `1`,
      `0`).
    - USB-C faces `-X`.

    Args:
        pcb_color: PCB solder-mask color (default: `"green"`).
        header_color: Pin header insulator color (default: `"black"`).
        export: When True, exports `./stepModels/ESP32-C3.step`.

    Returns:
        A `Compound` representing the ESP32-C3 microcontroller board.
    """
    pcb_x = 22.8
    pcb_y = 18.0
    pcb_thickness = common.pcb_width_16
    pitch = common.male_pin_pitch
    pin_count = 8
    support_x = 0.85
    support_y = 0.15
    support_w = 20.4
    support_h = 2.6

    pin1_x_offset = support_x + (support_w - (pin_count - 1) * pitch) / 2
    pin1_y_offset = support_y + support_h / 2
    row_spacing = pcb_y - 2 * pin1_y_offset
    z_top = common.male_pin_insulation_height + pcb_thickness

    row1_labels = ("5", "6", "7", "8", "9", "10", "20", "21")
    row2_labels = ("5V", "GND", "3V3", "4", "3", "2", "1", "0")
    pin_labels_row1 = _build_row_pin_labels(
        labels=row1_labels,
        pitch=pitch,
        y_pos=1.95,
        z_top=z_top,
        group_label="PinLabels_Row1",
        font_size=0.90,
    )
    pin_labels_row2 = _build_row_pin_labels(
        labels=row2_labels,
        pitch=pitch,
        y_pos=row_spacing - 1.95,
        z_top=z_top,
        group_label="PinLabels_Row2",
        font_size=0.90,
    )

    return iot_microcontroller(
        name="ESP32-C3",
        pcb_width=pcb_x,
        pcb_length=pcb_y,
        pins_per_row=pin_count,
        row_spacing=row_spacing,
        pin1_x_offset=pin1_x_offset,
        pin1_y_offset=pin1_y_offset,
        usb_connector="usb-c",
        usb_overhang=1.4,
        usb_edge="-x",
        pcb_thickness=pcb_thickness,
        pcb_color=pcb_color,
        header_color=header_color,
        extras=(pin_labels_row1, pin_labels_row2),
        export=export,
    )


def esp32_s3(
    pcb_color: ColorSpec = "green",
    header_color: ColorSpec = "yellow",
    export: bool = False,
) -> Compound:
    """Create an ESP32-S3 DevKit-style microcontroller board 3D model.

    Composed of a `57.5 x 28.6 x 1.6 mm` PCB, two parallel 1x22 male pin
    headers (2.54 mm pitch, 25.80 mm row spacing), white silkscreen short pin
    labels along both rows, dual USB-C receptacles on the `-X` edge, and the
    ESP32-S3 RF module (antenna substrate overhanging 7.0 mm past `+X`,
    metallic shield can, and embossed `"ESP32-S3"` label).

    Coordinate convention (KiCad standard):
    - Pin 1 of Row 1 (`G`) is at `(X=0, Y=0, Z=0)`; pins step along `+X`
      (`G`, `G`, `19`, `20`, ..., `TX`, `G`).
    - Row 2 sits at `Y = 25.80 mm` (`G`, `5V`, `14`, `13`, ..., `3V3`, `3V3`).
    - Dual USB-C receptacles face `-X` and the RF module sits at `+X`.

    Args:
        pcb_color: PCB solder-mask color (default: `"green"`).
        header_color: Pin header insulator color (default: `"yellow"`).
        export: When True, exports `./stepModels/ESP32-S3.step`.

    Returns:
        A `Compound` representing the ESP32-S3 microcontroller board.
    """
    pcb_x = 57.5
    pcb_y = 28.6
    pcb_thickness = common.pcb_width_16
    pitch = common.male_pin_pitch
    pin_count = 22
    support_x = 0.85
    support_y = 0.15
    support_w = 55.8
    support_h = 2.5

    antenna_x = 25.2
    antenna_y = 18.0
    antenna_z = 0.8
    antenna_overhang = 7.0

    module_x = 17.5
    module_y = 15.9
    module_z = 2.5

    pin1_x_offset = support_x + (support_w - (pin_count - 1) * pitch) / 2
    pin1_y_offset = support_y + support_h / 2
    row_spacing = pcb_y - 2 * pin1_y_offset

    pcb_x_min = -pin1_x_offset
    pcb_y_min = -pin1_y_offset
    z_top = common.male_pin_insulation_height + pcb_thickness

    row1_labels = (
        "G", "G", "19", "20", "21", "47", "48", "45", "0", "35", "36",
        "37", "38", "39", "40", "41", "42", "2", "1", "RX", "TX", "G",
    )
    row2_labels = (
        "G", "5V", "14", "13", "12", "11", "10", "9", "46", "3", "8",
        "18", "17", "16", "15", "7", "6", "5", "4", "RST", "3V3", "3V3",
    )
    pin_labels_row1 = _build_row_pin_labels(
        labels=row1_labels,
        pitch=pitch,
        y_pos=1.15,
        z_top=z_top,
        group_label="PinLabels_Row1",
        font_size=0.85,
    )
    pin_labels_row2 = _build_row_pin_labels(
        labels=row2_labels,
        pitch=pitch,
        y_pos=row_spacing - 1.15,
        z_top=z_top,
        group_label="PinLabels_Row2",
        font_size=0.85,
    )

    # RF module antenna substrate (black)
    with (
        BuildPart() as antenna_builder,
        Locations(
            (
                pcb_x_min + pcb_x - antenna_x + antenna_overhang,
                pcb_y_min + (pcb_y - antenna_y) / 2,
                z_top,
            )
        ),
    ):
        Box(
            antenna_x,
            antenna_y,
            antenna_z,
            align=(Align.MIN, Align.MIN, Align.MIN),
        )
    assert antenna_builder.part is not None
    antenna = antenna_builder.part
    antenna.color = PLASTIC_COLOR
    antenna.label = "Antenna"

    # RF metallic shield can (silver)
    with (
        BuildPart() as shield_builder,
        Locations(
            (
                pcb_x_min + pcb_x - module_x,
                pcb_y_min + (pcb_y - module_y) / 2,
                z_top + antenna_z,
            )
        ),
    ):
        Box(
            module_x,
            module_y,
            module_z,
            align=(Align.MIN, Align.MIN, Align.MIN),
        )
    assert shield_builder.part is not None
    shield = shield_builder.part
    shield.color = SHELL_COLOR
    shield.label = "RFShield"

    # Embossed "ESP32-S3" text on top of the RF shield
    with BuildPart() as label_builder:
        with BuildSketch(Plane.XY):
            Text("ESP32-S3", font_size=2.0, align=(Align.MIN, Align.MIN))
        extrude(amount=0.1)
    assert label_builder.part is not None
    label = label_builder.part.moved(
        Location(
            (
                pcb_x_min + pcb_x - 3.0,
                pcb_y_min + (pcb_y - module_y) / 2 + 14.0,
                z_top + antenna_z + module_z,
            ),
            (0, 0, -90),
        )
    )
    label.color = PLASTIC_COLOR
    label.label = "Label"

    usb_offsets = (
        (pcb_y - 21.1) - pcb_y / 2,
        (pcb_y - 7.7) - pcb_y / 2,
    )

    return iot_microcontroller(
        name="ESP32-S3",
        pcb_width=pcb_x,
        pcb_length=pcb_y,
        pins_per_row=pin_count,
        row_spacing=row_spacing,
        pin1_x_offset=pin1_x_offset,
        pin1_y_offset=pin1_y_offset,
        usb_connector="usb-c",
        usb_overhang=0.0,
        usb_edge="-x",
        usb_offsets=usb_offsets,
        pcb_thickness=pcb_thickness,
        pcb_color=pcb_color,
        header_color=header_color,
        extras=(pin_labels_row1, pin_labels_row2, antenna, shield, label),
        export=export,
    )


def esp8266(
    pcb_color: ColorSpec = "green",
    header_color: ColorSpec = "black",
    export: bool = False,
) -> Compound:
    """Create an ESP8266 (NodeMCU-style) microcontroller board 3D model.

    Composed of a `48.6 x 25.5 x 1.6 mm` PCB, two parallel 1x15 male pin
    headers (2.54 mm pitch, 22.70 mm row spacing, centered along X), and a
    Micro-USB Type-B receptacle flush with the `-X` edge.

    Args:
        pcb_color: PCB solder-mask color (default: `"green"`).
        header_color: Pin header insulator color (default: `"black"`).
        export: When True, exports `./stepModels/ESP8266.step`.

    Returns:
        A `Compound` representing the ESP8266 microcontroller board.
    """
    pcb_x = 48.6
    pcb_y = 25.5
    pin_count = 15
    support_w = 38.0
    support_h = 2.5
    support_x = (pcb_x - support_w) / 2
    support_y = 0.15

    pin1_x_offset = (
        support_x + (support_w - (pin_count - 1) * common.male_pin_pitch) / 2
    )
    pin1_y_offset = support_y + support_h / 2
    row_spacing = pcb_y - 2 * pin1_y_offset

    return iot_microcontroller(
        name="ESP8266",
        pcb_width=pcb_x,
        pcb_length=pcb_y,
        pins_per_row=pin_count,
        row_spacing=row_spacing,
        pin1_x_offset=pin1_x_offset,
        pin1_y_offset=pin1_y_offset,
        usb_connector="micro-usb",
        usb_overhang=0.0,
        usb_edge="-x",
        pcb_thickness=common.pcb_width_16,
        pcb_color=pcb_color,
        header_color=header_color,
        export=export,
    )


def _build_row_pin_labels(
    labels: tuple[str, ...],
    pitch: float,
    y_pos: float,
    z_top: float,
    group_label: str,
    font_size: float = 0.95,
    thickness: float = 0.08,
) -> Compound:
    """Build raised white silkscreen labels aligned with a pin row along +X."""
    label_parts: list[Shape] = []
    for idx, text in enumerate(labels):
        with BuildPart() as text_builder:
            with BuildSketch(Plane.XY):
                Text(text, font_size=font_size, align=(Align.CENTER, Align.CENTER))
            extrude(amount=thickness)
        assert text_builder.part is not None
        part = text_builder.part.moved(Location((idx * pitch, y_pos, z_top)))
        part.color = SILKSCREEN_COLOR
        part.label = f"Label_{idx + 1:02d}_{text}"
        label_parts.append(part)

    labels_compound = Compound(children=label_parts, label=group_label)
    labels_compound.color = SILKSCREEN_COLOR
    return labels_compound


def _build_tactile_button(
    center_x: float,
    center_y: float,
    z_top: float,
    name: str,
) -> Compound:
    """Build a small SMD tactile pushbutton (e.g. EN / BOOT)."""
    body_x = 3.4
    body_y = 4.2
    body_h = 1.4
    btn_dia = 1.8
    btn_h = 0.6

    with (
        BuildPart() as body_builder,
        Locations((center_x, center_y, z_top)),
    ):
        Box(
            body_x,
            body_y,
            body_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        )
    assert body_builder.part is not None
    body = body_builder.part
    body.color = SHELL_COLOR
    body.label = f"{name}_Body"

    with (
        BuildPart() as cap_builder,
        Locations((center_x, center_y, z_top + body_h)),
    ):
        Cylinder(
            radius=btn_dia / 2,
            height=btn_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        )
    assert cap_builder.part is not None
    cap = cap_builder.part
    cap.color = PLASTIC_COLOR
    cap.label = f"{name}_Cap"

    return Compound(children=[body, cap], label=name)


def esp32_devkit_v1_30_pin(
    pcb_color: ColorSpec = "black",
    header_color: ColorSpec = "black",
    export: bool = False,
) -> Compound:
    """Create an ESP32 DevKit V1 (30-pin, DOIT-style) microcontroller board.

    Composed of a `51.4 x 28.5 x 1.6 mm` rounded PCB with four corner mounting
    holes, two parallel 1x15 male pin headers (`2.54 mm` pitch, `25.4 mm` /
    1 in row spacing), white silkscreen pin labels along both rows, a USB-C
    receptacle on the `-X` edge flanked by `EN` and `BOOT` tactile buttons,
    `AMS1117` voltage regulator, `CP2102` USB-UART bridge, power/GPIO2 LEDs,
    and the `ESP-WROOM-32` RF module at the `+X` end.

    Coordinate convention (KiCad standard):
    - Pin 1 of Row 1 (`3V3`) is at `(X=0, Y=0, Z=0)`; pins step along `+X`
      (`3V3`, `GND`, `D15`, ..., `D23`).
    - Row 2 sits at `Y = 25.4 mm` (`VIN`, `GND`, `D13`, ..., `EN`).
    - USB-C faces `-X` and the ESP-WROOM-32 antenna sits near `+X`.

    Args:
        pcb_color: PCB solder-mask color (default: `"black"`).
        header_color: Pin header insulator color (default: `"black"`).
        export: When True, exports `./stepModels/ESP32_DevKit_V1_30_pin.step`.

    Returns:
        A `Compound` representing the ESP32 DevKit V1 (30-pin) board.
    """
    pcb_x = 51.4
    pcb_y = 28.5
    pcb_thickness = common.pcb_width_16
    pitch = common.male_pin_pitch
    pin_count = 15
    row_spacing = 25.4  # 1.0 in

    pin1_x_offset = 9.0
    pin1_y_offset = (pcb_y - row_spacing) / 2  # 1.55 mm

    pcb_x_min = -pin1_x_offset
    pcb_x_max = pcb_x_min + pcb_x
    pcb_y_min = -pin1_y_offset
    pcb_center_y = pcb_y_min + pcb_y / 2
    z_top = common.male_pin_insulation_height + pcb_thickness

    # Four corner mounting holes (relative to PCB center)
    hole_inset = 2.5
    mount_hole_dia = 2.8
    extra_holes = [
        (sx * (pcb_x / 2 - hole_inset), sy * (pcb_y / 2 - hole_inset), mount_hole_dia)
        for sx in (-1, 1)
        for sy in (-1, 1)
    ]

    # Pin silkscreen labels (inboard of each pin header row)
    row1_labels = (
        "3V3", "GND", "D15", "D2", "D4", "RX2", "TX2", "D5",
        "D18", "D19", "D21", "RX0", "TX0", "D22", "D23",
    )
    row2_labels = (
        "VIN", "GND", "D13", "D12", "D14", "D27", "D26", "D25",
        "D33", "D32", "D35", "D34", "VN", "VP", "EN",
    )
    pin_labels_row1 = _build_row_pin_labels(
        labels=row1_labels,
        pitch=pitch,
        y_pos=2.15,
        z_top=z_top,
        group_label="PinLabels_Row1",
    )
    pin_labels_row2 = _build_row_pin_labels(
        labels=row2_labels,
        pitch=pitch,
        y_pos=row_spacing - 2.15,
        z_top=z_top,
        group_label="PinLabels_Row2",
    )

    # ESP-WROOM-32 RF module substrate (black) & metallic shield can (silver)
    module_pcb_x = 25.5
    module_pcb_y = 18.0
    module_pcb_z = 0.8
    module_x_inset = 0.6
    module_x_min = pcb_x_max - module_x_inset - module_pcb_x

    shield_x = 18.0
    shield_y = 15.8
    shield_z = 2.4
    shield_x_min = module_x_min + 0.6

    with (
        BuildPart() as wroom_pcb_builder,
        Locations((module_x_min, pcb_center_y - module_pcb_y / 2, z_top)),
    ):
        Box(
            module_pcb_x,
            module_pcb_y,
            module_pcb_z,
            align=(Align.MIN, Align.MIN, Align.MIN),
        )
    assert wroom_pcb_builder.part is not None
    wroom_pcb = wroom_pcb_builder.part
    wroom_pcb.color = PLASTIC_COLOR
    wroom_pcb.label = "ESP_WROOM_32_PCB"

    with (
        BuildPart() as shield_builder,
        Locations(
            (shield_x_min, pcb_center_y - shield_y / 2, z_top + module_pcb_z)
        ),
    ):
        Box(
            shield_x,
            shield_y,
            shield_z,
            align=(Align.MIN, Align.MIN, Align.MIN),
        )
    assert shield_builder.part is not None
    shield = shield_builder.part
    shield.color = SHELL_COLOR
    shield.label = "RFShield"

    with BuildPart() as wroom_label_builder:
        with BuildSketch(Plane.XY):
            Text(
                "ESP-WROOM-32",
                font_size=1.6,
                align=(Align.CENTER, Align.CENTER),
            )
        extrude(amount=0.08)
    assert wroom_label_builder.part is not None
    wroom_label = wroom_label_builder.part.moved(
        Location(
            (
                shield_x_min + shield_x / 2,
                pcb_center_y,
                z_top + module_pcb_z + shield_z,
            ),
            (0, 0, -90),
        )
    )
    wroom_label.color = PLASTIC_COLOR
    wroom_label.label = "ESP_WROOM_32_Label"

    # EN (+Y) and BOOT (-Y) tactile switches flanking the USB-C connector
    btn_x = pcb_x_min + 4.2
    btn_en = _build_tactile_button(
        center_x=btn_x,
        center_y=pcb_center_y + 7.8,
        z_top=z_top,
        name="Button_EN",
    )
    btn_boot = _build_tactile_button(
        center_x=btn_x,
        center_y=pcb_center_y - 7.8,
        z_top=z_top,
        name="Button_BOOT",
    )

    # Silkscreen labels for EN and BOOT buttons
    button_label_parts: list[Shape] = []
    for text, y_off in (("EN", 5.1), ("BOOT", -5.1)):
        with BuildPart() as b_lbl:
            with BuildSketch(Plane.XY):
                Text(text, font_size=0.95, align=(Align.CENTER, Align.CENTER))
            extrude(amount=0.08)
        assert b_lbl.part is not None
        part = b_lbl.part.moved(
            Location((btn_x, pcb_center_y + y_off, z_top))
        )
        part.color = SILKSCREEN_COLOR
        part.label = f"Label_Button_{text}"
        button_label_parts.append(part)
    button_labels = Compound(children=button_label_parts, label="ButtonLabels")
    button_labels.color = SILKSCREEN_COLOR

    # AMS1117-3.3 voltage regulator (SOT-223, +Y side)
    reg_x = pcb_x_min + 13.0
    reg_y = pcb_center_y + 5.5
    with (
        BuildPart() as reg_body_builder,
        Locations((reg_x, reg_y, z_top)),
    ):
        Box(6.5, 3.5, 1.6, align=(Align.CENTER, Align.CENTER, Align.MIN))
    assert reg_body_builder.part is not None
    reg_body = reg_body_builder.part
    reg_body.color = IC_BODY_COLOR
    reg_body.label = "AMS1117_Body"

    with (
        BuildPart() as reg_tab_builder,
        Locations((reg_x, reg_y + 2.4, z_top)),
    ):
        Box(3.0, 1.4, 0.3, align=(Align.CENTER, Align.CENTER, Align.MIN))
    assert reg_tab_builder.part is not None
    reg_tab = reg_tab_builder.part
    reg_tab.color = TIN_PIN_COLOR
    reg_tab.label = "AMS1117_Tab"

    ams1117 = Compound(children=[reg_body, reg_tab], label="AMS1117")

    # CP2102 USB-to-UART bridge IC (QFN-28, -Y side)
    cp_x = pcb_x_min + 13.0
    cp_y = pcb_center_y - 5.2
    with (
        BuildPart() as cp_builder,
        Locations((cp_x, cp_y, z_top)),
    ):
        Box(5.0, 5.0, 0.85, align=(Align.CENTER, Align.CENTER, Align.MIN))
    assert cp_builder.part is not None
    cp2102 = cp_builder.part
    cp2102.color = IC_BODY_COLOR
    cp2102.label = "CP2102"

    # Power (red) and GPIO2 (blue) status LEDs
    led_x = pcb_x_min + 21.2
    with (
        BuildPart() as pwr_led_builder,
        Locations((led_x, pcb_center_y + 4.8, z_top)),
    ):
        Box(2.0, 1.25, 0.8, align=(Align.CENTER, Align.CENTER, Align.MIN))
    assert pwr_led_builder.part is not None
    pwr_led = pwr_led_builder.part
    pwr_led.color = RED_LED_COLOR
    pwr_led.label = "LED_Power"

    with (
        BuildPart() as gpio2_led_builder,
        Locations((led_x, pcb_center_y - 4.2, z_top)),
    ):
        Box(2.0, 1.25, 0.8, align=(Align.CENTER, Align.CENTER, Align.MIN))
    assert gpio2_led_builder.part is not None
    gpio2_led = gpio2_led_builder.part
    gpio2_led.color = BLUE_LED_COLOR
    gpio2_led.label = "LED_GPIO2"

    extras: tuple[Shape, ...] = (
        pin_labels_row1,
        pin_labels_row2,
        wroom_pcb,
        shield,
        wroom_label,
        btn_en,
        btn_boot,
        button_labels,
        ams1117,
        cp2102,
        pwr_led,
        gpio2_led,
    )

    return iot_microcontroller(
        name="ESP32_DevKit_V1_30_pin",
        pcb_width=pcb_x,
        pcb_length=pcb_y,
        pins_per_row=pin_count,
        row_spacing=row_spacing,
        pin1_x_offset=pin1_x_offset,
        pin1_y_offset=pin1_y_offset,
        usb_connector="usb-c",
        usb_overhang=0.8,
        usb_edge="-x",
        pcb_thickness=pcb_thickness,
        pcb_color=pcb_color,
        header_color=header_color,
        corner_radius=2.0,
        extra_holes=extra_holes,
        extras=extras,
        export=export,
    )


def esp32_devkitc_38_pin(
    pcb_color: ColorSpec = "black",
    header_color: ColorSpec = "black",
    export: bool = False,
) -> Compound:
    """Create an ESP32-DevKitC (38-pin) microcontroller board 3D model.

    Composed of a `54.7 x 28.5 x 1.6 mm` rounded PCB, two parallel 1x19 male
    pin headers (`2.54 mm` pitch, `25.4 mm` / 1 in row spacing), white
    silkscreen pin labels along both rows, a USB-C receptacle on the `-X` edge
    flanked by `RST` and `BOOT` tactile buttons, `AMS1117` voltage regulator,
    `CP2102` USB-UART bridge, status LED, and the `ESP-WROOM-32D` RF module at
    the `+X` end.

    Coordinate convention (KiCad standard):
    - Pin 1 of Row 1 (`CLK`) is at `(X=0, Y=0, Z=0)`; pins step along `+X`
      (`CLK`, `SD0`, `SD1`, `G15`, ..., `GND`).
    - Row 2 sits at `Y = 25.4 mm` (`V5`, `CMD`, `SD3`, `SD2`, ..., `3V3`).
    - USB-C faces `-X` and the ESP-WROOM-32D antenna sits near `+X`.

    Args:
        pcb_color: PCB solder-mask color (default: `"black"`).
        header_color: Pin header insulator color (default: `"black"`).
        export: When True, exports `./stepModels/ESP32-DevKitC-38_PIN.step`.

    Returns:
        A `Compound` representing the ESP32-DevKitC (38-pin) board.
    """
    pcb_x = 54.7
    pcb_y = 28.5
    pcb_thickness = common.pcb_width_16
    pitch = common.male_pin_pitch
    pin_count = 19
    row_spacing = 25.4  # 1.0 in

    pin1_x_offset = (pcb_x - (pin_count - 1) * pitch) / 2  # 4.49 mm
    pin1_y_offset = (pcb_y - row_spacing) / 2  # 1.55 mm

    pcb_x_min = -pin1_x_offset
    pcb_x_max = pcb_x_min + pcb_x
    pcb_y_min = -pin1_y_offset
    pcb_center_y = pcb_y_min + pcb_y / 2
    z_top = common.male_pin_insulation_height + pcb_thickness

    # Pin silkscreen labels (inboard of each pin header row)
    row1_labels = (
        "CLK", "SD0", "SD1", "G15", "G2", "G0", "G4", "G16", "G17", "G5",
        "G18", "G19", "GND", "G21", "RXD", "TXD", "G22", "G23", "GND",
    )
    row2_labels = (
        "V5", "CMD", "SD3", "SD2", "G13", "GND", "G12", "G14", "G27", "G26",
        "G25", "G33", "G32", "G35", "G34", "SN", "SP", "EN", "3V3",
    )
    pin_labels_row1 = _build_row_pin_labels(
        labels=row1_labels,
        pitch=pitch,
        y_pos=2.15,
        z_top=z_top,
        group_label="PinLabels_Row1",
    )
    pin_labels_row2 = _build_row_pin_labels(
        labels=row2_labels,
        pitch=pitch,
        y_pos=row_spacing - 2.15,
        z_top=z_top,
        group_label="PinLabels_Row2",
    )

    # ESP-WROOM-32D RF module substrate (black) & metallic shield can (silver)
    module_pcb_x = 25.5
    module_pcb_y = 18.0
    module_pcb_z = 0.8
    module_x_inset = 0.6
    module_x_min = pcb_x_max - module_x_inset - module_pcb_x

    shield_x = 18.0
    shield_y = 15.8
    shield_z = 2.4
    shield_x_min = module_x_min + 0.6

    with (
        BuildPart() as wroom_pcb_builder,
        Locations((module_x_min, pcb_center_y - module_pcb_y / 2, z_top)),
    ):
        Box(
            module_pcb_x,
            module_pcb_y,
            module_pcb_z,
            align=(Align.MIN, Align.MIN, Align.MIN),
        )
    assert wroom_pcb_builder.part is not None
    wroom_pcb = wroom_pcb_builder.part
    wroom_pcb.color = PLASTIC_COLOR
    wroom_pcb.label = "ESP_WROOM_32D_PCB"

    with (
        BuildPart() as shield_builder,
        Locations(
            (shield_x_min, pcb_center_y - shield_y / 2, z_top + module_pcb_z)
        ),
    ):
        Box(
            shield_x,
            shield_y,
            shield_z,
            align=(Align.MIN, Align.MIN, Align.MIN),
        )
    assert shield_builder.part is not None
    shield = shield_builder.part
    shield.color = SHELL_COLOR
    shield.label = "RFShield"

    with BuildPart() as wroom_label_builder:
        with BuildSketch(Plane.XY):
            Text(
                "ESP-WROOM-32D",
                font_size=1.5,
                align=(Align.CENTER, Align.CENTER),
            )
        extrude(amount=0.08)
    assert wroom_label_builder.part is not None
    wroom_label = wroom_label_builder.part.moved(
        Location(
            (
                shield_x_min + shield_x / 2,
                pcb_center_y,
                z_top + module_pcb_z + shield_z,
            ),
            (0, 0, -90),
        )
    )
    wroom_label.color = PLASTIC_COLOR
    wroom_label.label = "ESP_WROOM_32D_Label"

    # RST (+Y) and BOOT (-Y) tactile switches flanking the USB-C connector
    btn_x = pcb_x_min + 3.2
    btn_rst = _build_tactile_button(
        center_x=btn_x,
        center_y=pcb_center_y + 7.6,
        z_top=z_top,
        name="Button_RST",
    )
    btn_boot = _build_tactile_button(
        center_x=btn_x,
        center_y=pcb_center_y - 7.6,
        z_top=z_top,
        name="Button_BOOT",
    )

    # Silkscreen labels for RST and BOOT buttons
    button_label_parts: list[Shape] = []
    for text, y_off in (("RST", 5.0), ("BOOT", -5.0)):
        with BuildPart() as b_lbl:
            with BuildSketch(Plane.XY):
                Text(text, font_size=0.9, align=(Align.CENTER, Align.CENTER))
            extrude(amount=0.08)
        assert b_lbl.part is not None
        part = b_lbl.part.moved(
            Location((btn_x, pcb_center_y + y_off, z_top))
        )
        part.color = SILKSCREEN_COLOR
        part.label = f"Label_Button_{text}"
        button_label_parts.append(part)
    button_labels = Compound(children=button_label_parts, label="ButtonLabels")
    button_labels.color = SILKSCREEN_COLOR

    # AMS1117-3.3 voltage regulator (SOT-223, +Y side)
    reg_x = pcb_x_min + 11.5
    reg_y = pcb_center_y + 5.5
    with (
        BuildPart() as reg_body_builder,
        Locations((reg_x, reg_y, z_top)),
    ):
        Box(6.5, 3.5, 1.6, align=(Align.CENTER, Align.CENTER, Align.MIN))
    assert reg_body_builder.part is not None
    reg_body = reg_body_builder.part
    reg_body.color = IC_BODY_COLOR
    reg_body.label = "AMS1117_Body"

    with (
        BuildPart() as reg_tab_builder,
        Locations((reg_x, reg_y + 2.4, z_top)),
    ):
        Box(3.0, 1.4, 0.3, align=(Align.CENTER, Align.CENTER, Align.MIN))
    assert reg_tab_builder.part is not None
    reg_tab = reg_tab_builder.part
    reg_tab.color = TIN_PIN_COLOR
    reg_tab.label = "AMS1117_Tab"

    ams1117 = Compound(children=[reg_body, reg_tab], label="AMS1117")

    # CP2102 USB-to-UART bridge IC (QFN-28, -Y side)
    cp_x = pcb_x_min + 12.5
    cp_y = pcb_center_y - 3.0
    with (
        BuildPart() as cp_builder,
        Locations((cp_x, cp_y, z_top)),
    ):
        Box(5.0, 5.0, 0.85, align=(Align.CENTER, Align.CENTER, Align.MIN))
    assert cp_builder.part is not None
    cp2102 = cp_builder.part
    cp2102.color = IC_BODY_COLOR
    cp2102.label = "CP2102"

    # Power status LED (red)
    with (
        BuildPart() as pwr_led_builder,
        Locations((pcb_x_min + 19.0, pcb_center_y - 5.2, z_top)),
    ):
        Box(2.0, 1.25, 0.8, align=(Align.CENTER, Align.CENTER, Align.MIN))
    assert pwr_led_builder.part is not None
    pwr_led = pwr_led_builder.part
    pwr_led.color = RED_LED_COLOR
    pwr_led.label = "LED_Power"

    extras: tuple[Shape, ...] = (
        pin_labels_row1,
        pin_labels_row2,
        wroom_pcb,
        shield,
        wroom_label,
        btn_rst,
        btn_boot,
        button_labels,
        ams1117,
        cp2102,
        pwr_led,
    )

    return iot_microcontroller(
        name="ESP32-DevKitC-38_PIN",
        pcb_width=pcb_x,
        pcb_length=pcb_y,
        pins_per_row=pin_count,
        row_spacing=row_spacing,
        pin1_x_offset=pin1_x_offset,
        pin1_y_offset=pin1_y_offset,
        usb_connector="usb-c",
        usb_overhang=0.8,
        usb_edge="-x",
        pcb_thickness=pcb_thickness,
        pcb_color=pcb_color,
        header_color=header_color,
        corner_radius=2.5,
        extras=extras,
        export=export,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate 3D STEP models for IoT microcontrollers."
    )
    parser.add_argument(
        "board",
        choices=(
            "esp32-c3",
            "esp32-s3",
            "esp8266",
            "esp32-devkit-v1-30-pin",
            "esp32-devkitc-38-pin",
        ),
        help="IoT microcontroller board to generate.",
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
        help="Override pin header plastic color.",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export the generated model to ./stepModels/.",
    )
    args = parser.parse_args()

    if args.board == "esp32-c3":
        esp32_c3(
            pcb_color=args.pcb_color if args.pcb_color is not None else "green",
            header_color=(
                args.header_color if args.header_color is not None else "black"
            ),
            export=args.export,
        )
    elif args.board == "esp32-s3":
        esp32_s3(
            pcb_color=args.pcb_color if args.pcb_color is not None else "green",
            header_color=(
                args.header_color if args.header_color is not None else "yellow"
            ),
            export=args.export,
        )
    elif args.board == "esp8266":
        esp8266(
            pcb_color=args.pcb_color if args.pcb_color is not None else "green",
            header_color=(
                args.header_color if args.header_color is not None else "black"
            ),
            export=args.export,
        )
    elif args.board == "esp32-devkit-v1-30-pin":
        esp32_devkit_v1_30_pin(
            pcb_color=args.pcb_color if args.pcb_color is not None else "black",
            header_color=(
                args.header_color if args.header_color is not None else "black"
            ),
            export=args.export,
        )
    elif args.board == "esp32-devkitc-38-pin":
        esp32_devkitc_38_pin(
            pcb_color=args.pcb_color if args.pcb_color is not None else "black",
            header_color=(
                args.header_color if args.header_color is not None else "black"
            ),
            export=args.export,
        )
