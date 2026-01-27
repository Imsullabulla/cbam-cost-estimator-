# cost_config.py

# 1. PHASE-IN RATES
CBAM_PHASE_IN_REDUCTION = {
    2026: 0.025,
    2027: 0.05,
    2028: 0.10,
    2029: 0.225,
    2030: 0.485,
    2031: 0.61,
    2032: 0.735,
    2033: 0.86,
    2034: 1.00
}

# 2. FILE SETTINGS
BENCHMARK_FILE = "cbam-benchmarks.csv"

# 3. ROUTE LEGEND
ROUTE_DESCRIPTIONS = {
    "A": "Grey clinker / cement",
    "B": "White clinker / cement",
    "C": "Carbon Steel (BF/BOF)",
    "D": "Carbon Steel (DRI/EAF)",
    "E": "Carbon Steel (Scrap/EAF)",
    "F": "Low alloy Steel (BF/BOF)",
    "G": "Low alloy Steel (DRI/EAF)",
    "H": "Low alloy Steel (Scrap/EAF)",
    "J": "High alloy Steel (EAF)",
    "K": "Primary Aluminium",
    "L": "Secondary Aluminium",
    "DEFAULT": "Standard/General Benchmark"
}
