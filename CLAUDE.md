# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python-based Carbon Border Adjustment Mechanism (CBAM) Financial Estimator for calculating carbon import costs under EU regulation (effective 2026). Provides both a CLI tool for batch processing and a Streamlit web app for interactive calculations.

## Commands

**Run the Streamlit web app:**
```bash
streamlit run cbam_cost_app.py
```

**Run the CLI batch processor:**
```bash
python run_cost_tool.py
```

**Dependencies:** pandas, streamlit, openpyxl, plotly

## Architecture

### Core Components

- **`cost_config.py`** - Configuration constants: CBAM phase-in reduction rates (2026-2034), benchmark file paths, route tag descriptions (A-L)

- **`cost_engine.py`** - Shared calculation logic: `BenchmarkDatabase` class and `calculate_liability()` function used by CLI

- **`cbam_cost_app.py`** - Streamlit web application (contains duplicated database classes for standalone operation)

- **`run_cost_tool.py`** - CLI entry point: reads `CBAM_Cost_Input.xlsx`, outputs `CBAM_Financial_Report.xlsx`

### Data Files

- **`cbam-benchmarks.csv`** - EU CBAM benchmark emission values by CN code and route tag (semicolon-separated, Latin-1 encoded, European decimal format "0,666")

- **`cbam_defaults.csv`** - Country-specific default emission intensities by CN code and year

### Key Data Structures

**BenchmarkDatabase:** `{CN_Code: {RouteTag: EmissionValue}}`
- Hierarchical lookup: 8-digit → 6-digit → 4-digit CN code
- Route tag fallback: specific tag → DEFAULT → conservative minimum

**DefaultValueDatabase:** `{Country: {CN_Code: {Year: Value, RouteTag: Tag}}}`

### Calculation Flow

1. Look up CBAM phase-in reduction rate for year
2. Fetch benchmark from database (CN code + route tag)
3. Calculate free allocation: benchmark × quantity × (1 - reduction_rate)
4. Calculate payable emissions: (specific_emissions × quantity) - free_allocation
5. Calculate cost: payable_emissions × ETS_price

### Route Tags

Production technology codes affecting benchmark selection:
- A/B: Clinker/cement (grey/white)
- C/D/E: Carbon steel (BF/BOF, DRI/EAF, Scrap/EAF)
- F/G/H: Low alloy steel (BF/BOF, DRI/EAF, Scrap/EAF)
- J: High alloy steel (EAF)
- K/L: Aluminium (primary/secondary)

### Yield Factor Logic

- Raw materials (72xx, 25xx): 1.0
- Manufactured articles (73xx, 76xx except 7601): 1.1 (accounts for manufacturing loss)
