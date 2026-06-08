import unittest
import pandas as pd
import sys
from unittest.mock import MagicMock

# Mock streamlit so we can test the logic without starting a web server
sys.modules['streamlit'] = MagicMock()

from app import evaluate_po, get_risk_level, get_recommendation

class TestSupplyChainRiskEngine(unittest.TestCase):
    
    def setUp(self):
        # We set a fixed 'today' date so tests are perfectly deterministic
        self.today = pd.Timestamp('2026-06-04')
        
        # Base row template with completely clean data (0 points expected)
        self.base_row = {
            'po_id': 'TEST-001',
            'supplier_name': 'Test Supplier',
            'order_value': 5000, # Not high value (< 100k)
            'expected_delivery_date': pd.Timestamp('2026-06-15'), # Future delivery
            'shipment_status': 'In Transit', # Has started
            'supplier_previous_delays': 0 # No delays
        }

    def test_baseline_zero_risk(self):
        row = pd.Series(self.base_row)
        score, reasons = evaluate_po(row, self.today)
        self.assertEqual(score, 0, "Base scenario should have 0 risk score.")

    def test_rule_1_delivery_date_missed(self):
        row = pd.Series(self.base_row)
        row['expected_delivery_date'] = pd.Timestamp('2026-06-01') # Past date
        score, _ = evaluate_po(row, self.today)
        self.assertEqual(score, 40, "Missed delivery date should add exactly 40 points.")

    def test_rule_2_shipment_not_started(self):
        row = pd.Series(self.base_row)
        row['shipment_status'] = 'Not Started'
        score, _ = evaluate_po(row, self.today)
        self.assertEqual(score, 30, "Not Started should add exactly 30 points.")

    def test_rule_3_repeated_delays(self):
        row = pd.Series(self.base_row)
        row['supplier_previous_delays'] = 3
        score, _ = evaluate_po(row, self.today)
        self.assertEqual(score, 20, ">= 3 Delays should add exactly 20 points.")

    def test_rule_4_high_value(self):
        row = pd.Series(self.base_row)
        row['order_value'] = 150000
        score, _ = evaluate_po(row, self.today)
        self.assertEqual(score, 10, "Order value > 100k should add exactly 10 points.")

    def test_bonus_rule_approaching_deadline(self):
        row = pd.Series(self.base_row)
        # Approaching (within 3 days), not started
        row['expected_delivery_date'] = pd.Timestamp('2026-06-06') 
        row['shipment_status'] = 'Not Started'
        score, _ = evaluate_po(row, self.today)
        # Not Started (30) + Approaching Bonus (25) = 55
        self.assertEqual(score, 55, "Approaching deadline + Not Started should trigger bonus (+25) and Rule 2 (+30).")

    def test_risk_classification(self):
        # Test boundaries
        self.assertEqual(get_risk_level(29), 'Low')
        self.assertEqual(get_risk_level(30), 'Medium')
        self.assertEqual(get_risk_level(59), 'Medium')
        self.assertEqual(get_risk_level(60), 'High')
        self.assertEqual(get_risk_level(100), 'High')

    def test_recommendations(self):
        self.assertEqual(get_recommendation('High', 3), 'Consider Alternate Supplier')
        self.assertEqual(get_recommendation('High', 1), 'Escalate To Procurement Manager')
        self.assertEqual(get_recommendation('Medium', 0), 'Follow Up With Supplier')
        self.assertEqual(get_recommendation('Low', 0), 'Continue Monitoring')

if __name__ == '__main__':
    unittest.main()
