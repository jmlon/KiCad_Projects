# Python build123d model generation for KiCad

Reusable 3D component models implemented in Python with [`build123d`](https://build123d.readthedocs.io/).
Standard dimensions (in mm) are defined in `common.py`, and exported `.step` files are saved to `./stepModels/` for import in the KiCad footprint manager.

## Setup

Requires Python 3.13+ and [`uv`](https://docs.astral.sh/uv/):

```sh
uv sync
```

## Components

### Pin headers (`pinHeaders.py`)

Vertical through-hole male pin headers and female pin sockets (single-row and multi-row, 2.54 mm pitch).

- **Origin & alignment**: Pin 1 is centered at `(X=0, Y=0)` with `Z=0` at the PCB top surface (bottom of the plastic housing). Pins step along `+X` and additional rows step along `+Y`.
- **Exported files** (in `./stepModels/` when `--export` / `export=True` is set):
  - Male: `PinHeader_{rows}x{pins:02d}_P2.54mm_Vertical.step`
  - Female: `PinSocket_{rows}x{pins:02d}_P2.54mm_Vertical.step`

#### CLI usage

```sh
# 1x8 male pin header
uv run python pinHeaders.py 8 --type male --export

# 1x8 female pin socket
uv run python pinHeaders.py 8 --type female --export

# 2x4 male pin header
uv run python pinHeaders.py 4 --type male --rows 2 --export
```

Options:
- `pins`: Number of pins per row (required).
- `--type {male,female}`: Header gender (default: `male`).
- `--rows ROWS`: Number of rows (default: `1`).
- `--export`: Export the model as a `.step` file to `./stepModels/`.

#### Python API

```python
from pinHeaders import male_pin_header, female_pin_header, pin_header

male_pin_header(8, export=True)
female_pin_header(8, export=True)
pin_header(4, header_type="male", rows=2, export=True)
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
