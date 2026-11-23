# Python 3D models of components to be used as footprints in KiCad

A collection of reusable 3D component models implemented in Python with `build123d`.
Generated models are saved as `.step` files in `./stepModels/` to be imported in the KiCad footprint manager.

## Project Structure

- `common.py` — Standard physical dimensions in mm (PCB thickness, male/female pin header dimensions). Reuse or extend constants here instead of hardcoding standard measurements.
- `pinHeaders.py` — Parametric vertical male pin headers and female pin sockets (`rows x pins`, optional plastic `color` defaulting to `"black"`).
- `pcb.py` — Parametric rectangular module PCBs (default `1.6 mm` thickness, solder-mask color presets like `"green"` / `"purple"` with custom overrides, optional corner fillets and through-holes).
- `iotModules.py` — Breakout/IoT modules composed from `pcb.py` and `pinHeaders.py` (e.g., `bmp180`).
- `stepViewer.py` — Self-contained offline WebGL2 `.step` viewer for visual inspection (2.54 mm grid at `Z=0`, origin axes, bounding-box dimensions, per-part visibility).
- `./stepModels/` — Output folder for exported `.step` files.

## KiCad Coordinate & Geometry Conventions

- **Units & axes**: All dimensions are in **millimeters (mm)** with **Z-up**.
- **PCB plane (`Z = 0`)**: `Z = 0` is the top surface of the host/carrier PCB where the component body or header insulator rests. Through-hole leads and mating pins extend into `Z < 0`.
- **Origin (Pin 1)**: Place Pin 1 at `(X = 0, Y = 0, Z = 0)`. Step pins along `+X` by pitch and additional rows along `+Y`.
- **Breakout modules**: Mount the module PCB on top of the header insulator (`Z = 2.5 .. 2.5 + thickness`), drill through-holes for the pins, and orient male headers so the **short end (3.0 mm)** passes upward through the module PCB for soldering while the **long end (5.7 mm)** extends downward (`Z < 0`) to insert into the host board.

## Module & Export Guidelines

- **Composition**: Build higher-level modules by composing existing primitives (`module_pcb`, `male_pin_header`, `female_pin_header`) rather than duplicating geometry.
- **Export interface**: Model functions should accept `export: bool = False` and write `<ModelName>.step` into `./stepModels/` when `export=True`. Provide a CLI (`if __name__ == "__main__":`) with `--export`.
- **STEP colors & labels**: Set `.label` and `.color` (`build123d.Color`) on logical sub-parts (e.g., `PCB`, `Insulator`, `Housing`, `Pins`, `SolderTails`) so KiCad and `stepViewer.py` preserve materials and part structure.
- **Documentation**: Keep `README.md` updated when adding new component modules or CLI options.

## Verification Workflow

Run all commands via `uv`:

```sh
uv run ruff check .
uv run mypy .
```

When adding or modifying geometry:
1. Confirm `model.is_valid` is `True` and verify bounding-box dimensions in mm.
2. Verify STEP round-trip geometry and world-space part coordinates/colors via `stepViewer.load_step_model(...)` (which accounts for nested `Compound` transforms).
3. Inspect visually with `uv run python stepViewer.py stepModels/<file>.step` when needed.
