# Python build123d model generation for KiCad

Reusable 3D component models implemented in Python with [`build123d`](https://build123d.readthedocs.io/).
Standard dimensions (in mm) are defined in `common.py`, and exported `.step` files are saved to `./stepModels/` for import in the KiCad footprint manager.

## Setup

Requires Python 3.13+ and [`uv`](https://docs.astral.sh/uv/):

```sh
$env:UV_PYTHON_PREFERENCE = "only-system"
uv python pin 3.12
uv sync
```

## Components

### Pin headers (`pinHeaders.py`)

Vertical and right-angle (horizontal/angled) through-hole male pin headers, plus vertical female pin sockets (single-row and multi-row, 2.54 mm pitch).

- **Origin & alignment**: Pin 1 is centered at `(X=0, Y=0)` with `Z=0` at the PCB top surface (bottom of the plastic housing). Pins step along `+X` and additional rows step along `+Y`. For angled/horizontal male headers, the 90° bent mating posts extend along `+Y` while solder tails extend into `Z < 0`.
- **Exported files** (in `./stepModels/` when `--export` / `export=True` is set):
  - Vertical male: `PinHeader_{rows}x{pins:02d}_P2.54mm_Vertical[_<Color>].step`
  - Angled/horizontal male: `PinHeader_{rows}x{pins:02d}_P2.54mm_Horizontal[_<Color>].step`
  - Female: `PinSocket_{rows}x{pins:02d}_P2.54mm_Vertical[_<Color>].step`
  - Default `black` omits the color suffix.

#### CLI usage

```sh
# 1x8 male pin header (default black, vertical)
uv run python pinHeaders.py 8 --type male --export

# 1x6 right-angle (angled/horizontal) male pin header
uv run python pinHeaders.py 6 --orientation angled --export

# 1x8 red female pin socket
uv run python pinHeaders.py 8 --type female --color red --export

# 2x4 angled male pin header with custom hex color
uv run python pinHeaders.py 4 --rows 2 --orientation horizontal --color "#1e90ff" --export
```

Options:
- `pins`: Number of pins per row (required).
- `--type {male,female}`: Header gender (default: `male`).
- `--rows ROWS`: Number of rows (default: `1`).
- `--orientation {vertical,horizontal,angled}`: Header orientation (default: `vertical`; `horizontal`/`angled` supported for male headers).
- `--color COLOR`: Plastic housing color preset (`black`, `white`, `red`, `blue`, `green`, `yellow`, `orange`, `gray`), CSS color name, or `#RRGGBB` hex string (default: `black`).
- `--export`: Export the model as a `.step` file to `./stepModels/`.

#### Python API

```python
from pinHeaders import (
    angled_male_pin_header,
    female_pin_header,
    male_pin_header,
    pin_header,
)

male_pin_header(8, export=True)
angled_male_pin_header(6, export=True)
female_pin_header(8, color="red", export=True)
pin_header(4, header_type="male", rows=2, orientation="angled", color="#1e90ff", export=True)
```

### Module PCBs (`pcb.py`)

Rectangular module PCBs (default thickness `1.6 mm` from `common.pcb_width_16`) with optional corner fillets and drilled through-holes. Common solder-mask presets include `green` (default), `purple`, `blue`, `red`, `black`, `white`, and `yellow`, plus CSS color names, `#RRGGBB` hex strings, RGB float tuples, or `build123d.Color`.

```sh
uv run python pcb.py 10.3 13.0 --color purple --export
```

### IoT breakout modules (`iotModules.py`)

Composes a rectangular PCB from `pcb.py` with 1 or 2 parallel male pin headers from `pinHeaders.py`. Pin 1 of row 1 is at `(0, 0, 0)` with `Z=0` at the bottom of the header insulator (5.7 mm mating pins extending downward, 3.0 mm solder tails passing upward through the PCB).

Includes:
- `bmp180` (`10.3 × 13.0 × 1.6 mm` PCB + 4-pin header on the short edge, default `purple` PCB).
- `ftdi` (FTDI FT232RL USB-to-TTL serial breakout: `18.20 × 36.00 × 1.6 mm` default `red` PCB, 1×6 right-angle male pin header with `GND`, `CTS`, `VCC`, `TXD`, `RXD`, `DTR` silkscreen labels, 3.3V/5V voltage jumper, FT232RL IC, 2×9 side breakout holes, and selectable USB receptacle: `mini` [default], `micro`, or `usb-c`).
- `max98357a` (MAX98357A I2S 3W mono amplifier: `17.7 × 18.9 × 1.6 mm` rounded-corner default `purple` PCB, 1×7 default `yellow` male header with `LRC`, `BCLK`, `DIN`, `GAIN`, `SD`, `GND`, `Vin` silkscreen labels, corner mounting holes, speaker output holes, and QFN-16 IC).

```sh
# Generate BMP180 (default purple PCB, black header)
uv run python iotModules.py bmp180 --export

# Generate FTDI FT232RL module (default red PCB, black header, Mini-USB)
uv run python iotModules.py ftdi --export

# Generate FTDI with Micro-USB or USB-C
uv run python iotModules.py ftdi --usb micro --export
uv run python iotModules.py ftdi --usb usb-c --export

# Generate MAX98357A I2S amp (default purple PCB, yellow 7-pin header)
uv run python iotModules.py max98357a --export

# Override PCB or header color
uv run python iotModules.py bmp180 --pcb-color green --header-color yellow --export
```

```python
from iotModules import bmp180, ftdi, iot_module, max98357a

bmp180(export=True)
bmp180(pcb_color="green", export=True)
ftdi(export=True)
ftdi(usb_connector="micro", export=True)
ftdi(usb_connector="usb-c", export=True)
max98357a(export=True)
iot_module("CustomDualRow", pcb_width=20.32, pcb_length=18.0, pins_per_row=7, header_rows=2, export=True)
```

### USB connectors (`usbConnectors.py`)

Standard surface-mount USB-C (`USB_C_Receptacle.step`), Micro-USB Type-B (`Micro_USB_B_Receptacle.step`), and Mini-USB Type-B (`Mini_USB_B_Receptacle.step`) receptacles. All connectors are centered in `X`, have their front mating opening at `Y = 0` facing `-Y` with the body extending along `+Y`, and rest on `Z = 0` (with locating pegs / through-hole tabs extending into `Z < 0`).

```sh
# Generate USB-C receptacle
uv run python usbConnectors.py usb-c --export

# Generate Micro-USB Type-B receptacle
uv run python usbConnectors.py micro-usb --export

# Generate Mini-USB Type-B receptacle
uv run python usbConnectors.py mini-usb --export
```

```python
from usbConnectors import usb_c, micro_usb, mini_usb

usb_c(export=True)
micro_usb(export=True)
mini_usb(export=True)
```

### IoT microcontrollers (`iotMicrocontrollers.py`)

Dual-row IoT microcontroller boards composed from `pcb.py`, `pinHeaders.py`, and `usbConnectors.py`. Pin 1 of row 1 is at `(0, 0, 0)` with `Z = 0` at the bottom of the header insulator (5.7 mm mating posts extending downward, 3.0 mm solder tails passing upward through the PCB, and the USB receptacle mounted on the top surface of the PCB).

Includes:
- `esp32_c3` (ESP32-C3 SuperMini: `22.8 × 18.0 × 1.6 mm` PCB, two 1×8 male headers at `15.10 mm` row spacing with white silkscreen pin labels, and a USB-C receptacle overhanging `1.4 mm` on the `-X` edge).
- `esp32_s3` (ESP32-S3 DevKit: `57.5 × 28.6 × 1.6 mm` PCB, two 1×22 male headers at `25.80 mm` row spacing with white silkscreen pin labels, dual USB-C receptacles on the `-X` edge, and the RF module with antenna overhang, metallic shield, and `"ESP32-S3"` label).
- `esp32_devkit_v1_30_pin` (ESP32 DevKit V1 30-pin: `51.4 × 28.5 × 1.6 mm` rounded default `black` PCB with four corner mounting holes, two 1×15 male headers at `25.4 mm` / 1 in row spacing with white silkscreen pin labels, USB-C receptacle flanked by `EN` and `BOOT` buttons, `AMS1117`, `CP2102`, power/GPIO2 LEDs, and the `ESP-WROOM-32` RF module).
- `esp32_devkitc_38_pin` (ESP32-DevKitC 38-pin: `54.7 × 28.5 × 1.6 mm` rounded default `black` PCB, two 1×19 male headers at `25.4 mm` / 1 in row spacing with white silkscreen pin labels, USB-C receptacle flanked by `RST` and `BOOT` buttons, `AMS1117`, `CP2102`, power LED, and the `ESP-WROOM-32D` RF module).
- `esp8266` (ESP8266 NodeMCU: `48.6 × 25.5 × 1.6 mm` PCB, two 1×15 male headers at `22.70 mm` row spacing, and a Micro-USB Type-B receptacle flush with the `-X` edge).
- `stm32f103c8t6` (STM32F103C8T6 "Blue Pill" USB-C: `53.34 × 22.86 × 1.6 mm` default `blue` PCB, two 1×20 male headers at `15.24 mm` / 0.6 in row spacing with white silkscreen pin labels outboard of both rows, USB-C receptacle on `-X`, 2×3 yellow BOOT jumper block, RESET button, 45° LQFP-48 STM32 MCU, 8 MHz & 32.768 kHz crystals, PWR/PC13 LEDs, and a 1×4 right-angle SWD header on `+X`).
- `stm32f411ceu6` (STM32F411CEU6 "Black Pill" USB-C: `52.81 × 20.78 × 1.6 mm` default `black` PCB, two 1×20 male headers at `15.24 mm` / 600 mil row spacing with white silkscreen pin labels outboard of both rows, USB-C receptacle on `-X`, `NRST`/`BOOT0` buttons, 45° UFQFPN-48 STM32F411 MCU, 25 MHz & 32.768 kHz SMD crystals, `KEY` button, C13/PWR LEDs, and a 1×4 right-angle SWD header on `+X`).

```sh
# Generate ESP32-C3 (default green PCB, black headers)
uv run python iotMicrocontrollers.py esp32-c3 --export

# Generate ESP32-S3 (default green PCB, yellow headers)
uv run python iotMicrocontrollers.py esp32-s3 --export

# Generate ESP32 DevKit V1 30-pin (default black PCB, black headers)
uv run python iotMicrocontrollers.py esp32-devkit-v1-30-pin --export

# Generate ESP32-DevKitC 38-pin (default black PCB, black headers)
uv run python iotMicrocontrollers.py esp32-devkitc-38-pin --export

# Generate ESP8266 (default green PCB, black headers)
uv run python iotMicrocontrollers.py esp8266 --export

# Generate STM32F103C8T6 Blue Pill USB-C (default blue PCB, yellow headers)
uv run python iotMicrocontrollers.py stm32f103c8t6 --export

# Generate STM32F411CEU6 Black Pill USB-C (default black PCB, yellow headers)
uv run python iotMicrocontrollers.py stm32f411ceu6 --export

# Override PCB or header color
uv run python iotMicrocontrollers.py esp32-c3 --pcb-color black --header-color yellow --export
```

```python
from iotMicrocontrollers import (
    esp32_c3,
    esp32_devkit_v1_30_pin,
    esp32_devkitc_38_pin,
    esp32_s3,
    esp8266,
    iot_microcontroller,
    stm32f103c8t6,
    stm32f411ceu6,
)

esp32_c3(export=True)
esp32_s3(export=True)
esp32_devkit_v1_30_pin(export=True)
esp32_devkitc_38_pin(export=True)
esp8266(export=True)
stm32f103c8t6(export=True)
stm32f411ceu6(export=True)
```

### Displays (`displays.py`)

Display modules composed from `pcb.py` with mounting holes, bezels, and screen panes. Centered in `XY` with the bottom of the PCB resting on `Z = 0`.

Includes:
- `lcd1602` (16×2 character LCD: `80.0 × 36.0 × 1.6 mm` PCB with four `3.0 mm` corner mounting holes at `75 × 31 mm` pitch, `71.4 × 23.8 × 7.4 mm` black bezel, and a recessed `64.5 × 14.5 mm` viewing window).
- `lcd2004` (20×4 character LCD: `98.0 × 60.0 × 1.6 mm` PCB with four `3.0 mm` corner mounting holes at `93 × 55 mm` pitch, `97.0 × 39.7 × 9.0 mm` black bezel, and a recessed `76.0 × 26.0 mm` viewing window).
- `lcd12864` (128×64 graphic LCD: `93.0 × 70.0 × 1.6 mm` PCB with four `2.5 mm` corner mounting holes at `88 × 65 mm` pitch, 1×20 male pin header along the `-Y` edge at `14.0 mm` from `-X` with top silkscreen labels `BLK..GND`, `78.6 × 50.5 × 7.9 mm` black bezel, and recessed `72.0 × 40.0 mm` viewing window).
- `st7735s_128x160_sd` (`SPI-ST7735S-1.8-TFT-128x160-SD`: `58.0 × 34.2 × 1.6 mm` red PCB with four `3.0 mm` mounting holes, 1×8 male pin header with Pin 1 at `(0, 0, 0)`, white frame + black TFT glass on top, and full-size SD card reader on the bottom).
- `st7735_128x160` (`SPI-ST7735-1.8-TFT-128x160`: `55.0 × 35.0 × 1.6 mm` blue PCB with rounded corners, four `3.0 mm` mounting holes at `50 × 30 mm` pitch, 1×8 male pin header along the `-X` edge with Pin 1 (`GND`) at `(0, 0, 0)`, and white frame + black TFT glass on top; no SD card reader).
- `st7789_170x320` (`SPI-ST7789-1.9-TFT-170x320`: `62.0 × 29.0 × 1.6 mm` blue PCB with rounded corners, four `2.5 mm` mounting holes at `57 × 24 mm` pitch, FPC ribbon slot, 1×8 male pin header along the `-X` edge with Pin 1 (`GND`) at `(0, 0, 0)` and top silkscreen labels `GND, VCC, SCL, SDA, RES, DC, CS, BLK`, plus `49.72 × 25.80 × 1.43 mm` IPS TFT panel with `42.72 × 22.70 mm` active area).

```sh
# Generate LCD1602 (default green PCB, blue screen)
uv run python displays.py lcd1602 --export

# Generate LCD2004, LCD12864, or SPI TFT displays
uv run python displays.py lcd2004 --export
uv run python displays.py lcd12864 --export
uv run python displays.py st7735s-128x160-sd --export
uv run python displays.py st7735-128x160 --export
uv run python displays.py st7789-170x320 --export

# Yellow-green backlit LCD1602
uv run python displays.py lcd1602 --screen-color yellow-green --export
```

```python
from displays import (
    lcd1602,
    lcd2004,
    lcd12864,
    st7735_128x160,
    st7735s_128x160_sd,
    st7789_170x320,
)

lcd1602(export=True)
lcd2004(export=True)
lcd12864(export=True)
st7735s_128x160_sd(export=True)
st7735_128x160(export=True)
st7789_170x320(export=True)
```

## STEP viewer (`stepViewer.py`)

Interactive offline 3D viewer for inspecting generated `.step`/`.stp` models in your browser (WebGL2, no extra dependencies). Includes orbit/pan/zoom controls, camera presets, a 2.54 mm PCB grid at `Z=0`, origin axes, bounding-box dimensions, and per-part visibility toggles.

```sh
# View a specific STEP file
uv run python stepViewer.py stepModels/PinHeader_1x08_P2.54mm_Vertical.step

# View all STEP files in ./stepModels/ (with a model selector dropdown)
uv run python stepViewer.py

# Save a standalone HTML viewer without opening the browser
uv run python stepViewer.py stepModels/PinHeader_1x08_P2.54mm_Vertical.step -o preview.html --no-browser
```

## Code quality verification

```sh
uv run ruff check .
uv run mypy .
```
