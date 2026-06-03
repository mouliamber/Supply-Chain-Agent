import streamlit as st
import pandas as pd

# Constants for validation
REQUIRED_COLUMNS = [
    "po_id",
    "supplier_name",
    "order_value",
    "expected_delivery_date",
    "shipment_status",
    "supplier_previous_delays"
]

ALLOWED_STATUSES = [
    "Not Started",
    "In Transit",
    "Delivered",
    "Delayed"
]

def load_data(uploaded_file):
    """Loads uploaded file into a pandas DataFrame."""
    try:
        if uploaded_file.name.endswith('.csv'):
            return pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith(('.xls', '.xlsx')):
            return pd.read_excel(uploaded_file)
        else:
            st.error("Unsupported file format. Please upload a CSV or Excel file.")
            return None
    except Exception as e:
        st.error(f"Error reading file: {e}")
        return None

def validate_data(df):
    """Validates the dataframe against required schema and rules."""
    
    # 1. Validate required columns
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        st.error(f"**Missing Required Column(s):**\n\n{', '.join(missing_columns)}")
        return False

    # 2. Validate shipment status values
    invalid_statuses = df[~df['shipment_status'].isin(ALLOWED_STATUSES)]['shipment_status'].dropna().unique()
    if len(invalid_statuses) > 0:
        st.error(f"**Invalid shipment status found:**\n\n{', '.join(invalid_statuses)}\n\n**Allowed values:**\n\n{', '.join(ALLOWED_STATUSES)}")
        return False

    # 3. Validate expected_delivery_date
    try:
        # Attempt to convert to datetime; coerce errors to NaT to find invalid dates
        parsed_dates = pd.to_datetime(df['expected_delivery_date'], errors='coerce')
        
        # If there were non-null values originally that became NaT, they are invalid dates
        original_notnull = df['expected_delivery_date'].notna()
        invalid_dates_mask = original_notnull & parsed_dates.isna()
        
        if invalid_dates_mask.any():
            st.error("**Invalid delivery date detected in expected_delivery_date column.**")
            return False
            
        # Optional: Replace the column with parsed datetime objects for future processing
        df['expected_delivery_date'] = parsed_dates
        
    except Exception:
        st.error("**Invalid delivery date detected in expected_delivery_date column.**")
        return False

    return True

def evaluate_po(row, today):
    """Evaluates a single purchase order row against risk rules."""
    score = 0
    reasons = []
    
    expected_date = row['expected_delivery_date']
    status = row['shipment_status']
    delays = row['supplier_previous_delays']
    value = row['order_value']
    
    # Calculate days until delivery
    days_until_delivery = (expected_date - today).days if pd.notnull(expected_date) else None
    
    # Rule 1 — Delivery Date Missed
    if pd.notnull(expected_date) and today > expected_date:
        score += 40
        reasons.append("Delivery date missed")
        
    # Rule 2 — Shipment Not Started
    if status == "Not Started":
        score += 30
        reasons.append("Shipment not started")
        
    # Rule 3 — Supplier Has Repeated Delays
    if pd.notnull(delays) and delays >= 3:
        score += 20
        reasons.append("Supplier has history of delays")
        
    # Rule 4 — High Value Order
    if pd.notnull(value) and value > 100000:
        score += 10
        reasons.append("High value order")
        
    # Bonus Rule — Delivery Date Approaching
    if pd.notnull(expected_date) and status == "Not Started" and today <= expected_date and days_until_delivery <= 3:
        score += 25
        reasons.append("Delivery date approaching but shipment not started")
        
    return score, "; ".join(reasons)

def calculate_risk(df):
    """Evaluates each purchase order against risk rules and returns updated DataFrame."""
    today = pd.Timestamp.today().normalize()
    
    # Apply evaluation function row by row
    results = df.apply(lambda row: evaluate_po(row, today), axis=1)
    
    # Unpack results into new columns
    df['risk_score'] = [res[0] for res in results]
    df['risk_reasons'] = [res[1] for res in results]
    
    return df

def get_risk_level(score):
    """Determines the risk classification based on risk score."""
    if score >= 60:
        return "High"
    elif score >= 30:
        return "Medium"
    else:
        return "Low"

def get_recommendation(risk_level, delays):
    """Determines the recommended action based on risk level and delay history."""
    if risk_level == "High" and pd.notnull(delays) and delays >= 3:
        return "Consider Alternate Supplier"
    elif risk_level == "High":
        return "Escalate To Procurement Manager"
    elif risk_level == "Medium":
        return "Follow Up With Supplier"
    else:
        return "Continue Monitoring"

def classify_and_recommend(df):
    """Applies risk classification and recommendations to the DataFrame."""
    df['risk_level'] = df['risk_score'].apply(get_risk_level)
    df['recommendation'] = df.apply(
        lambda row: get_recommendation(row['risk_level'], row['supplier_previous_delays']),
        axis=1
    )
    return df

def render_dashboard(df):
    """Renders the Streamlit dashboard."""
    st.markdown("---")
    
    # Section 1 — Risk Summary Cards
    st.subheader("Risk Summary Cards")
    
    total_orders = len(df)
    low_risk = len(df[df['risk_level'] == 'Low'])
    medium_risk = len(df[df['risk_level'] == 'Medium'])
    high_risk = len(df[df['risk_level'] == 'High'])
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Orders", total_orders)
    with col2:
        st.metric("Low Risk Orders", low_risk)
    with col3:
        st.metric("Medium Risk Orders", medium_risk)
    with col4:
        st.metric("High Risk Orders", high_risk)
        
    st.markdown("---")
        
    # Section 2 — Risk Distribution Chart
    st.subheader("Risk Distribution Chart")
    risk_counts = df['risk_level'].value_counts()
    risk_counts = risk_counts.reindex(['Low', 'Medium', 'High']).fillna(0)
    st.bar_chart(risk_counts)
    
    st.markdown("---")
    
    # Section 3 — High Risk Orders
    st.subheader("High Risk Orders")
    high_risk_df = df[df['risk_level'] == 'High'].sort_values(by='risk_score', ascending=False)
    if not high_risk_df.empty:
        st.dataframe(high_risk_df[['po_id', 'supplier_name', 'risk_score', 'recommendation']], use_container_width=True)
    else:
        st.info("No high risk orders found.")
        
    st.markdown("---")
        
    # Section 4 — Full Analysis Table
    st.subheader("Full Analysis Table")
    st.dataframe(df[['po_id', 'supplier_name', 'risk_score', 'risk_level', 'risk_reasons', 'recommendation']], use_container_width=True)

def main():
    st.set_page_config(page_title="Supplier Delay Risk Monitor", page_icon="📦")
    
    st.title("Supplier Delay Risk Monitor")
    st.markdown("Upload your purchase order data to analyze potential supplier delivery risks.")

    uploaded_file = st.file_uploader("Upload Purchase Orders (CSV or Excel)", type=["csv", "xlsx", "xls"])

    if uploaded_file is not None:
        df = load_data(uploaded_file)
        
        if df is not None:
            is_valid = validate_data(df)
            
            if is_valid:
                df = calculate_risk(df)
                df = classify_and_recommend(df)
                st.success(f"**{len(df)} Orders Analyzed Successfully**\n\nValidation, risk calculation, and recommendations complete.")
                render_dashboard(df)

if __name__ == "__main__":
    main()
