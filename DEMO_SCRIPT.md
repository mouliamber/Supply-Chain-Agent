# Demo Script: Supply Chain Risk Agent

**Goal:** Prove to stakeholders that the agent can instantly parse raw procurement data, detect risk using business logic, and provide actionable recommendations.

**Prep Work:**
1. Ensure the app is running (`python -m streamlit run app.py`).
2. Have your 100-order test CSV ready to upload.
3. Ensure your `.env` file with the Gemini API key is properly configured.

---

### Step 1: The Hook
*What you say:*
"Managing supply chain delays is historically a manual, slow process. By the time we realize a supplier is late, it's often too late to pivot. Today, I'm going to show you a lightweight AI agent we built in just 5 days that completely automates this. It takes raw purchase orders and instantly flags the ones we need to worry about."

### Step 2: Ingestion & AI Mapping
*Action:* Click "Browse files" in the app and select your 100-order CSV file.
*What you say:*
"I'm uploading a batch of 100 recent purchase orders pulled straight from our system. Notice what happens here: the agent uses Gemini AI to automatically figure out which column is which, even if the data is messy. It also standardizes all the random shipment statuses—like 'on the way' or 'customs'—into clean, usable categories."

### Step 3: The Big Reveal
*Action:* Point to the top Risk Summary Cards and the Risk Distribution Chart.
*What you say:*
"In seconds, it evaluated every single order against our 5 core business rules. Out of the 100 orders, it successfully filtered out the noise and identified exactly 12 high-risk orders that need our immediate attention."

### Step 4: The Deep Dive
*Action:* Scroll down to the "High Risk Orders" and "Full Analysis Table".
*What you say:*
"Let's look at why it flagged these. [Point to a specific high-risk row]. This order has a high risk score because the shipment hasn't even started, but the expected delivery date is only a few days away. Plus, the system notes this specific supplier has a history of delays. 

Instead of just giving us a red flag, the agent tells our procurement team exactly what to do. Right here, it recommends **'Consider Alternate Supplier'**. It takes the guesswork out of crisis management."

### Step 5: The Value Proposition (Closing)
*What you say:*
"This agent operates entirely on our strict business rules, so there is no regulatory risk and no AI hallucinating the numbers. It simply automates the tedious analysis and highlights exactly where we need to take action today. Are there any questions?"
