# Comprehensive Treasury, Payout & Allocation Engine Test Results

**Date**: September 18, 2026  
**Environment**: Python 3.7.9 / Django 3.2.18 / Windows  
**Test Suite**: 	reasury.tests_comprehensive_payout.ComprehensivePayoutAndAllocationTests  
**Overall Suite**: 56 Total Tests (10 Comprehensive Scenarios + 46 Regression Tests)  
**Final Status**: **100% PASSED (0 Failures, 0 Errors)**

---

## Executive Summary

To permanently eliminate accounting discrepancies, ghost deductions, and installment corruption, the treasury and payout engine was restructured:
1. **Transaction-Level Allocations (TransactionAllocation)**: Multiple M-Pesa payments and prize conversions can now fund a single Gameweek contribution (e.g. 75 cash + 75 cash, or 75 cash + 75 prize) without overwriting each other.
2. **Self-Healing Prize Rollovers**: Available prize balances are now computed directly against active allocations. If any payment or transaction funded by prize winnings is deleted, those funds are restored to the manager's available prize balance immediately.
3. **Reversible Multi-Step Deletions**: Deleting one installment never deletes another installment. Deleting a transaction subtracts only that transaction's specific contribution from the Gameweek payment.
4. **Exact Mathematical Consistency**: Pot allocations and Ledger matrix rows/columns match to the cent.
5. **Auto-Finalization & Safety**: Provisional podiums exclude disqualified managers, and gameweeks auto-finalize with manual fallback.

---

## Test Scenarios & Results

| # | Scenario | Status | Description |
|---|---|:---:|---|
| 1 | **User Wins & Rolls Over Winnings** | **PASS** | Sam wins 166.67 in GW1, rolls over 150 into GW2 (leaving 16.67). Wins 250 in GW4, available balance becomes exactly 266.67. |
| 2 | **Data Entered & Then Deleted** | **PASS** | User pays 150 via M-Pesa for GW3. Total revenue is 150. Payment is deleted; revenue reverts to 0.00 and pots decrease proportionally. |
| 3 | **Prize Rollover Deleted (Ghost Deduction Prevention)** | **PASS** | User wins 250 in GW1, rolls over 150 into GW2 (leaving 100). Rollover transaction is deleted. Available balance **immediately restores to 250.00**. Zero ghost deductions! |
| 4 | **On-Time Installments ('Half and Half')** | **PASS** | User pays 75 in Tx #1, status is PARTIAL (Bal: 75). User pays 75 in Tx #2, status becomes PAID (Bal: 0). Tx #2 is deleted; status cleanly returns to PARTIAL (Bal: 75, Tx #1 intact). Tx #1 is deleted; GW becomes UNPAID. |
| 4b | **Late Installments with Fines & Multi-Step Deletion** | **PASS** | User incurs 50 fine + 150 contribution = 200 due. Tx #1 pays 75 (Bal: 125). Tx #2 pays 75 (50 settles fine, 25 to contribution, Bal: 50). Tx #3 pays 50 (cleared, Bal: 0). Deleting Tx #3, Tx #2, and Tx #1 sequentially rolls back each layer cleanly. |
| 5 | **Combined Cash + Prize Rollover** | **PASS** | User has 100 prize balance. Rolls over 75 prize into GW3 (leaving 25) and pays remaining 75 cash via M-Pesa. Deleting cash leaves 75 prize intact. Deleting prize restores available prize balance to 100.00. |
| 6 | **Payout Timing & Disqualification Roll-Down** | **PASS** | 1st place manager pays late (disqualified). Prizes roll down: 2nd gets 250, 3rd gets 166.67, 4th gets 83.33. Disqualified manager receives 0.00 prize and is_top3=False. |
| 7 | **Financial Ledger Matrix Consistency** | **PASS** | Matrix sum of column totals equals sum of row totals down to the cent across mixed states (paid, partial, late, waived, pardoned, prize-funded). |
| 8 | **Pot Calculator Exactness with Partial Payments** | **PASS** | 150 payment + 75 partial payment = 225 total revenue. Pots split evenly: 75 BBQ, 75 Jackpot, 75 Prize Pool. Sum equals 225.00 exactly. |
| 9 | **Direct Gameweek Payment Deletion** | **PASS** | Deleting a Payment record directly from the portal cleans up parent allocations and linked reinvested prize payouts, restoring prize winnings. |

---

## Failures Encountered During Development & Fixes Applied

### Failure 1: Gameweek() got an unexpected keyword argument 'start_time'
- **Symptom**: During initial test suite execution, all 8 test cases errored with TypeError: Gameweek() got an unexpected keyword argument 'start_time'.
- **Root Cause**: Gameweek.start_time is a computed Python @property (deadline_time + timedelta(minutes=90)), not a database column.
- **Fix Applied**: Removed start_time from Gameweek.objects.create calls and let the model property calculate kickoff dynamically.

### Failure 2: Installment Balance Due Mismatch (Decimal('125.00') != Decimal('75.00'))
- **Symptom**: In 	est_scenario_4, the first 75 installment resulted in alance_due = 125.00 instead of 75.00.
- **Root Cause**: When no 	imestamp was supplied, the allocation service defaulted to 	imezone.now(). Because the test gameweek had a deadline in the past, the payment was flagged is_late=True and incurred an automatic Ksh. 50 late fine (75 unpaid contribution + 50 fine = 125.00).
- **Fix Applied**: 
  1. Passed on-time timestamps (deadline - 2h) for Scenario 4 (on-time installments).
  2. Created dedicated **Scenario 4b** (	est_scenario_4b_late_installments_with_fines_and_deletions) to test the late installment flow where late fines are assessed and cleared across multiple transactions.

### Failure 3: In-Memory ORM Field Overwrite on Multi-Allocation Deletions
- **Symptom**: In 	est_scenario_4b, deleting Tx #2 failed at self.assertFalse(p.fine_paid) AssertionError: True is not false.
- **Root Cause**: Tx #2 contained two allocations to the same payment (50 for LATE_FINE and 25 for CONTRIBUTION). When select_related('payment') fetched the allocations, each allocation had its own in-memory instance of Payment. In iteration 1, ine_paid was set to False and saved with update_fields=['fine_paid']. In iteration 2, the second allocation instance called p.save() without update_fields, which overwrote the database record with its stale in-memory state (ine_paid=True).
- **Fix Applied**: Refactored delete_payment_transaction to group allocations by payment. All adjustments (ine_reverted, contrib_deduct) are aggregated and applied to a single payment instance before saving once.

### Failure 4: Waived Gameweek Payment Retention on Zero Balance
- **Symptom**: In 	est_scenario_3, deleting a prize rollover for GW2 left the payment in the database (AssertionError: True is not false).
- **Root Cause**: On waived gameweeks (GW1, GW2, GW19, GW38), Payment.save() sets ine_paid=True (since fines are waived). The deletion check was if p.amount_paid <= 0 and not p.fine_paid: p.delete(). Because p.fine_paid was True, the payment was retained with mount_paid = 0.00.
- **Fix Applied**: Updated the check to has_active_fine = bool(p.is_late and p.late_fine_amount > 0 and p.fine_paid). If has_active_fine is False and p.amount_paid <= 0, the payment is cleanly deleted.

---

## Verification Summary
- Comprehensive test suite: python manage.py test treasury.tests_comprehensive_payout -> **10/10 PASS (0.30s)**
- Entire project test suite: python manage.py test -> **56/56 PASS (5.71s)**
- System check: python manage.py check -> **0 issues**
