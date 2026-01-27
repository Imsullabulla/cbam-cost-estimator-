import pandas as pd
import os
from cost_engine import BenchmarkDatabase, calculate_liability
from cost_config import BENCHMARK_FILE, ROUTE_DESCRIPTIONS

def create_template():
    data = {
        'Year': [2026, 2026, 2026],
        'CN Code': ['72071114', '72071114', '25231000'],
        'Description': ['Carbon Steel (BF/BOF)', 'Carbon Steel (EAF)', 'Grey Clinker'],
        'Route Tag (A, B, C...)': ['C', 'E', 'A'], # <--- NEW COLUMN
        'Quantity (tonnes)': [1000, 1000, 5000],
        'Specific Emissions (tCO2/t)': [2.2, 0.4, 0.85],
        'ETS Price (€/tCO2)': [90, 90, 90]
    }
    df = pd.DataFrame(data)
    df.to_excel('CBAM_Cost_Input.xlsx', index=False)
    print("Created 'CBAM_Cost_Input.xlsx' with Route Tag column.")

def main():
    print("--- CBAM COST ESTIMATOR (Route Specific) ---")
    
    db = BenchmarkDatabase(BENCHMARK_FILE)
    if not db.data: return
    
    if not os.path.exists('CBAM_Cost_Input.xlsx'):
        create_template()
        return
        
    print("Reading 'CBAM_Cost_Input.xlsx'...")
    df_in = pd.read_excel('CBAM_Cost_Input.xlsx', dtype={'CN Code': str})
    
    print("Calculating Costs...")
    res_cols = ['Benchmark', 'Bench Source', 'CBAM Cut', 'Free Alloc %', 'PAYABLE tCO2', 'COST (€)']
    
    results = df_in.apply(lambda row: calculate_liability(row, db), axis=1)
    results.columns = res_cols
    
    df_final = pd.concat([df_in, results], axis=1)
    df_final['Effective Tax (€/t)'] = df_final['COST (€)'] / df_final['Quantity (tonnes)']
    
    # Save with a Reference Sheet for the Legend
    with pd.ExcelWriter('CBAM_Financial_Report.xlsx') as writer:
        df_final.to_excel(writer, sheet_name='Cost_Calculation', index=False)
        
        # Create Legend Sheet
        legend_df = pd.DataFrame(list(ROUTE_DESCRIPTIONS.items()), columns=['Tag', 'Description'])
        legend_df.to_excel(writer, sheet_name='Route_Legend', index=False)
        
    print("\nSUCCESS! Report saved.")
    print(df_final[['CN Code', 'Route Tag (A, B, C...)', 'Benchmark', 'COST (€)', 'Effective Tax (€/t)']].to_string())

if __name__ == "__main__":
    main()
