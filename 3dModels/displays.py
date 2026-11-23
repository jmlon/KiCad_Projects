"""3D models for electronic display modules using build123d."""

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
    Location,
    Locations,
    Mode,
    Plane,
    Polygon,
    Text,
    export_step,
    extrude,
)

import common
from pcb import ColorSpec, module_pcb
from pinHeaders import TIN_PIN_COLOR, male_pin_header
from usbConnectors import SHELL_COLOR

STEP_MODELS_DIR = Path(__file__).resolve().parent / "stepModels"

BEZEL_COLOR = Color(0.10, 0.10, 0.11)
WHITE_FRAME_COLOR = Color(0.92, 0.92, 0.90)

SCREEN_COLORS: dict[str, Color] = {
    "blue": Color(0.08, 0.28, 0.68),
    "green": Color(0.48, 0.66, 0.22),
    "yellow-green": Color(0.55, 0.72, 0.18),
    "black": Color(0.08, 0.09, 0.10),
    "white": Color(0.86, 0.88, 0.90),
    "red": Color(0.68, 0.12, 0.12),
}


def _resolve_screen_color(color: ColorSpec) -> Color:
    """Resolve an LCD screen color specification into a `build123d.Color`."""
    if isinstance(color, Color):
        return color
    if isinstance(color, tuple):
        if len(color) != 3:
            raise ValueError(f"RGB color tuple must have 3 values, got {color}")
        return Color(*color)

    key = color.strip().lower()
    if key in SCREEN_COLORS:
        return SCREEN_COLORS[key]

    hex_str = key.lstrip("#")
    if len(hex_str) == 6 and all(c in "0123456789abcdef" for c in hex_str):
        rf = int(hex_str[0:2], 16) / 255.0
        gf = int(hex_str[2:4], 16) / 255.0
        bf = int(hex_str[4:6], 16) / 255.0
        return Color(rf, gf, bf)

    try:
        return Color(key)
    except ValueError as exc:
        valid = ", ".join(SCREEN_COLORS)
        raise ValueError(
            f"Unsupported screen color {color!r}. Use one of ({valid}), "
            "a CSS color name, a #RRGGBB hex string, an RGB tuple, or a Color."
        ) from exc


def character_lcd(
    name: str,
    pcb_width: float,
    pcb_length: float,
    hole_inset: float,
    hole_diameter: float,
    bezel_width: float,
    bezel_length: float,
    bezel_height: float,
    bezel_x_offset: float,
    bezel_y_offset: float,
    window_width: float,
    window_length: float,
    window_x_offset: float,
    window_y_offset: float,
    window_recess: float = 0.99,
    pcb_thickness: float = common.pcb_width_16,
    pcb_color: ColorSpec = "green",
    screen_color: ColorSpec = "blue",
    export: bool = False,
) -> Compound:
    """Create a character LCD module composed of PCB, corner holes, bezel, and screen.

    Coordinate convention:
    - Centered in XY around `(X=0, Y=0)`.
    - Bottom of the PCB rests on `Z=0`, top at `Z=pcb_thickness`.
    - `bezel_*_offset` and `window_*_offset` are measured from the PCB's
      `(-X, -Y)` corner.

    Args:
        name: Model name (and STEP filename stem when exporting).
        pcb_width: PCB dimension along X in mm.
        pcb_length: PCB dimension along Y in mm.
        hole_inset: Mounting hole center inset from all four PCB edges in mm.
        hole_diameter: Mounting hole diameter in mm.
        bezel_width: Bezel dimension along X in mm.
        bezel_length: Bezel dimension along Y in mm.
        bezel_height: Bezel height above the PCB top in mm.
        bezel_x_offset: Bezel `-X` offset from PCB `-X` edge in mm.
        bezel_y_offset: Bezel `-Y` offset from PCB `-Y` edge in mm.
        window_width: Viewing window width along X in mm.
        window_length: Viewing window length along Y in mm.
        window_x_offset: Viewing window `-X` offset from PCB `-X` edge in mm.
        window_y_offset: Viewing window `-Y` offset from PCB `-Y` edge in mm.
        window_recess: Depth of the viewing window recess into the bezel in mm.
        pcb_thickness: PCB thickness in mm (default: `common.pcb_width_16`).
        pcb_color: PCB solder-mask color (default: `"green"`).
        screen_color: LCD screen pane color (default: `"blue"`).
        export: When True, exports `./stepModels/{name}.step`.

    Returns:
        A `Compound` containing the PCB, bezel, and screen pane.
    """
    hx = pcb_width / 2 - hole_inset
    hy = pcb_length / 2 - hole_inset
    holes = [
        (-hx, -hy, hole_diameter),
        (-hx, hy, hole_diameter),
        (hx, -hy, hole_diameter),
        (hx, hy, hole_diameter),
    ]

    board = module_pcb(
        width=pcb_width,
        length=pcb_length,
        thickness=pcb_thickness,
        color=pcb_color,
        holes=holes,
        name="PCB",
    )

    bezel_x0 = bezel_x_offset - pcb_width / 2
    bezel_y0 = bezel_y_offset - pcb_length / 2
    win_x0 = window_x_offset - pcb_width / 2
    win_y0 = window_y_offset - pcb_length / 2
    win_z0 = pcb_thickness + bezel_height - window_recess

    with BuildPart() as bezel_builder:
        with Locations((bezel_x0, bezel_y0, pcb_thickness)):
            Box(
                bezel_width,
                bezel_length,
                bezel_height,
                align=(Align.MIN, Align.MIN, Align.MIN),
            )
        with Locations((win_x0, win_y0, win_z0)):
            Box(
                window_width,
                window_length,
                window_recess + 0.01,
                align=(Align.MIN, Align.MIN, Align.MIN),
                mode=Mode.SUBTRACT,
            )

    assert bezel_builder.part is not None
    bezel = bezel_builder.part
    bezel.color = BEZEL_COLOR
    bezel.label = "Bezel"

    screen_thickness = 0.1
    with (
        BuildPart() as screen_builder,
        Locations((win_x0, win_y0, win_z0)),
    ):
        Box(
            window_width,
            window_length,
            screen_thickness,
            align=(Align.MIN, Align.MIN, Align.MIN),
        )

    assert screen_builder.part is not None
    screen = screen_builder.part
    screen.color = _resolve_screen_color(screen_color)
    screen.label = "Screen"

    model = Compound(children=[board, bezel, screen], label=name)

    if export:
        STEP_MODELS_DIR.mkdir(parents=True, exist_ok=True)
        export_step(model, str(STEP_MODELS_DIR / f"{name}.step"))

    return model


def lcd1602(
    pcb_color: ColorSpec = "green",
    screen_color: ColorSpec = "blue",
    export: bool = False,
) -> Compound:
    """Create a 16x2 character LCD (1602) display module 3D model.

    Coordinate convention:
    - Centered in XY around `(X=0, Y=0)`.
    - Bottom of the `80.0 x 36.0 x 1.6 mm` PCB rests on `Z=0`, with 4 corner
      mounting holes (3.0 mm diameter) at `(±37.5, ±15.5)`.
    - Black LCD bezel (`71.4 x 23.8 x 7.4 mm`) rests on top of the PCB
      (`Z = 1.6 .. 9.0`) with a recessed `64.5 x 14.5 mm` viewing window and
      screen pane.

    Args:
        pcb_color: PCB solder-mask color (default: `"green"`).
        screen_color: LCD viewing area color (`"blue"`, `"green"`,
            `"yellow-green"`, `"black"`, `"white"`, `"red"`, CSS color,
            `#RRGGBB`, RGB tuple, or `Color`; default: `"blue"`).
        export: When True, exports `./stepModels/LCD1602.step`.

    Returns:
        A `Compound` containing the PCB, black bezel, and LCD screen pane.
    """
    return character_lcd(
        name="LCD1602",
        pcb_width=80.0,
        pcb_length=36.0,
        hole_inset=2.5,
        hole_diameter=3.0,
        bezel_width=71.4,
        bezel_length=23.8,
        bezel_height=7.4,
        bezel_x_offset=4.3,
        bezel_y_offset=5.8,
        window_width=64.5,
        window_length=14.5,
        window_x_offset=7.75,
        window_y_offset=10.45,
        window_recess=0.99,
        pcb_color=pcb_color,
        screen_color=screen_color,
        export=export,
    )


def lcd2004(
    pcb_color: ColorSpec = "green",
    screen_color: ColorSpec = "blue",
    export: bool = False,
) -> Compound:
    """Create a 20x4 character LCD (2004) display module 3D model.

    Coordinate convention:
    - Centered in XY around `(X=0, Y=0)`.
    - Bottom of the `98.0 x 60.0 x 1.6 mm` PCB rests on `Z=0`, with 4 corner
      mounting holes (3.0 mm diameter) at `(±46.5, ±27.5)`.
    - Black LCD bezel (`97.0 x 39.7 x 9.0 mm`) rests on top of the PCB
      (`Z = 1.6 .. 10.6`) with a recessed `76.0 x 26.0 mm` viewing window and
      screen pane.

    Args:
        pcb_color: PCB solder-mask color (default: `"green"`).
        screen_color: LCD viewing area color (`"blue"`, `"green"`,
            `"yellow-green"`, `"black"`, `"white"`, `"red"`, CSS color,
            `#RRGGBB`, RGB tuple, or `Color`; default: `"blue"`).
        export: When True, exports `./stepModels/LCD2004.step`.

    Returns:
        A `Compound` containing the PCB, black bezel, and LCD screen pane.
    """
    return character_lcd(
        name="LCD2004",
        pcb_width=98.0,
        pcb_length=60.0,
        hole_inset=2.5,
        hole_diameter=3.0,
        bezel_width=97.0,
        bezel_length=39.7,
        bezel_height=9.0,
        bezel_x_offset=0.5,
        bezel_y_offset=10.15,
        window_width=76.0,
        window_length=26.0,
        window_x_offset=11.0,
        window_y_offset=17.0,
        window_recess=0.99,
        pcb_color=pcb_color,
        screen_color=screen_color,
        export=export,
    )


def lcd12864(
    pcb_color: ColorSpec = "green",
    screen_color: ColorSpec = "blue",
    header_color: ColorSpec = "black",
    export: bool = False,
) -> Compound:
    """Create a 128x64 graphic LCD (12864) display module with 1x20 pin header.

    Follows KiCad breakout module conventions:
    - Leftmost pin (Pin 20, `BLK`) of the 1x20 male header sits at `(X=0, Y=0,
      Z=0)` (14.0 mm from the PCB `-X` edge, 2.5 mm from the `-Y` edge) with
      `Z=0` at the bottom of the header insulator (top of the carrier PCB).
    - The 20 header pins step along `+X` at 2.54 mm pitch (`BLK, BLA, VOUT,
      RST, NC, PSB, DB7..DB0, E, R/W, RS, V0, VCC, GND`), with 5.7 mm mating
      posts extending downward (`Z < 0`) and 3.0 mm solder tails passing upward
      through the `93.0 x 70.0 x 1.6 mm` PCB (`Z = 2.5 .. 4.1`).
    - Four `2.5 mm` corner mounting holes sit at `88.0 x 65.0 mm` pitch.
    - Black LCD bezel (`78.6 x 50.5 x 7.9 mm`) rests on top of the PCB
      (`Z = 4.1 .. 12.0`) with a recessed `72.0 x 40.0 mm` viewing window,
      screen pane, and white top silkscreen pin labels.

    Args:
        pcb_color: PCB solder-mask color (default: `"green"`).
        screen_color: LCD viewing area color (`"blue"`, `"green"`,
            `"yellow-green"`, `"black"`, `"white"`, `"red"`, CSS color,
            `#RRGGBB`, RGB tuple, or `Color`; default: `"blue"`).
        header_color: Pin header plastic color (default: `"black"`).
        export: When True, exports `./stepModels/LCD12864.step`.

    Returns:
        A `Compound` containing the PCB, black bezel, LCD screen pane, 1x20
        male pin header, and top silkscreen pin labels.
    """
    pcb_w = 93.0
    pcb_l = 70.0
    pcb_t = common.pcb_width_16
    pitch = common.male_pin_pitch
    ins_height = common.male_pin_insulation_height

    pin_count = 20
    # Pin 20 (BLK) sits 14.0 mm from -X edge, 2.5 mm from -Y edge
    pin0_u = 14.0
    pin0_v = 2.5

    pcb_x_min = -pin0_u
    pcb_y_min = -pin0_v
    pcb_center_x = pcb_x_min + pcb_w / 2
    pcb_center_y = pcb_y_min + pcb_l / 2
    z_top = ins_height + pcb_t

    hole_inset = 2.5
    hole_dia = 2.5
    pin_hole_dia = common.female_solder_hole_diameter
    hx = pcb_w / 2 - hole_inset
    hy = pcb_l / 2 - hole_inset
    holes: list[tuple[float, float, float]] = [
        (-hx, -hy, hole_dia),
        (-hx, hy, hole_dia),
        (hx, -hy, hole_dia),
        (hx, hy, hole_dia),
    ]
    for i in range(pin_count):
        holes.append(
            (pin0_u + i * pitch - pcb_w / 2, pin0_v - pcb_l / 2, pin_hole_dia)
        )

    board = module_pcb(
        width=pcb_w,
        length=pcb_l,
        thickness=pcb_t,
        color=pcb_color,
        holes=holes,
        name="PCB",
    ).moved(Location((pcb_center_x, pcb_center_y, ins_height)))

    header = male_pin_header(
        pins=pin_count, rows=1, color=header_color
    ).moved(Location((0, 0, ins_height), (180, 0, 0)))
    header.label = "PinHeader"

    bezel_w = 78.6
    bezel_l = 50.5
    bezel_h = 7.9
    bezel_x0 = pcb_x_min + 7.2
    bezel_y0 = pcb_y_min + 9.75

    win_w = 72.0
    win_l = 40.0
    win_recess = 0.99
    win_x0 = pcb_x_min + (pcb_w - win_w) / 2  # 10.5 mm
    win_y0 = pcb_y_min + (pcb_l - win_l) / 2  # 15.0 mm
    win_z0 = z_top + bezel_h - win_recess

    with BuildPart() as bezel_builder:
        with Locations((bezel_x0, bezel_y0, z_top)):
            Box(
                bezel_w,
                bezel_l,
                bezel_h,
                align=(Align.MIN, Align.MIN, Align.MIN),
            )
        with Locations((win_x0, win_y0, win_z0)):
            Box(
                win_w,
                win_l,
                win_recess + 0.01,
                align=(Align.MIN, Align.MIN, Align.MIN),
                mode=Mode.SUBTRACT,
            )

    assert bezel_builder.part is not None
    bezel = bezel_builder.part
    bezel.color = BEZEL_COLOR
    bezel.label = "Bezel"

    screen_thickness = 0.1
    with (
        BuildPart() as screen_builder,
        Locations((win_x0, win_y0, win_z0)),
    ):
        Box(
            win_w,
            win_l,
            screen_thickness,
            align=(Align.MIN, Align.MIN, Align.MIN),
        )

    assert screen_builder.part is not None
    screen = screen_builder.part
    screen.color = _resolve_screen_color(screen_color)
    screen.label = "Screen"

    # Top silkscreen pin labels between the 1x20 header and the bezel
    pin_labels = (
        "BLK",
        "BLA",
        "VOUT",
        "RST",
        "NC",
        "PSB",
        "DB7",
        "DB6",
        "DB5",
        "DB4",
        "DB3",
        "DB2",
        "DB1",
        "DB0",
        "E",
        "R/W",
        "RS",
        "V0",
        "VCC",
        "GND",
    )
    label_y = pcb_y_min + 6.4  # centered between pin row (2.5) and bezel (9.5)
    with BuildPart() as silk_builder:
        with BuildSketch(Plane.XY.offset(z_top)):
            for i, text_str in enumerate(pin_labels):
                with Locations(Location((i * pitch, label_y), -90)):
                    Text(
                        text_str,
                        font_size=1.3,
                        align=(Align.CENTER, Align.CENTER),
                    )
        extrude(amount=0.05)

    assert silk_builder.part is not None
    silkscreen = silk_builder.part
    silkscreen.color = WHITE_FRAME_COLOR
    silkscreen.label = "Silkscreen"

    model_name = "LCD12864"
    model = Compound(
        children=[board, bezel, screen, header, silkscreen],
        label=model_name,
    )

    if export:
        STEP_MODELS_DIR.mkdir(parents=True, exist_ok=True)
        export_step(model, str(STEP_MODELS_DIR / f"{model_name}.step"))

    return model


def _sd_card_slot() -> Compound:
    """Build a standard full-size SMT SD card reader socket.

    Local coordinate convention (designed to mount on the bottom of a PCB):
    - Centered in X (`X in [-13.25, +13.25]`, outer shell width 26.5 mm).
    - Front card insertion opening at `Y = 0` facing `-Y`, body extending
      along `+Y` to `Y = 20.0` (rear SMT pins to `Y = 21.5`).
    - Top mounting surface (against the PCB bottom) at `Z = 0`, body extending
      downward into `Z in [-2.8, 0.0]`.
    """
    shell_w = 26.5
    shell_d = 20.0
    shell_h = 2.8
    wall = 0.35
    chamfer_x = 3.2
    chamfer_y = 3.2

    # Outer footprint in XY with beveled rear-left (-X, +Y) corner
    outer_pts = [
        (-shell_w / 2, 0.0),
        (shell_w / 2, 0.0),
        (shell_w / 2, shell_d),
        (-shell_w / 2 + chamfer_x, shell_d),
        (-shell_w / 2, shell_d - chamfer_y),
    ]

    with BuildPart() as shell_builder:
        with BuildSketch(Plane.XY):
            Polygon(*outer_pts, align=None)
        extrude(amount=-shell_h)

        # Front card insertion cavity (24.0 mm wide x 2.1 mm tall)
        with Locations((0.0, -0.01, -shell_h + wall)):
            Box(
                24.0,
                shell_d - 2.0,
                2.1,
                align=(Align.CENTER, Align.MIN, Align.MIN),
                mode=Mode.SUBTRACT,
            )

        # 4 side SMT mounting tabs flush with PCB bottom (Z = -0.3 .. 0)
        for side in (-1, 1):
            x_tab = side * (shell_w / 2 + 0.9)
            for y_tab in (1.4, shell_d - 2.0):
                with Locations((x_tab, y_tab, -0.3)):
                    Box(
                        2.0,
                        2.2,
                        0.3,
                        align=(Align.CENTER, Align.CENTER, Align.MIN),
                    )

    assert shell_builder.part is not None
    shell = shell_builder.part
    shell.color = SHELL_COLOR
    shell.label = "SD_Shell"

    # 9 rear SMT signal/power solder pins
    pin_count = 9
    pin_pitch = 2.54
    pin_start_x = -(pin_count - 1) * pin_pitch / 2 + 1.0
    with BuildPart() as pins_builder:
        for i in range(pin_count):
            with Locations((pin_start_x + i * pin_pitch, shell_d, -0.3)):
                Box(
                    0.8,
                    1.5,
                    0.3,
                    align=(Align.CENTER, Align.MIN, Align.MIN),
                )

    assert pins_builder.part is not None
    sd_pins = pins_builder.part
    sd_pins.color = TIN_PIN_COLOR
    sd_pins.label = "SD_Contacts"

    return Compound(children=[shell, sd_pins], label="SDCardSlot")


def st7735s_128x160_sd(
    pcb_color: ColorSpec = "red",
    screen_color: ColorSpec = "black",
    header_color: ColorSpec = "black",
    export: bool = False,
) -> Compound:
    """Create an SPI ST7735S 1.8" TFT (128x160) display module with SD card reader.

    Follows KiCad breakout module conventions:
    - Pin 1 (`VCC`) of the 1x8 male header is at `(X=0, Y=0, Z=0)` with `Z=0`
      at the bottom of the header insulator (top of the carrier PCB).
    - The 8 header pins step along `+Y` at 2.54 mm pitch, with 5.7 mm mating
      posts extending downward (`Z < 0`) and 3.0 mm solder tails passing upward
      through the `58.0 x 34.2 x 1.6 mm` PCB (`Z = 2.5 .. 4.1`).
    - White TFT backlight frame (`43.7 x 34.1 x 2.59 mm`) and black TFT glass
      (`38.0 x 31.7 x 2.60 mm`) rest on top of the PCB (`Z = 4.1 .. 6.7`).
    - Full-size SD card reader (`26.5 x 20.0 x 2.8 mm`) is mounted on the
      bottom of the PCB (`Z = -0.3 .. 2.5`) with the card opening at the `-Y`
      edge.

    Args:
        pcb_color: PCB solder-mask color (default: `"red"`).
        screen_color: TFT screen surface color (default: `"black"`).
        header_color: Pin header plastic color (default: `"black"`).
        export: When True, exports
            `./stepModels/SPI-ST7735S-1.8-TFT-128x160-SD.step`.

    Returns:
        A `Compound` containing the PCB, white frame, TFT screen, 1x8 male pin
        header, and bottom-mounted SD card reader.
    """
    pcb_w = 58.0
    pcb_l = 34.2
    pcb_t = common.pcb_width_16
    pitch = common.male_pin_pitch
    ins_height = common.male_pin_insulation_height

    # Pin 1 (VCC) of the 1x8 header on the +X edge in local PCB coords (u, v)
    pin_count = 8
    pin1_u = pcb_w - 2.5  # 55.5 mm from -X edge
    pin1_v = (pcb_l - (pin_count - 1) * pitch) / 2  # 8.21 mm from -Y edge

    pcb_x_min = -pin1_u
    pcb_y_min = -pin1_v
    pcb_center_x = pcb_x_min + pcb_w / 2
    pcb_center_y = pcb_y_min + pcb_l / 2
    z_top = ins_height + pcb_t

    # 4 corner mounting holes (3.0 mm) + 8 header holes + 4 unpopulated SD holes
    hole_dia = 3.0
    pin_hole_dia = common.female_solder_hole_diameter
    hx0 = 2.5 - pcb_w / 2
    hy0 = 2.5 - pcb_l / 2
    holes: list[tuple[float, float, float]] = [
        (hx0, hy0, hole_dia),
        (hx0, hy0 + 28.0, hole_dia),
        (hx0 + 52.0, hy0, hole_dia),
        (hx0 + 52.0, hy0 + 28.0, hole_dia),
    ]
    # 1x8 header through-holes along +X edge
    for i in range(pin_count):
        holes.append((pin1_u - pcb_w / 2, pin1_v + i * pitch - pcb_l / 2, pin_hole_dia))
    # 1x4 unpopulated SD pad through-holes along -X edge
    sd_pad_v0 = (pcb_l - 3 * pitch) / 2
    for i in range(4):
        holes.append((2.5 - pcb_w / 2, sd_pad_v0 + i * pitch - pcb_l / 2, pin_hole_dia))

    board = module_pcb(
        width=pcb_w,
        length=pcb_l,
        thickness=pcb_t,
        color=pcb_color,
        holes=holes,
        name="PCB",
    ).moved(Location((pcb_center_x, pcb_center_y, ins_height)))

    # 1x8 male pin header: flipped so 5.7 mm mating pins point down (-Z),
    # 3.0 mm solder tails pass up through PCB, and pins step along +Y
    header = (
        male_pin_header(pins=pin_count, rows=1, color=header_color)
        .moved(Location((0, 0, ins_height), (180, 0, 0)))
        .moved(Location((0, 0, 0), (0, 0, 90)))
    )
    header.label = "PinHeader"

    # White TFT frame & black screen on top of PCB (Z = z_top .. z_top + 2.60)
    frame_w = 43.7
    frame_l = 34.1
    frame_h = 2.59
    frame_x0 = pcb_x_min + 6.0
    frame_y0 = pcb_y_min + 0.05

    screen_w = 38.0
    screen_l = 31.7
    screen_h = 2.60
    screen_x0 = pcb_x_min + 6.5
    screen_y0 = pcb_y_min + 1.2

    with BuildPart() as frame_builder:
        with Locations((frame_x0, frame_y0, z_top)):
            Box(
                frame_w,
                frame_l,
                frame_h,
                align=(Align.MIN, Align.MIN, Align.MIN),
            )
        with Locations((screen_x0, screen_y0, z_top)):
            Box(
                screen_w,
                screen_l,
                frame_h,
                align=(Align.MIN, Align.MIN, Align.MIN),
                mode=Mode.SUBTRACT,
            )

    assert frame_builder.part is not None
    frame = frame_builder.part
    frame.color = WHITE_FRAME_COLOR
    frame.label = "Frame"

    with (
        BuildPart() as screen_builder,
        Locations((screen_x0, screen_y0, z_top)),
    ):
        Box(
            screen_w,
            screen_l,
            screen_h,
            align=(Align.MIN, Align.MIN, Align.MIN),
        )

    assert screen_builder.part is not None
    screen = screen_builder.part
    screen.color = _resolve_screen_color(screen_color)
    screen.label = "Screen"

    # Full-size SD card reader mounted on bottom of PCB (card slot at -Y edge)
    sd_center_u = 25.75
    sd_slot = _sd_card_slot().moved(
        Location((pcb_x_min + sd_center_u, pcb_y_min, ins_height))
    )

    # Bottom silkscreen pin labels (readable when viewing the back of the PCB)
    bottom_plane = Plane(
        (0.0, 0.0, ins_height), x_dir=(1, 0, 0), z_dir=(0, 0, -1)
    )
    header_labels = ("VCC", "GND", "CS", "RESET", "A0", "SDA", "SCK", "LED")
    sd_labels = ("SD_CS", "SD_MOSI", "SD_MISO", "SD_SCK")
    sd_pad_y0 = pcb_y_min + sd_pad_v0

    with BuildPart() as silk_builder:
        with BuildSketch(bottom_plane):
            # Plane y_dir is -Y_world, so world Y maps to sketch y = -Y_world
            for i, text_str in enumerate(header_labels):
                with Locations((-1.8, -(i * pitch))):
                    Text(
                        text_str,
                        font_size=1.25,
                        align=(Align.MAX, Align.CENTER),
                    )
            for i, text_str in enumerate(sd_labels):
                with Locations((pcb_x_min + 4.0, -(sd_pad_y0 + i * pitch))):
                    Text(
                        text_str,
                        font_size=1.25,
                        align=(Align.MIN, Align.CENTER),
                    )
        extrude(amount=0.05)

    assert silk_builder.part is not None
    silkscreen = silk_builder.part
    silkscreen.color = WHITE_FRAME_COLOR
    silkscreen.label = "Silkscreen"

    model_name = "SPI-ST7735S-1.8-TFT-128x160-SD"
    model = Compound(
        children=[board, frame, screen, header, sd_slot, silkscreen],
        label=model_name,
    )

    if export:
        STEP_MODELS_DIR.mkdir(parents=True, exist_ok=True)
        export_step(model, str(STEP_MODELS_DIR / f"{model_name}.step"))

    return model


def st7735_128x160(
    pcb_color: ColorSpec = "blue",
    screen_color: ColorSpec = "black",
    header_color: ColorSpec = "black",
    export: bool = False,
) -> Compound:
    """Create an SPI ST7735 1.8" TFT (128x160) display module without SD card.

    Follows KiCad breakout module conventions:
    - Pin 1 (`GND`) of the 1x8 male header is at `(X=0, Y=0, Z=0)` with `Z=0`
      at the bottom of the header insulator (top of the carrier PCB).
    - The 8 header pins (`GND, VCC, SCL, SDA, RES, DC, CS, BL`) sit along the
      `-X` edge and step along `+Y` at 2.54 mm pitch, with 5.7 mm mating posts
      extending downward (`Z < 0`) and 3.0 mm solder tails passing upward
      through the `55.0 x 35.0 x 1.6 mm` blue PCB (`Z = 2.5 .. 4.1`).
    - Four `3.0 mm` corner mounting holes sit at `50.0 x 30.0 mm` pitch.
    - White TFT backlight frame (`43.7 x 34.1 x 2.59 mm`) and black TFT glass
      (`38.0 x 31.7 x 2.60 mm`) rest on top of the PCB (`Z = 4.1 .. 6.7`).

    Args:
        pcb_color: PCB solder-mask color (default: `"blue"`).
        screen_color: TFT screen surface color (default: `"black"`).
        header_color: Pin header plastic color (default: `"black"`).
        export: When True, exports
            `./stepModels/SPI-ST7735-1.8-TFT-128x160.step`.

    Returns:
        A `Compound` containing the PCB, white frame, TFT screen, and 1x8 male
        pin header.
    """
    pcb_w = 55.0
    pcb_l = 35.0
    pcb_t = common.pcb_width_16
    pitch = common.male_pin_pitch
    ins_height = common.male_pin_insulation_height

    # Pin 1 (GND) of the 1x8 header on the -X edge in local PCB coords (u, v)
    pin_count = 8
    pin1_u = 2.0  # 2.0 mm from -X edge
    pin1_v = (pcb_l - (pin_count - 1) * pitch) / 2  # 8.61 mm from -Y edge

    pcb_x_min = -pin1_u
    pcb_y_min = -pin1_v
    pcb_center_x = pcb_x_min + pcb_w / 2
    pcb_center_y = pcb_y_min + pcb_l / 2
    z_top = ins_height + pcb_t

    # 4 corner mounting holes (3.0 mm, 2.5 mm inset -> 50 x 30 mm pitch)
    hole_inset = 2.5
    hole_dia = 3.0
    pin_hole_dia = common.female_solder_hole_diameter
    hx = pcb_w / 2 - hole_inset
    hy = pcb_l / 2 - hole_inset
    holes: list[tuple[float, float, float]] = [
        (-hx, -hy, hole_dia),
        (-hx, hy, hole_dia),
        (hx, -hy, hole_dia),
        (hx, hy, hole_dia),
    ]
    for i in range(pin_count):
        holes.append(
            (pin1_u - pcb_w / 2, pin1_v + i * pitch - pcb_l / 2, pin_hole_dia)
        )

    board = module_pcb(
        width=pcb_w,
        length=pcb_l,
        thickness=pcb_t,
        color=pcb_color,
        corner_radius=1.5,
        holes=holes,
        name="PCB",
    ).moved(Location((pcb_center_x, pcb_center_y, ins_height)))

    header = (
        male_pin_header(pins=pin_count, rows=1, color=header_color)
        .moved(Location((0, 0, ins_height), (180, 0, 0)))
        .moved(Location((0, 0, 0), (0, 0, 90)))
    )
    header.label = "PinHeader"

    # White TFT frame & black screen on top of PCB (Z = z_top .. z_top + 2.60)
    frame_w = 43.7
    frame_l = 34.1
    frame_h = 2.59
    frame_x0 = pcb_x_min + 5.5
    frame_y0 = pcb_y_min + (pcb_l - frame_l) / 2

    screen_w = 38.0
    screen_l = 31.7
    screen_h = 2.60
    screen_x0 = frame_x0 + 0.5
    screen_y0 = pcb_y_min + (pcb_l - screen_l) / 2

    with BuildPart() as frame_builder:
        with Locations((frame_x0, frame_y0, z_top)):
            Box(
                frame_w,
                frame_l,
                frame_h,
                align=(Align.MIN, Align.MIN, Align.MIN),
            )
        with Locations((screen_x0, screen_y0, z_top)):
            Box(
                screen_w,
                screen_l,
                frame_h,
                align=(Align.MIN, Align.MIN, Align.MIN),
                mode=Mode.SUBTRACT,
            )

    assert frame_builder.part is not None
    frame = frame_builder.part
    frame.color = WHITE_FRAME_COLOR
    frame.label = "Frame"

    with (
        BuildPart() as screen_builder,
        Locations((screen_x0, screen_y0, z_top)),
    ):
        Box(
            screen_w,
            screen_l,
            screen_h,
            align=(Align.MIN, Align.MIN, Align.MIN),
        )

    assert screen_builder.part is not None
    screen = screen_builder.part
    screen.color = _resolve_screen_color(screen_color)
    screen.label = "Screen"

    # Top silkscreen pin labels along the -X edge between the header and frame
    header_labels = ("GND", "VCC", "SCL", "SDA", "RES", "DC", "CS", "BL")
    with BuildPart() as silk_builder:
        with BuildSketch(Plane.XY.offset(z_top)):
            for i, text_str in enumerate(header_labels):
                with Locations(Location((2.25, i * pitch), 90)):
                    Text(
                        text_str,
                        font_size=1.0,
                        align=(Align.CENTER, Align.CENTER),
                    )
        extrude(amount=0.05)

    assert silk_builder.part is not None
    silkscreen = silk_builder.part
    silkscreen.color = WHITE_FRAME_COLOR
    silkscreen.label = "Silkscreen"

    model_name = "SPI-ST7735-1.8-TFT-128x160"
    model = Compound(
        children=[board, frame, screen, header, silkscreen],
        label=model_name,
    )

    if export:
        STEP_MODELS_DIR.mkdir(parents=True, exist_ok=True)
        export_step(model, str(STEP_MODELS_DIR / f"{model_name}.step"))

    return model


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate 3D STEP models for display modules."
    )
    parser.add_argument(
        "display",
        choices=(
            "lcd1602",
            "lcd2004",
            "lcd12864",
            "st7735s-128x160-sd",
            "st7735-128x160",
        ),
        help="Display module to generate.",
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
        "--screen-color",
        default=None,
        help=(
            "Override screen color (blue, green, yellow-green, black, white, "
            "red, CSS color, or #RRGGBB)."
        ),
    )
    parser.add_argument(
        "--header-color",
        default="black",
        help="Pin header plastic color for displays with headers (default: black).",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export the generated model to ./stepModels/.",
    )
    args = parser.parse_args()

    if args.display == "lcd1602":
        lcd1602(
            pcb_color=args.pcb_color if args.pcb_color is not None else "green",
            screen_color=(
                args.screen_color if args.screen_color is not None else "blue"
            ),
            export=args.export,
        )
    elif args.display == "lcd2004":
        lcd2004(
            pcb_color=args.pcb_color if args.pcb_color is not None else "green",
            screen_color=(
                args.screen_color if args.screen_color is not None else "blue"
            ),
            export=args.export,
        )
    elif args.display == "lcd12864":
        lcd12864(
            pcb_color=args.pcb_color if args.pcb_color is not None else "green",
            screen_color=(
                args.screen_color if args.screen_color is not None else "blue"
            ),
            header_color=args.header_color,
            export=args.export,
        )
    elif args.display == "st7735s-128x160-sd":
        st7735s_128x160_sd(
            pcb_color=args.pcb_color if args.pcb_color is not None else "red",
            screen_color=(
                args.screen_color if args.screen_color is not None else "black"
            ),
            header_color=args.header_color,
            export=args.export,
        )
    elif args.display == "st7735-128x160":
        st7735_128x160(
            pcb_color=args.pcb_color if args.pcb_color is not None else "blue",
            screen_color=(
                args.screen_color if args.screen_color is not None else "black"
            ),
            header_color=args.header_color,
            export=args.export,
        )
