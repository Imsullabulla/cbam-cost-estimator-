import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import re

# ==========================================
# 1. CONFIGURATION
# ==========================================
CBAM_PHASE_IN_REDUCTION = {
    2026: 0.025, 2027: 0.05, 2028: 0.10, 2029: 0.225,
    2030: 0.485, 2031: 0.61, 2032: 0.735, 2033: 0.86, 2034: 1.00
}

# Official CBAM certificate prices per quarter (2026)
# Published by the Commission the first calendar week after each quarter ends.
# Each price applies to CBAM certificates for goods imported during that quarter.
# Source: Article 20 of Regulation (EU) 2023/956
CBAM_QUARTERLY_PRICES_2026 = {
    "Q1 (Jan–Mar)": {"price": 75.36, "published": "7 April 2026"},
    "Q2 (Apr–Jun)": {"price": None,  "published": "6 July 2026"},
    "Q3 (Jul–Sep)": {"price": None,  "published": "5 October 2026"},
    "Q4 (Oct–Dec)": {"price": None,  "published": "4 January 2027"},
}

# Standard defaults for yield (Consumption Factor)
# 72xx = 1.0 (It IS the steel)
# 73xx = 1.1 (It is MADE of steel, with scrap loss)
def get_default_yield(cn_code):
    if cn_code.startswith("73"): return 1.10 # Steel Articles
    if cn_code.startswith("76") and not cn_code.startswith("7601"): return 1.10 # Alu Articles
    return 1.00 # Default for Raw Materials (72xx, 25xx, etc.)

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

BENCHMARK_FILE = "cbam-benchmarks.csv"
DEFAULTS_FILE = "cbam_defaults.csv"

# ==========================================
# 2. ENGINE LOGIC
# ==========================================
class BenchmarkDatabase:
    def __init__(self, csv_path):
        self.data = {} 
        self.cn_list = []
        
        if not os.path.exists(csv_path):
            st.error(f"CRITICAL: '{csv_path}' missing.")
            return

        try:
            df = pd.read_csv(csv_path, sep=';', encoding='latin-1', on_bad_lines='skip')
            for _, row in df.iterrows():
                try:
                    cn_raw = str(row[0])
                    cn_code = ''.join(filter(str.isdigit, cn_raw))
                    if len(cn_code) < 4: continue

                    val_raw = str(row[1]).strip()
                    val_match = re.search(r'([0-9]+,[0-9]+|[0-9]+\.[0-9]+|[0-9]+)', val_raw)
                    if not val_match: continue
                    val = float(val_match.group(0).replace(',', '.'))
                    
                    tag_match = re.search(r'\(([A-Z0-9]+)\)', val_raw)
                    tag = tag_match.group(1) if tag_match else "DEFAULT"

                    if cn_code not in self.data: 
                        self.data[cn_code] = {}
                        self.cn_list.append(cn_code)
                    
                    if tag in self.data[cn_code]:
                        self.data[cn_code][tag] = min(self.data[cn_code][tag], val)
                    else:
                        self.data[cn_code][tag] = val
                except: continue
        except Exception as e:
            st.error(f"Bench DB Error: {e}")

    def get_benchmark(self, cn_code, route_tag="DEFAULT"):
        cn = str(cn_code).strip()
        tag = str(route_tag).strip().upper()
        
        variants = None
        if cn in self.data: variants = self.data[cn]
        elif len(cn) >= 6 and cn[:6] in self.data: variants = self.data[cn[:6]]
        elif len(cn) >= 4 and cn[:4] in self.data: variants = self.data[cn[:4]]
        
        if not variants: return 0.0, "No Benchmark Found"
        if tag in variants: return variants[tag], f"Tag ({tag})"
        if "DEFAULT" in variants: return variants["DEFAULT"], "Fallback to Default"
        return min(variants.values()), "Conservative Min"

    def find_siblings(self, cn_prefix):
        prefix = str(cn_prefix)[:4]
        matches = [c for c in self.cn_list if c.startswith(prefix)]
        return sorted(matches)

class DefaultValueDatabase:
    def __init__(self, csv_path):
        self.data = []
        self.cn_lookup = {}  # {cn_code: description} for search
        if not os.path.exists(csv_path):
            st.error(f"CRITICAL: '{csv_path}' missing.")
            return

        try:
            df = pd.read_csv(csv_path, sep=';', encoding='latin-1', dtype=str, on_bad_lines='skip')
            df.columns = df.columns.str.strip()

            col_cn = next((c for c in df.columns if 'CN Code' in c), 'Product CN Code')
            col_country = next((c for c in df.columns if 'Country' in c), 'Country')
            col_route = next((c for c in df.columns if 'route' in c.lower()), df.columns[-1])
            col_desc = next((c for c in df.columns if 'Description' in c), 'Description')

            cols_year = {
                2026: next((c for c in df.columns if '2026' in c), None),
                2027: next((c for c in df.columns if '2027' in c), None),
                2028: next((c for c in df.columns if '2028' in c), None)
            }

            for _, row in df.iterrows():
                try:
                    route_raw = str(row[col_route])
                    route_match = re.search(r'\(([A-Z])\)', route_raw)
                    route_tag = route_match.group(1) if route_match else "UNKNOWN"

                    cn_code = ''.join(filter(str.isdigit, str(row[col_cn])))
                    description = str(row[col_desc]).strip() if col_desc in row else ""

                    entry = {
                        'country': str(row[col_country]).strip().lower(),
                        'cn_code': cn_code,
                        'description': description,
                        'route_tag': route_tag
                    }
                    for year, col in cols_year.items():
                        if col:
                            match = re.search(r'([0-9]+[.,][0-9]+|[0-9]+)', str(row[col]))
                            entry[year] = float(match.group(0).replace(',', '.')) if match else 0.0
                    self.data.append(entry)

                    # Build CN lookup for search (store unique CN + description pairs)
                    if cn_code and cn_code not in self.cn_lookup and description:
                        self.cn_lookup[cn_code] = description
                except: continue
        except Exception as e:
            st.error(f"Default DB Error: {e}")

    def search_cn_codes(self, query, limit=15):
        """Search CN codes and descriptions by prefix or keyword."""
        if not query or len(query) < 2:
            return []

        query_lower = query.lower().strip()
        results = []

        for cn_code, description in self.cn_lookup.items():
            # Match CN code prefix or description keyword
            if cn_code.startswith(query) or query_lower in description.lower():
                results.append((cn_code, description))
                if len(results) >= limit:
                    break

        # Sort by CN code
        return sorted(results, key=lambda x: x[0])[:limit]

    def get_default_see(self, cn, country, year):
        target_cn = str(cn).strip()
        target_country = str(country).strip().lower()
        lookup_year = min(year, 2028)
        
        def search(c, cntry):
            for row in self.data:
                if row['cn_code'] == c and row['country'] == cntry:
                    return row.get(lookup_year, 0.0), row['route_tag']
            return 0.0, None

        val, tag = search(target_cn, target_country)
        if val > 0: return val, tag, "Exact Match"
        if len(target_cn) >= 6:
            val, tag = search(target_cn[:6], target_country)
            if val > 0: return val, tag, "6-digit Parent"
        if len(target_cn) >= 4:
            val, tag = search(target_cn[:4], target_country)
            if val > 0: return val, tag, "4-digit Parent"
            
        val, tag = search(target_cn, "other countries and territories")
        return val, tag, "Global Fallback" if val > 0 else "Not Found"

def calculate_liability_logic(year, cn, qty, see, price, route_tag, db_bench, yield_factor):
    reduction_rate = CBAM_PHASE_IN_REDUCTION.get(year, 1.0)
    benchmark, note = db_bench.get_benchmark(cn, route_tag)
    
    # FREE ALLOCATION LOGIC
    # Adjusted Quantity = Quantity * Yield (e.g. 1000 Screws * 1.1 = 1100 Steel)
    # Free Alloc = Benchmark * Adjusted_Quantity * Free_Factor
    
    adjusted_quantity = qty * yield_factor
    free_alloc_factor = max(0.0, 1.0 - reduction_rate)
    
    total_free_alloc = benchmark * adjusted_quantity * free_alloc_factor
    
    # LIABILITY LOGIC
    total_embedded = see * qty # Emissions based on actual import mass
    
    payable = max(0.0, total_embedded - total_free_alloc)
    cost = payable * price
    
    return [benchmark, note, f"{reduction_rate*100}%", f"{free_alloc_factor*100:.1f}%", payable, cost, total_free_alloc]

# ==========================================
# 3. UI
# ==========================================
st.set_page_config(page_title="CBAM Cost Estimator", page_icon="💶", layout="wide")
st.markdown("""
<style>
    .product-badge {
        background: linear-gradient(135deg, #1a3d2b 0%, #1d7145 60%, #2ecc71 100%);
        color: #ffffff;
        padding: 14px 18px;
        border-radius: 12px;
        margin: 8px 0 4px 0;
        box-shadow: 0 4px 12px rgba(29,113,69,0.22);
    }
    .product-badge b { color: #a8edbc; font-size: 16px; letter-spacing: 1px; }
    .product-badge small { color: rgba(255,255,255,0.82); font-size: 13px; }

    .result-card {
        background: linear-gradient(145deg, #1a3d2b 0%, #1d7145 55%, #2ecc71 100%);
        border-radius: 20px;
        padding: 32px 28px;
        text-align: center;
        box-shadow: 0 8px 28px rgba(29,113,69,0.30), 0 2px 8px rgba(0,0,0,0.12);
    }

    .info-card {
        background: #ffffff;
        padding: 14px 18px;
        border-radius: 12px;
        border-left: 4px solid #34c759;
        margin: 8px 0;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def load_data(): return BenchmarkDatabase(BENCHMARK_FILE), DefaultValueDatabase(DEFAULTS_FILE)

try: db_bench, db_defaults = load_data()
except: st.stop()

# Build full product list for selectbox
@st.cache_data
def get_product_options():
    options = []
    for cn, desc in sorted(db_defaults.cn_lookup.items()):
        options.append(f"{cn} - {desc}")
    return options

product_options = get_product_options()

st.title("CBAM Financial Estimator")

# Sidebar - cleaner
with st.sidebar:
    st.markdown("### Settings")
    reporting_year = st.selectbox("Year", [2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033, 2034])

    if reporting_year == 2026:
        st.markdown("**Quarter of import**")
        quarter_label = st.selectbox(
            "Quarter",
            list(CBAM_QUARTERLY_PRICES_2026.keys()),
            label_visibility="collapsed"
        )
        q_data = CBAM_QUARTERLY_PRICES_2026[quarter_label]
        q_price = q_data["price"]

        if q_price is not None:
            st.success(f"Official price: **€{q_price:.2f}/tCO2**")
            ets_price = st.number_input(
                "CBAM Certificate Price (€/tCO2)",
                value=q_price, step=1.0, format="%.2f"
            )
        else:
            st.warning(f"Price not yet published (expected {q_data['published']})")
            ets_price = st.number_input(
                "CBAM Certificate Price (€/tCO2)",
                value=85.0, step=1.0, format="%.2f"
            )

        with st.expander("About quarterly prices"):
            st.markdown(
                "The CBAM certificate price is calculated by the Commission during the "
                "first calendar week after each quarter ends, based on EU ETS auction data. "
                "Each price applies to certificates for goods **imported during that quarter**.\n\n"
                "| Quarter | Publication date | Price (€) |\n"
                "|---------|-----------------|----------:|\n"
                + "\n".join(
                    f"| {q} | {d['published']} | {'€{:.2f}'.format(d['price']) if d['price'] else '—'} |"
                    for q, d in CBAM_QUARTERLY_PRICES_2026.items()
                )
                + "\n\n*Source: Article 20, Regulation (EU) 2023/956*"
            )
    else:
        ets_price = st.number_input("ETS Price (€/tCO2)", value=85.0, step=5.0, format="%.2f")
        st.caption("[View live EU ETS price](https://tradingeconomics.com/commodity/carbon)")

    st.markdown("---")
    st.caption(f"Phase-in rate: {CBAM_PHASE_IN_REDUCTION.get(reporting_year, 1.0)*100:.1f}%")

col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    # === PRODUCT SELECTION ===
    st.markdown("### Product")

    # Single unified search/select
    selected_product = st.selectbox(
        "Search or select product",
        options=product_options,
        index=0,
        placeholder="Type to search by CN code or name...",
        help="Start typing a CN code (e.g., 7201) or product name"
    )
    cn_code = selected_product.split(" - ")[0] if selected_product else "72131000"
    product_name = selected_product.split(" - ", 1)[1] if " - " in selected_product else ""

    # Show selected product clearly
    if product_name:
        st.markdown(f'<div class="product-badge"><b style="font-size:15px;letter-spacing:-0.25px;">{cn_code}</b><br><small style="color:#b0b4ba;font-size:13px;">{product_name}</small></div>', unsafe_allow_html=True)

    # === IMPORT DETAILS ===
    st.markdown("### Import Details")
    col_a, col_b = st.columns(2)
    with col_a:
        # Country list
        if db_defaults.data:
            unique = set(d['country'].title() for d in db_defaults.data)
            countries = sorted(list(unique))
            priority = ['China', 'India', 'Turkey', 'Vietnam', 'South Korea', 'United Kingdom']
            final_list = [c for c in priority if c in countries] + [c for c in countries if c not in priority]
        else:
            final_list = ["China", "India", "Other"]
        country_origin = st.selectbox("Origin Country", final_list)
    with col_b:
        quantity = st.number_input("Quantity (tonnes)", value=1000.0, step=100.0, format="%.0f")

    # === EMISSIONS ===
    st.markdown("### Emissions Data")

    # Get default value automatically
    val, def_route, match_type = db_defaults.get_default_see(cn_code, country_origin, reporting_year)

    # Initialize defaults
    route_tag = "DEFAULT"
    spec_em = 2.0
    final_benchmark_cn = cn_code
    yield_factor = get_default_yield(cn_code)

    use_default = st.toggle("Use default emission values", value=(val > 0), disabled=(val <= 0))

    if use_default and val > 0:
        spec_em = val
        st.success(f"Using default: **{val:.3f}** tCO2/t ({match_type})")
        if def_route and def_route != "UNKNOWN":
            route_tag = def_route
            st.caption(f"Production route: {route_tag} - {ROUTE_DESCRIPTIONS.get(route_tag, '')}")
    else:
        spec_em = st.number_input("Specific Emissions (tCO2/t)", value=2.0, min_value=0.01, step=0.1, format="%.3f")
        if val <= 0:
            st.warning("No default available for this product/country combination")

        # Route selection for manual entry
        valid_tags = []
        if cn_code in db_bench.data:
            valid_tags = list(db_bench.data[cn_code].keys())
        elif len(cn_code) >= 6 and cn_code[:6] in db_bench.data:
            valid_tags = list(db_bench.data[cn_code[:6]].keys())
        elif len(cn_code) >= 4 and cn_code[:4] in db_bench.data:
            valid_tags = list(db_bench.data[cn_code[:4]].keys())

        if valid_tags:
            opts = [f"{t} - {ROUTE_DESCRIPTIONS.get(t, 'Unknown')}" for t in valid_tags]
        else:
            opts = [f"{t} - {d}" for t, d in list(ROUTE_DESCRIPTIONS.items())[:6]]

        sel_route = st.selectbox("Production Route", opts)
        route_tag = sel_route.split(" - ")[0]

    # === ADVANCED SETTINGS ===
    with st.expander("Advanced Settings"):
        # Benchmark logic
        test_bench, bench_note = db_bench.get_benchmark(cn_code, route_tag)

        if test_bench == 0:
            siblings = db_bench.find_siblings(cn_code)
            if siblings:
                st.info(f"No exact benchmark for {cn_code}. Select related product:")
                selected_sibling = st.selectbox("Benchmark from:", siblings)
                final_benchmark_cn = selected_sibling
            else:
                proxies = {"7207 - Crude Steel": "7207", "7201 - Pig Iron": "7201",
                           "7601 - Aluminium": "7601", "2523 - Cement": "2523"}
                proxy_display = st.selectbox("Use proxy benchmark:", list(proxies.keys()))
                final_benchmark_cn = proxies[proxy_display]
        else:
            st.caption(f"Benchmark: {test_bench:.3f} tCO2/t ({bench_note})")

        # Yield factor
        yield_factor = st.number_input("Yield Factor", value=yield_factor, step=0.05, min_value=0.1,
                                        help="1.0 for raw materials, 1.1 for manufactured articles")
        if get_default_yield(cn_code) > 1.0:
            st.caption("Adjusted for manufacturing loss (73xx/76xx goods)")

# === RESULTS - Auto-calculate ===
with col_right:
    st.markdown("### Cost Estimate")

    if spec_em > 0 and quantity > 0:
        res = calculate_liability_logic(reporting_year, final_benchmark_cn, quantity, spec_em, ets_price, route_tag, db_bench, yield_factor)

        benchmark_val = res[0]
        total_free = res[6]
        payable = res[4]
        cost = res[5]

        # Main result card
        st.markdown(f"""
        <div class="result-card">
            <div style="font-size:11px;font-weight:600;color:rgba(255,255,255,0.65);letter-spacing:1px;text-transform:uppercase;">Estimated CBAM Cost</div>
            <div style="font-size:54px;font-weight:800;color:#ffffff;letter-spacing:-2.5px;line-height:1.05;margin:10px 0;text-shadow:0 2px 12px rgba(0,0,0,0.18);">€{cost:,.0f}</div>
            <div style="font-size:14px;color:rgba(255,255,255,0.72);font-weight:500;letter-spacing:0.1px;">€{cost/quantity:.2f} per tonne</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("###")

        # Key metrics
        c1, c2, c3 = st.columns(3)
        c1.metric("Payable CO2", f"{payable:,.0f} t")
        c2.metric("Benchmark", f"{benchmark_val:.3f}")
        c3.metric("Free Alloc.", f"{res[3]}")

        # Calculation breakdown
        with st.expander("View calculation breakdown", expanded=False):
            st.markdown(f"""
            **1. Embedded Emissions**
            {quantity:,.0f} tonnes × {spec_em:.3f} tCO2/t = **{quantity*spec_em:,.1f} tCO2**

            **2. Free Allocation Credit**
            - Benchmark: {benchmark_val:.3f} tCO2/t
            - Adjusted quantity: {quantity*yield_factor:,.0f} t
            - Free rate: {res[3]}
            - **Credit: {total_free:,.1f} tCO2**

            **3. Net Liability**
            {quantity*spec_em:,.1f} - {total_free:,.1f} = **{payable:,.1f} tCO2**

            **4. Cost**
            {payable:,.1f} tCO2 × €{ets_price:.0f} = **€{cost:,.2f}**
            """)

        # Cost projection chart
        st.markdown("---")
        st.markdown("#### Cost Projection (2026-2034)")

        # Inflation slider
        inflation_rate = st.slider(
            "Annual ETS Price Inflation %",
            min_value=-10.0, max_value=20.0, value=0.0, step=0.5,
            help="Adjust expected annual change in ETS price"
        )

        # Calculate costs for all years with inflation
        years = list(range(2026, 2035))
        costs = []
        ets_prices_projected = []

        for yr in years:
            # Apply inflation from base year (reporting_year)
            years_diff = yr - reporting_year
            projected_ets = ets_price * ((1 + inflation_rate / 100) ** years_diff)
            ets_prices_projected.append(projected_ets)

            r = calculate_liability_logic(yr, final_benchmark_cn, quantity, spec_em, projected_ets, route_tag, db_bench, yield_factor)
            costs.append(r[5])

        # Create Plotly chart
        fig = go.Figure()

        # Cost line
        fig.add_trace(go.Scatter(
            x=years, y=costs,
            mode='lines+markers',
            name='Estimated Cost',
            line=dict(color='#1d7145', width=3),
            marker=dict(size=7, color='#34c759', line=dict(color='#1d7145', width=2)),
            hovertemplate='<b>%{x}</b><br>Cost: €%{y:,.0f}<extra></extra>'
        ))

        # Highlight current year
        current_idx = years.index(reporting_year)
        fig.add_trace(go.Scatter(
            x=[reporting_year], y=[costs[current_idx]],
            mode='markers',
            name=f'Selected Year ({reporting_year})',
            marker=dict(color='#ff9f0a', size=14, symbol='star'),
            hovertemplate=f'<b>{reporting_year}</b><br>Cost: €{costs[current_idx]:,.0f}<extra></extra>'
        ))

        fig.update_layout(
            xaxis_title='Year',
            yaxis_title='Estimated Cost (€)',
            xaxis=dict(tickmode='linear', tick0=2026, dtick=1, gridcolor='rgba(0,0,0,0.05)', color='#6e6e73'),
            yaxis=dict(tickformat=',.0f', tickprefix='€', gridcolor='rgba(0,0,0,0.05)', color='#6e6e73'),
            hovermode='x unified',
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1, font=dict(color='#3a3a3c')),
            margin=dict(l=20, r=20, t=40, b=20),
            height=320,
            font=dict(family='-apple-system, Inter, sans-serif', color='#3a3a3c'),
        )

        st.plotly_chart(fig, use_container_width=True)

        # Show projected ETS prices if inflation is set
        if inflation_rate != 0:
            st.caption(f"Projected ETS prices with {inflation_rate:+.1f}% annual change: " +
                      ", ".join([f"{yr}: €{p:.0f}" for yr, p in zip(years[::2], ets_prices_projected[::2])]))

    else:
        st.info("Enter product details to see cost estimate")
