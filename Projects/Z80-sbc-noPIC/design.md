# Z80 Retro SBC — I/O Subsystem Design Document

## 1. Overview

This document describes the I/O subsystem design for a 5V through-hole retro-Z80 Single Board Computer (SBC) combining:

- **Z80 CPU** (5V, system clock **≤ 6 MHz** to match the Z80 PIO speed grade)
- **`Z84C2006PEC` (Z80 PIO)** — native 5V 40-PDIP parallel GPIO controller (two 8-bit ports with handshake lines and Z80 Mode 2 interrupt daisy-chaining)
- RAM Memory: HM62256B (Hitachi) or CY62256 (Cypress). 28 pin.
- ROM Memory: EEPROM: AT28C256-15PU.
- Serial:
    - TL16C550CN + 1.8432Mhz crystal : Strictly interrupt mode 1.
    - External USB-to-Serial adapter module (e.g. CH340) connected via a female pin header in the board.
- Parallel:
	- Z84C2006PEC (2 8-bit bidirectional ports)
- Logic gates: 74HCT00, 74HCT04, 74HCT138 (A3,A4,A5, used as I/O address decoder).
- 6 Mhz 4-pin canned crystal
- Reset: MCP130-450DI TO-92
- Decoupling capacitors: 100nF

## Memory map

- ROM: 0000-7FFF
- RAM: 8000-FFFF

## I/O map

- Z84C2006PEC: 00-03 (mirrored 04-07)
- TL16C550CN : 08-0F

