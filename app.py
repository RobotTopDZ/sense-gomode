import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import re

# --- PAGE CONFIG ---
st.set_page_config(page_title="GoMode Dashboard", layout="wide", page_icon="🚚")

# --- STYLE ---
st.markdown("""
    <style>
    body {
        background-color: #0b0c0c;
        color: #00ff88;
    }
    .css-1d391kg, .css-1avcm0n, .st-bx, .st-c7, .st-ci, .st-ch {
        background-color: #0f1117 !important;
        color: #00ff88 !important;
        border-color: #00ff88 !important;
    }
    .stDataFrame tbody tr:hover {
        background-color: #003322 !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- LOAD DATA ---
@st.cache_data
def load_data():
    df = pd.read_csv("merged_yalidine.csv")
    # Parse all relevant date columns using exact names
    df['date_creation'] = pd.to_datetime(df['date_creation'], errors='coerce')
    df['date_expedition'] = pd.to_datetime(df['date_expedition'], errors='coerce')
    df['date_last_status'] = pd.to_datetime(df['date_last_status'], errors='coerce')
    if 'Date de commande' in df.columns:
        df['date_commande'] = pd.to_datetime(df['Date de commande'], errors='coerce')
    else:
        df['date_commande'] = pd.NaT
    # New intervals using date_commande
    df['commande_to_creation_days'] = (df['date_creation'] - df['date_commande']).dt.days
    df['commande_to_expedition_days'] = (df['date_expedition'] - df['date_commande']).dt.days
    df['commande_to_last_status_days'] = (df['date_last_status'] - df['date_commande']).dt.days
    df['delivered'] = df['last_status'].str.lower().str.contains("livré")
    df['returned'] = df['last_status'].str.lower().str.contains("retour")
    df['delivery_delay_days'] = (df['date_last_status'] - df['date_expedition']).dt.days
    df['processing_time_days'] = (df['date_expedition'] - df['date_creation']).dt.days
    df['revenue'] = df['Montant total de la commande'].fillna(0)
    df['lost_revenue'] = df['revenue'].where(df['returned'], 0)
    df['success_revenue'] = df['revenue'].where(df['delivered'], 0)
    df['has_recouvrement'] = df['has_recouvrement'].fillna(0)
    return df

df = load_data()

# --- DEBUG: Show columns ---
st.sidebar.write('Columns in DataFrame:')
st.sidebar.write(list(df.columns))

# --- TITLE ---
st.title("🚛 GoMode COD Dashboard")

# --- GLOBAL KPIs ---
st.header("📈 Global KPIs")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Orders", f"{len(df):,}")
col2.metric("Success Rate", f"{df['delivered'].mean():.1%}")
col3.metric("Return Rate", f"{df['returned'].mean():.1%}")
col4.metric("Avg Delivery Delay", f"{df['delivery_delay_days'].mean():.1f} days")

# --- NEW TIME KPIs (including Date de commande intervals) ---
colA, colB, colC, colD = st.columns(4)
colA.metric("Avg Processing Time", f"{df['processing_time_days'].mean():.1f} days")
colB.metric("Avg Shipping Time", f"{df['delivery_delay_days'].mean():.1f} days")
colC.metric("Avg Cmd→Expedition", f"{df['commande_to_expedition_days'].mean():.1f} days")
colD.metric("Avg Cmd→Last Status", f"{df['commande_to_last_status_days'].mean():.1f} days")

# --- TIME INTERVAL DISTRIBUTIONS (including Date de commande intervals) ---
st.subheader("⏱️ Time Intervals Distribution")
time_cols = [
    ("Processing Time (Creation → Expedition)", 'processing_time_days', df['processing_time_days'].dropna()),
    ("Shipping Time (Expedition → Last Status)", 'delivery_delay_days', df['delivery_delay_days'].dropna()),
    ("Cmd→Creation", 'commande_to_creation_days', df['commande_to_creation_days'].dropna()),
    ("Cmd→Expedition", 'commande_to_expedition_days', df['commande_to_expedition_days'].dropna()),
    ("Cmd→Last Status", 'commande_to_last_status_days', df['commande_to_last_status_days'].dropna()),
]
seen = set()
unique_time_cols = []
for label, col, data in time_cols:
    if col not in seen and col in df.columns and data is not None:
        unique_time_cols.append((label, col, data))
        seen.add(col)
for label, col, data in unique_time_cols:
    st.write(f"**{label}:**")
    if not data.empty:
        st.plotly_chart(px.histogram(data, x=col, nbins=30, title=label, color_discrete_sequence=["#00ff88"]), key=f"hist_{col}_{label}")
    else:
        st.warning(f"No valid data for {label}.")

# --- BOTTLENECKS & DELAYS ---
st.subheader("🚦 Bottlenecks & Delays")
# Robustly choose the sort column
if 'total_fulfillment_days' in df.columns:
    slow_orders = df.sort_values('total_fulfillment_days', ascending=False).head(10)
else:
    slow_orders = df.sort_values('delivery_delay_days', ascending=False).head(10)
desired_cols = [
    'order_id', 'from_wilaya_name', 'to_wilaya_name', 'processing_time_days',
    'delivery_delay_days', 'commande_to_creation_days', 'commande_to_expedition_days', 'commande_to_last_status_days',
    'last_to_final_days', 'total_fulfillment_days', 'last_status', 'date_creation', 'date_expedition', 'date_last_status', 'date_commande', 'date_etat_fin'
]
existing_cols = [col for col in desired_cols if col in slow_orders.columns]
if existing_cols:
    st.dataframe(slow_orders[existing_cols])
else:
    st.info('No relevant columns found to display bottlenecks and delays.')

# --- INSIGHTS & RECOMMENDATIONS ---
st.subheader("💡 Insights & Recommendations")
insights = []
if df['processing_time_days'].mean() > 1:
    insights.append("Order processing is slow. Consider optimizing warehouse or admin processes.")
if df['delivery_delay_days'].mean() > 2:
    insights.append("Shipping times are high. Investigate courier or route efficiency.")
if not insights:
    insights.append("No major bottlenecks detected. Keep monitoring for improvements!")
for i, insight in enumerate(insights, 1):
    st.markdown(f"**{i}. {insight}**")

# --- REVENUE KPIs ---
st.subheader("💰 COD Revenue Analysis")
col5, col6, col7 = st.columns(3)
col5.metric("Total COD Revenue", f"{df['success_revenue'].sum():,.0f} DA")
col6.metric("Lost Revenue (Returned)", f"{df['lost_revenue'].sum():,.0f} DA")
col7.metric("Recouvrement Rate", f"{df['has_recouvrement'].mean():.1%}")

# --- ORDERS BY WILAYA ---
st.subheader("📍 Orders & Revenue by Wilaya")
wilaya_stats = df.groupby("to_wilaya_name").agg(
    orders=("order_id", "count"),
    revenue=("success_revenue", "sum"),
    return_rate=("returned", "mean")
).reset_index()

fig1 = px.bar(wilaya_stats.sort_values("orders", ascending=False), x="to_wilaya_name", y="orders",
              title="Orders per Wilaya", color_discrete_sequence=["#00ff88"])
fig2 = px.bar(wilaya_stats.sort_values("revenue", ascending=False), x="to_wilaya_name", y="revenue",
              title="Revenue per Wilaya", color_discrete_sequence=["#00ff88"])
st.plotly_chart(fig1, use_container_width=True)
st.plotly_chart(fig2, use_container_width=True)

# --- TOP RETURNED PRODUCTS ---
st.subheader("📦 Most Returned Products")
# Robustly detect the product column
def get_product_col(df):
    for col in df.columns:
        norm = re.sub(r"[’']", "'", col.strip().lower())
        if norm == "nom de l'élément":
            return col
    return None
product_col = get_product_col(df)
if product_col:
    top_returns = df[df['returned']].groupby(product_col).size().sort_values(ascending=False).head(10)
    st.dataframe(top_returns.rename("Returned Orders"))
else:
    st.warning("Column 'Nom de l'élément' not found in data.")

# --- AVERAGE DELIVERY DELAY BY HUB ---
st.subheader("⏳ Avg Delivery Delay by Hub")
hub_delays = df.groupby("stopdesk_name").agg(avg_delay=("delivery_delay_days", "mean")).sort_values("avg_delay", ascending=False)
st.dataframe(hub_delays.style.format({"avg_delay": "{:.1f} days"}))

# --- CASH COLLECTION (RECOUVREMENT) RATE BY WILAYA ---
st.subheader("🧾 Cash Collection by Wilaya")
rec_rate = df.groupby("to_wilaya_name")["has_recouvrement"].mean().sort_values(ascending=False)
st.dataframe(rec_rate.rename("Recouvrement Rate").map(lambda x: f"{x:.1%}"))

# --- HIGH-RISK AREAS ---
st.subheader("🚨 High-Risk Areas")
risk_df = df.groupby("to_wilaya_name").agg(
    return_rate=("returned", "mean"),
    rec_rate=("has_recouvrement", "mean"),
    orders=("order_id", "count")
).query("orders > 10").sort_values("return_rate", ascending=False)
st.dataframe(risk_df)

# --- TIME SERIES ANALYSIS ---
st.subheader("📆 Orders Over Time")
orders_time = df.groupby(df["date_creation"].dt.date).size()
fig_time = px.line(x=orders_time.index, y=orders_time.values, labels={"x": "Date", "y": "Orders"}, title="Orders Over Time",
                   markers=True, color_discrete_sequence=["#00ff88"])
st.plotly_chart(fig_time, use_container_width=True, key="orders_time")

# --- PRICE vs DECLARED VALUE OUTLIERS ---
st.subheader("🧐 Product Price vs. Declared Value")
if 'Prix du produit' in df.columns and 'declared_value' in df.columns:
    valid_price = df[df['Prix du produit'].notna() & df['declared_value'].notna()]
    fig_scatter = px.scatter(valid_price, x="Prix du produit", y="declared_value",
                             hover_data=[product_col, "order_id"] if product_col else ["order_id"],
                             title="Product Price vs. Declared Value",
                             color_discrete_sequence=["#00ff88"])
    st.plotly_chart(fig_scatter, use_container_width=True, key="price_declared")
else:
    st.warning("'Prix du produit' or 'declared_value' column not found.")

# --- FOOTER ---
st.markdown("---")
st.markdown("🔍 Built for GoMode logistics by [Your Team/Name] — powered by Streamlit 💚🖤")

# --- NEW ANALYTICS & INSIGHTS ---
st.header("🔎 Advanced Time Analysis & Insights")
# Warn if many NaNs in new columns
for col in ["processing_time_days", "delivery_delay_days"]:
    if col in df.columns:
        if df[col].isna().mean() > 0.2:
            st.warning(f"More than 20% missing values in {col}. Check your date columns in the CSV.")

# --- NEW TIME KPIs ---
colA, colB, colC, colD = st.columns(4)
colA.metric("Avg Processing Time", f"{df['processing_time_days'].mean():.1f} days")
colB.metric("Avg Shipping Time", f"{df['delivery_delay_days'].mean():.1f} days")

# --- TIME INTERVAL DISTRIBUTIONS ---
st.subheader("⏱️ Time Intervals Distribution")
time_cols = [
    ("Processing Time (Creation → Expedition)", 'processing_time_days', df['processing_time_days'].dropna()),
    ("Shipping Time (Expedition → Last Status)", 'delivery_delay_days', df['delivery_delay_days'].dropna()),
]
for label, col, data in time_cols:
    st.write(f"**{label}:**")
    if not data.empty:
        st.plotly_chart(px.histogram(data, x=col, nbins=30, title=label, color_discrete_sequence=["#00ff88"]), key=f"hist_{col}")
    else:
        st.warning(f"No valid data for {label}.")

# --- BOTTLENECKS & DELAYS ---
st.subheader("🚦 Bottlenecks & Delays")
slow_orders = df.sort_values('delivery_delay_days', ascending=False).head(10)
st.dataframe(slow_orders[[
    'order_id', 'from_wilaya_name', 'to_wilaya_name', 'processing_time_days', 'delivery_delay_days', 'commande_to_creation_days', 'commande_to_expedition_days', 'commande_to_last_status_days',
    'last_status', 'date_creation', 'date_expedition', 'date_last_status', 'date_commande'
]])

# --- INSIGHTS & RECOMMENDATIONS ---
st.subheader("💡 Insights & Recommendations")
insights = []
if df['processing_time_days'].mean() > 1:
    insights.append("Order processing is slow. Consider optimizing warehouse or admin processes.")
if df['delivery_delay_days'].mean() > 2:
    insights.append("Shipping times are high. Investigate courier or route efficiency.")
if not insights:
    insights.append("No major bottlenecks detected. Keep monitoring for improvements!")
for i, insight in enumerate(insights, 1):
    st.markdown(f"**{i}. {insight}**")

