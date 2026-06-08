# Supplier Delay Risk Monitor

A lightweight, rule-based supply chain monitoring agent built with Python and Streamlit. This tool helps procurement and supply chain teams quickly identify purchase orders that are at risk of delay, prioritize them, and decide on actionable next steps.

## Features

* **AI-Powered Data Ingestion:** Upload CSV or Excel files containing your purchase orders. The system uses Gemini 2.5 Flash to automatically map your custom column names to the internal schema and normalize varying shipment statuses (e.g., mapping "shipped" to "In Transit").
* **Risk Detection Engine:** Evaluates each purchase order against clearly defined business rules:
  * Delivery Date Missed (+40)
  * Shipment Not Started (+30)
  * Supplier Has Repeated Delays (+20)
  * High Value Order (+10)
  * Delivery Date Approaching (+25)
* **Risk Classification:** Translates raw risk scores into actionable categories (`Low`, `Medium`, `High`).
* **Actionable Recommendations:** Recommends exactly what procurement teams should do (e.g., `Escalate To Procurement Manager`, `Consider Alternate Supplier`, `Follow Up With Supplier`, `Continue Monitoring`).
* **Business Dashboard:** A clean, easy-to-read dashboard summarizing total risk distribution and highlighting the specific purchase orders that require immediate attention.

## Installation

1. Clone or download this repository.
2. Ensure you have Python installed.
3. Install the required dependencies:

```bash
pip install -r requirements.txt
```

4. **Environment Setup:** Create a `.env` file in the root directory and add your Google Gemini API key (required for smart column mapping and status normalization):

```env
GEMINI_API_KEY=your_api_key_here
```

## Usage

Run the Streamlit application using the following command:

```bash
python -m streamlit run app.py
```

The application will launch in your default web browser. You can then upload the provided `sample_data.csv` to test the dashboard and see the risk engine in action.

## Project Structure

* `app.py`: The main Streamlit application containing all validation, risk detection logic, classification rules, and the UI dashboard (all under 600 lines of code).
* `sample_data.csv`: A sample dataset designed to thoroughly test all business rules and edge cases.
* `requirements.txt`: Python package dependencies.
