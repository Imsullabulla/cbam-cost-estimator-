import pandas as pd
import re
import os
import csv
from cost_config import CBAM_PHASE_IN_REDUCTION, ROUTE_DESCRIPTIONS

class BenchmarkDatabase:
    def __init__(self, csv_path):
        # Data Structure: {'73181510': {'C': 0.85, 'E': 0.25, 'DEFAULT': 0.5}}
        self.data = {} 
        
        if not os.path.exists(csv_path):
            print(f"CRITICAL ERROR: '{csv_path}' not found.")
            return

        print(f"Loading benchmarks from '{csv_path}'...")
        try:
            # Load with Latin-1 and Semi-colon separator
            df = pd.read_csv(csv_path, sep=';', encoding='latin-1', on_bad_lines='skip')
            
            count = 0
            for index, row in df.iterrows():
                try:
                    # Clean CN Code
                    cn_raw = str(row[0])
                    cn_code = ''.join(filter(str.isdigit, cn_raw))
                    if len(cn_code) < 4: continue

                    val_raw = str(row[1]).strip() # e.g., "0,666 (A)"
                    
                    # 1. Extract Value (e.g., 0,666 -> 0.666)
                    val_match = re.search(r'([0-9]+,[0-9]+|[0-9]+\.[0-9]+|[0-9]+)', val_raw)
                    if not val_match: continue
                    
                    val_str = val_match.group(0).replace(',', '.')
                    val = float(val_str)
                    
                    # 2. Extract Tag (e.g., A, B, C)
                    # Look for pattern: space + parenthesis + letter + parenthesis
                    tag_match = re.search(r'\(([A-Z0-9]+)\)', val_raw)
                    if tag_match:
                        tag = tag_match.group(1) # e.g. "A"
                    else:
                        tag = "DEFAULT"

                    # 3. Store in Dictionary
                    if cn_code not in self.data:
                        self.data[cn_code] = {}
                    
                    # Logic: If duplicate tags exist, take the MIN (Conservative)
                    if tag in self.data[cn_code]:
                        self.data[cn_code][tag] = min(self.data[cn_code][tag], val)
                    else:
                        self.data[cn_code][tag] = val
                        
                    count += 1
                except:
                    continue
            
            print(f"SUCCESS: Loaded {count} benchmark variants.")
            
        except Exception as e:
            print(f"Benchmark Load Error: {e}")

    def get_benchmark(self, cn_code, route_tag=None):
        cn = str(cn_code).strip()
        tag = str(route_tag).strip().upper() if pd.notna(route_tag) else "DEFAULT"
        
        # 1. Find the CN Code dictionary
        # Hierarchy: 8 digit -> 6 digit -> 4 digit
        variants = None
        if cn in self.data: variants = self.data[cn]
        elif len(cn) >= 6 and cn[:6] in self.data: variants = self.data[cn[:6]]
        elif len(cn) >= 4 and cn[:4] in self.data: variants = self.data[cn[:4]]
        
        if not variants: return 0.0, "No Benchmark Found"

        # 2. Find the Specific Tag (e.g., "C")
        if tag in variants:
            return variants[tag], f"Tag ({tag})"
            
        # 3. Fallback Logic
        if "DEFAULT" in variants:
            return variants["DEFAULT"], "Fallback to Default"
            
        # If user left it blank/default, return MINIMUM (Conservative)
        min_val = min(variants.values())
        return min_val, "Conservative Min (Tag Unspecified)"

def calculate_liability(row, db):
    try:
        year = int(row['Year'])
        cn = str(row['CN Code'])
        qty = float(row['Quantity (tonnes)'])
        see = float(row['Specific Emissions (tCO2/t)'])
        price = float(row['ETS Price (€/tCO2)'])
        route_tag = row.get('Route Tag (A, B, C...)', 'DEFAULT')
        
        # 1. Get Factors
        # Default to 1.0 (100% reduction) if year is beyond scope
        reduction_rate = CBAM_PHASE_IN_REDUCTION.get(year, 1.0)
        
        # 2. Get Benchmark
        benchmark, note = db.get_benchmark(cn, route_tag)
        
        # 3. Free Allocation Calculation
        # You get Benchmark * (1 - Reduction Rate)
        free_alloc_factor = 1.0 - reduction_rate
        if free_alloc_factor < 0: free_alloc_factor = 0
        
        free_alloc_per_ton = benchmark * free_alloc_factor
        
        # 4. Financials
        total_embedded = see * qty
        total_free_alloc = free_alloc_per_ton * qty
        
        payable_emissions = total_embedded - total_free_alloc
        if payable_emissions < 0: payable_emissions = 0
        
        est_cost = payable_emissions * price
        
        return pd.Series([
            benchmark,
            note,
            f"{reduction_rate*100}%",
            f"{free_alloc_factor*100:.1f}%",
            payable_emissions,
            est_cost
        ])
        
    except Exception as e:
        return pd.Series([0, "Error", 0, 0, 0, 0])
