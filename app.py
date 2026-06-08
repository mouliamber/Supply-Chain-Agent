import streamlit as st
import pandas as pd
import re
import os
import json
from dotenv import load_dotenv
from google import genai

# Load environment variables from .env file if it exists
load_dotenv()
from google.genai import types
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

class ColumnMapEntry(BaseModel):
    uploaded_column: str
    internal_schema_field: str

class ColumnMappingResult(BaseModel):
    mapped_columns: list[ColumnMapEntry] = Field(description="List mapping uploaded column names to internal schema names")
    missing_required_fields: list[str] = Field(description="List of required internal fields that are missing from the uploaded columns")
    ignored_columns: list[str] = Field(description="List of uploaded column names that do not map to any required internal fields")

class StatusMapEntry(BaseModel):
    uploaded_status: str
    allowed_status: str

class StatusNormalizationResult(BaseModel):
    status_mapping: list[StatusMapEntry] = Field(description="List mapping original status strings to allowed statuses")

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

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_llm_mapping(headers: list[str]) -> ColumnMappingResult:
    api_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    You are an expert Data Engineer specializing in supply chain and procurement data integration.
    Your task is to accurately map columns from a raw, uploaded dataset to our application's strictly defined internal schema.
    
    Internal Schema fields required and their definitions:
    - `po_id`: The unique identifier for the purchase order (e.g., PO Number, Document ID).
    - `supplier_name`: The name of the vendor, merchant, or supplier organization.
    - `order_value`: The total monetary value or amount of the order.
    - `expected_delivery_date`: The targeted or promised arrival date for the shipment (e.g., ETA, Delivery Deadline).
    - `shipment_status`: The current logistics state of the order (e.g., Transit status, Stage).
    - `supplier_previous_delays`: A numerical count of historical delays associated with this supplier.
    
    Uploaded columns found in the file:
    {json.dumps(headers)}
    
    Instructions:
    1. Map the uploaded columns to the internal schema based on deep semantic meaning and supply chain domain knowledge.
    2. Handle abbreviations (e.g., 'vndr' -> supplier_name, 'val' -> order_value).
    3. If an internal field is not represented in the uploaded columns, you MUST include it in the `missing_required_fields` list. Do not force a mapping if it's incorrect.
    4. If an uploaded column is irrelevant to the internal schema, include it in `ignored_columns`.
    5. Output strictly in the requested JSON schema format.
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ColumnMappingResult,
        ),
    )
    return ColumnMappingResult.model_validate_json(response.text)

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_llm_status_normalization(unique_statuses: list[str]) -> StatusNormalizationResult:
    api_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    You are a Logistics Expert data processor.
    Your task is to normalize raw shipment status strings from various ERP and logistics systems into our standardized application categories.
    
    Uploaded Raw Statuses:
    {json.dumps(unique_statuses)}
    
    Allowed Standard Categories:
    {json.dumps(ALLOWED_STATUSES)}
    
    Instructions:
    1. Map each raw status to exactly one of the allowed categories based on its semantic meaning.
    2. For example, "shipped", "on the way", or "customs" should map to "In Transit".
    3. For example, "booked", "pending", or "acknowledged" should map to "Not Started".
    4. Only map a status if you are highly confident it fits into the allowed category. If it is completely ambiguous, do not map it.
    5. Output strictly in the requested JSON schema format.
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=StatusNormalizationResult,
        ),
    )
    return StatusNormalizationResult.model_validate_json(response.text)

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

def clean_numeric(series):
    """Strips currency symbols and commas, coerces to float."""
    def clean_val(val):
        if pd.isna(val):
            return pd.NA
        val_str = str(val)
        cleaned = re.sub(r'[^\d.-]', '', val_str)
        try:
            return float(cleaned)
        except ValueError:
            return pd.NA
    return series.apply(clean_val)

def map_columns(df):
    """Maps varying column names to REQUIRED_COLUMNS."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        st.warning("⚠ LLM-powered column mapping is unavailable until a valid GEMINI_API_KEY is configured in the environment.")
        return None
        
    df_cols = list(df.columns)
    
    with st.spinner("Analyzing columns with LLM..."):
        try:
            mapping_result = call_llm_mapping(df_cols)
        except Exception as e:
            st.error(f"Error calling LLM for column mapping: {e}")
            return None
            
    if mapping_result.mapped_columns:
        mapping_dict = {entry.uploaded_column: entry.internal_schema_field for entry in mapping_result.mapped_columns}
        df.rename(columns=mapping_dict, inplace=True)
        mapped_msg = "\n".join([f"* {k} → {v}" for k, v in mapping_dict.items()])
        st.success(f"**Detected Column Mapping:**\n{mapped_msg}")
        
    if mapping_result.missing_required_fields:
        missing_msg = "\n".join([f"* {col}" for col in mapping_result.missing_required_fields])
        st.warning(f"**⚠ Missing Required Fields:**\n{missing_msg}\n\nSome risk rules may be skipped due to unavailable data.")
        for col in mapping_result.missing_required_fields:
            df[col] = pd.NA
            
    return df[REQUIRED_COLUMNS]

def clean_data(df):
    """Cleans data values and normalizes statuses."""
    if 'order_value' in df.columns:
        df['order_value'] = clean_numeric(df['order_value'])
    if 'supplier_previous_delays' in df.columns:
        df['supplier_previous_delays'] = clean_numeric(df['supplier_previous_delays'])
        
    if 'expected_delivery_date' in df.columns:
        df['expected_delivery_date'] = pd.to_datetime(df['expected_delivery_date'], errors='coerce')
        
    if 'shipment_status' in df.columns and not df['shipment_status'].isna().all():
        unique_statuses = df['shipment_status'].dropna().unique().tolist()
        if unique_statuses:
            with st.spinner("Normalizing shipment statuses with LLM..."):
                try:
                    status_result = call_llm_status_normalization(unique_statuses)
                    status_mapping = {entry.uploaded_status: entry.allowed_status for entry in status_result.status_mapping}
                except Exception as e:
                    st.error(f"Error calling LLM for status normalization: {e}")
                    status_mapping = {}
            
            if status_mapping:
                mapped_status_msg = "\n".join([f"* '{k}' → '{v}'" for k, v in status_mapping.items()])
                st.success(f"**Detected Status Mapping:**\n{mapped_status_msg}")
                
            df['shipment_status'] = df['shipment_status'].apply(
                lambda val: status_mapping.get(str(val).strip(), val) if pd.notna(val) else pd.NA
            )
        
    return df

def validate_data(df):
    """Non-blocking validation that warns users of missing/invalid data."""
    # We no longer fail the file; we just warn.
    for col in REQUIRED_COLUMNS:
        if df[col].isna().all():
            st.warning(f"**Warning:** The required column '{col}' is entirely empty. Risk rules depending on this field will be skipped.")
            
    unknown_statuses = df[~df['shipment_status'].isin(ALLOWED_STATUSES) & df['shipment_status'].notna()]
    if not unknown_statuses.empty:
        st.warning(f"**Warning:** Found {len(unknown_statuses)} rows with unrecognized shipment statuses.")
        
    invalid_dates_mask = df['expected_delivery_date'].isna()
    if invalid_dates_mask.any():
        st.warning(f"**Warning:** Found {invalid_dates_mask.sum()} rows with invalid or missing expected delivery dates. Delivery-date-based risk rules will be skipped for these rows.")
        
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
    if pd.notna(status) and status == "Not Started":
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
    if pd.notnull(expected_date) and pd.notna(status) and status == "Not Started" and today <= expected_date and days_until_delivery <= 3:
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
            df = map_columns(df)
            
            if df is not None:
                df = clean_data(df)
                is_valid = validate_data(df)
                
                if is_valid:
                    df = calculate_risk(df)
                    df = classify_and_recommend(df)
                    st.success(f"**{len(df)} Orders Analyzed Successfully**\n\nValidation, risk calculation, and recommendations complete.")
                    render_dashboard(df)

if __name__ == "__main__":
    main()
