import pandas as pd
from dataclasses import dataclass
import sys
import os
import re

# --- DATA MODELS ---
@dataclass
class CalculationResult:
    total_emissions: float
    type: str 
    notes: str

class DefaultValueDatabase:
    def __init__(self, csv_path: str):
        self.data = [] 
        
        if not os.path.exists(csv_path):
            print(f"CRITICAL ERROR: '{csv_path}' not found.")
            return

        print(f"Reading database from '{csv_path}'...")
        
        try:
            # Load with Latin-1 to handle special chars and Semi-colon separator
            df = pd.read_csv(
                csv_path, 
                sep=';', 
                encoding='latin-1',
                dtype=str,
                on_bad_lines='skip'
            )
            
            df.columns = df.columns.str.strip()
            
            # Identify Columns
            col_cn = next((c for c in df.columns if 'CN Code' in c), 'Product CN Code')
            col_country = next((c for c in df.columns if 'Country' in c), 'Country')
            
            # Map years to columns
            self.cols_year = {
                2026: next((c for c in df.columns if '2026' in c), None),
                2027: next((c for c in df.columns if '2027' in c), None),
                2028: next((c for c in df.columns if '2028' in c), None)
            }

            # Process Data
            count = 0
            for _, row in df.iterrows():
                try:
                    country = str(row[col_country]).strip().lower()
                    cn_raw = str(row[col_cn])
                    cn_code = ''.join(filter(str.isdigit, cn_raw))
                    
                    entry = {'country': country, 'cn_code': cn_code}
                    
                    # Store values for all available years
                    for year, col_name in self.cols_year.items():
                        if col_name:
                            val_raw = str(row[col_name])
                            # Regex to fix "0,957" -> 0.957
                            match = re.search(r'([0-9]+[.,][0-9]+|[0-9]+)', val_raw)
                            if match:
                                val_str = match.group(0).replace(',', '.')
                                entry[year] = float(val_str)
                            else:
                                entry[year] = 0.0
                    
                    self.data.append(entry)
                    count += 1
                except:
                    continue
            
            print(f"SUCCESS: Loaded {count} rows successfully.")
            
        except Exception as e:
            print(f"Read failed: {e}")

    def get_default_see(self, cn_code: str, country: str, year: int) -> float:
        target_cn = str(cn_code).strip()
        target_country = str(country).strip().lower()
        
        # LOGIC UPGRADE: Fallback for Future Years
        lookup_year = year
        if year > 2028:
            lookup_year = 2028 # Cap at 2028
            
        # Hierarchy Search
        res = self._lookup(target_cn, target_country, lookup_year)
        if res > 0: return res
        
        if len(target_cn) >= 6:
            res = self._lookup(target_cn[:6], target_country, lookup_year)
            if res > 0: return res
            
        if len(target_cn) >= 4:
            res = self._lookup(target_cn[:4], target_country, lookup_year)
            if res > 0: return res
            
        return 0.0

    def _lookup(self, cn, country, year):
        # A. Specific Country
        for row in self.data:
            if row['cn_code'] == cn and row['country'] == country:
                return row.get(year, 0.0)
                
        # B. Global Fallback
        for row in self.data:
            if row['cn_code'] == cn and 'other countries' in row['country']:
                return row.get(year, 0.0)
        return 0.0
