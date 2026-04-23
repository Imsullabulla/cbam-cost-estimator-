"""
Parses 'DVs as adopted_v20260204 .xlsx' and regenerates cbam_defaults.csv.
Run: python build_defaults_csv.py
"""
import re
import pandas as pd

EXCEL_FILE = "DVs as adopted_v20260204 .xlsx"
OUTPUT_CSV = "cbam_defaults.csv"
SKIP_SHEETS = {"Overview", "Version History"}

OUTPUT_COLUMNS = [
    "Country",
    "Sector",
    "Product CN Code",
    "Description",
    "Default Value (direct emissions)",
    "Default Value (Indirect emissions)",
    "Default Value (total emissions)",
    "2026 Default Value (Including mark-up)",
    "2027 Default Value (Including mark-up)",
    "2028 Default Value (Including mark-up)",
    "Underlying production route determining CBAM BM",
]

# Column indices in each sheet (0-based)
COL_CN = 0
COL_DESC = 1
COL_DIRECT = 2
COL_INDIRECT = 3
COL_TOTAL = 4
COL_2026 = 5
COL_2027 = 6
COL_2028 = 7
COL_ROUTE = 8


def is_cn_code(val):
    return bool(re.match(r"^\s*\d", str(val)))


def clean_cn(val):
    return "".join(filter(str.isdigit, str(val)))


def parse_numeric(val):
    """Return float or None for missing/dash values."""
    s = str(val).strip()
    if s in ("nan", "", "–", "-", "see below"):
        return None
    m = re.search(r"([0-9]+[.,][0-9]+|[0-9]+)", s)
    if m:
        return round(float(m.group(0).replace(",", ".")), 6)
    return None


def parse_sheet(xl, sheet_name):
    df = xl.parse(sheet_name, header=None)
    rows = []
    current_sector = ""

    for i, row in df.iterrows():
        cell0 = str(row[COL_CN]).strip()

        # Skip country-name row and header row
        if i <= 1:
            continue

        if is_cn_code(cell0):
            cn = clean_cn(cell0)
            if len(cn) < 4:
                continue

            desc = str(row[COL_DESC]).strip() if not pd.isna(row[COL_DESC]) else ""
            route_raw = str(row[COL_ROUTE]).strip() if not pd.isna(row[COL_ROUTE]) else ""
            route_m = re.search(r"\(([A-Z])\)", route_raw)
            route = f"({route_m.group(1)})" if route_m else ""

            rows.append({
                "Country": sheet_name,
                "Sector": current_sector,
                "Product CN Code": cn,
                "Description": desc,
                "Default Value (direct emissions)": parse_numeric(row[COL_DIRECT]),
                "Default Value (Indirect emissions)": parse_numeric(row[COL_INDIRECT]),
                "Default Value (total emissions)": parse_numeric(row[COL_TOTAL]),
                "2026 Default Value (Including mark-up)": parse_numeric(row[COL_2026]),
                "2027 Default Value (Including mark-up)": parse_numeric(row[COL_2027]),
                "2028 Default Value (Including mark-up)": parse_numeric(row[COL_2028]),
                "Underlying production route determining CBAM BM": route,
            })
        elif not pd.isna(row[COL_DESC]) if COL_DESC < len(row) else True:
            pass  # header-like row inside sheet — ignore
        elif cell0 not in ("nan",) and not is_cn_code(cell0):
            # Sector header: text in col0, col1 is NaN
            if pd.isna(row[COL_DESC]):
                current_sector = cell0

    return rows


def main():
    xl = pd.ExcelFile(EXCEL_FILE)
    all_rows = []

    country_sheets = [s for s in xl.sheet_names if s not in SKIP_SHEETS]
    print(f"Behandler {len(country_sheets)} lande-faner...")

    for sheet in country_sheets:
        rows = parse_sheet(xl, sheet)
        all_rows.extend(rows)
        print(f"  {sheet}: {len(rows)} rækker")

    df_out = pd.DataFrame(all_rows, columns=OUTPUT_COLUMNS)

    # Use semicolon separator and latin-1 encoding to match original
    df_out.to_csv(OUTPUT_CSV, sep=";", index=False, encoding="latin-1")
    print(f"\nFærdig: {len(df_out)} rækker skrevet til {OUTPUT_CSV}")
    print(f"Lande: {df_out['Country'].nunique()}")
    print(f"Sektorer: {sorted(df_out['Sector'].unique())}")


if __name__ == "__main__":
    main()
