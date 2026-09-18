from decimal import Decimal
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from league.models import Member, Gameweek, GameweekResult
from league.services.payout_engine import calculate_gameweek_payouts, is_member_eligible_for_prize
from treasury.models import Payment, PaymentTransaction, TransactionAllocation, PrizePayout
from treasury.services.payment_allocation import (
    allocate_payment_with_rollover,
    apply_winnings_to_future_gameweeks,
    get_member_available_prize_balance,
    delete_payment_transaction,
    delete_gameweek_payment,
    record_cash_payout
)
from treasury.services.pot_calculator import get_treasury_summary
from treasury.services.ledger_matrix import build_financial_ledger_matrix


class ComprehensivePayoutAndAllocationTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.past = self.now - timedelta(days=5)

        self.m1 = Member.objects.create(fpl_entry_id=201, manager_name='Sam Wambua', team_name='Sam Stars', phone_number='254700000001')
        self.m2 = Member.objects.create(fpl_entry_id=202, manager_name='Ben Mwangi', team_name='Ben FC', phone_number='254700000002')
        self.m3 = Member.objects.create(fpl_entry_id=203, manager_name='King Chris', team_name='Chris Kings', phone_number='254700000003')
        self.m4 = Member.objects.create(fpl_entry_id=204, manager_name='Dennis Torque', team_name='Torque XI', phone_number='254700000004')

        self.gw1 = Gameweek.objects.create(number=1, name='Gameweek 1', deadline_time=self.past, status='finished')
        self.gw2 = Gameweek.objects.create(number=2, name='Gameweek 2', deadline_time=self.past + timedelta(days=1), status='finished')
        self.gw3 = Gameweek.objects.create(number=3, name='Gameweek 3', deadline_time=self.past + timedelta(days=2), status='finished')
        self.gw4 = Gameweek.objects.create(number=4, name='Gameweek 4', deadline_time=self.past + timedelta(days=3), status='finished')
        self.gw5 = Gameweek.objects.create(number=5, name='Gameweek 5', deadline_time=self.past + timedelta(days=4), status='upcoming')

    def test_scenario_1_user_wins_and_rolls_over_winnings(self):
        # Sam wins 166.67 in GW1
        GameweekResult.objects.create(
            member=self.m1, gameweek=self.gw1, gw_points=75, net_points=75,
            gw_prize_won=Decimal('166.67'), is_top3=True, league_rank=2
        )
        self.assertEqual(get_member_available_prize_balance(self.m1), Decimal('166.67'))

        # Sam rolls over 150.00 into GW2
        created = apply_winnings_to_future_gameweeks(self.m1, Decimal('150.00'), start_gw_number=2)
        self.assertEqual(len(created), 1)
        p_gw2 = Payment.objects.get(member=self.m1, gameweek=self.gw2)
        self.assertEqual(p_gw2.amount_paid, Decimal('150.00'))
        self.assertIn('PRIZE', p_gw2.mpesa_code)

        # Available balance is now 16.67
        avail = get_member_available_prize_balance(self.m1)
        self.assertEqual(avail, Decimal('16.67'))

        # Sam wins 250.00 in GW4
        GameweekResult.objects.create(
            member=self.m1, gameweek=self.gw4, gw_points=85, net_points=85,
            gw_prize_won=Decimal('250.00'), is_top3=True, league_rank=1
        )
        self.assertEqual(get_member_available_prize_balance(self.m1), Decimal('266.67'))

    def test_scenario_2_data_entered_and_then_deleted(self):
        payments = allocate_payment_with_rollover(
            member=self.m2, start_gw=self.gw3, total_amount=Decimal('150.00'),
            mpesa_code='QWERTY1234', notes='Payment for GW3'
        )
        self.assertEqual(len(payments), 1)
        p = payments[0]
        self.assertEqual(Payment.objects.filter(member=self.m2, gameweek=self.gw3).count(), 1)
        self.assertEqual(get_treasury_summary()['total_revenue_collected'], Decimal('150.00'))

        delete_gameweek_payment(p)
        self.assertEqual(Payment.objects.filter(member=self.m2, gameweek=self.gw3).count(), 0)
        self.assertEqual(get_treasury_summary()['total_revenue_collected'], Decimal('0.00'))

    def test_scenario_3_prize_rollover_deleted_ghost_deduction_prevented(self):
        GameweekResult.objects.create(
            member=self.m1, gameweek=self.gw1, gw_points=90, net_points=90,
            gw_prize_won=Decimal('250.00'), is_top3=True, league_rank=1
        )
        self.assertEqual(get_member_available_prize_balance(self.m1), Decimal('250.00'))

        apply_winnings_to_future_gameweeks(self.m1, Decimal('150.00'), start_gw_number=2)
        self.assertEqual(get_member_available_prize_balance(self.m1), Decimal('100.00'))

        p_gw2 = Payment.objects.get(member=self.m1, gameweek=self.gw2)
        tx = p_gw2.transaction
        self.assertIsNotNone(tx)

        delete_payment_transaction(tx)

        self.assertFalse(Payment.objects.filter(member=self.m1, gameweek=self.gw2).exists())
        self.assertEqual(get_member_available_prize_balance(self.m1), Decimal('250.00'))

    def test_scenario_4_installment_payments_half_and_half_and_deletion(self):
        ontime = self.gw3.deadline_time - timedelta(hours=2)

        # 1st installment: 75.00 on-time
        allocate_payment_with_rollover(
            member=self.m3, start_gw=self.gw3, total_amount=Decimal('75.00'),
            timestamp=ontime, mpesa_code='TX1_CODE', notes='First half'
        )
        p = Payment.objects.get(member=self.m3, gameweek=self.gw3)
        tx1 = p.transaction
        self.assertEqual(p.amount_paid, Decimal('75.00'))
        self.assertEqual(p.balance_due, Decimal('75.00'))
        self.assertFalse(p.is_fully_cleared)

        # 2nd installment: 75.00 on-time
        allocate_payment_with_rollover(
            member=self.m3, start_gw=self.gw3, total_amount=Decimal('75.00'),
            timestamp=ontime, mpesa_code='TX2_CODE', notes='Second half'
        )
        p.refresh_from_db()
        self.assertEqual(p.amount_paid, Decimal('150.00'))
        self.assertEqual(p.balance_due, Decimal('0.00'))
        self.assertTrue(p.is_fully_cleared)
        self.assertEqual(p.allocation_records.count(), 2)

        # Delete Tx2
        tx2 = PaymentTransaction.objects.get(mpesa_code='TX2_CODE')
        delete_payment_transaction(tx2)

        p.refresh_from_db()
        self.assertEqual(p.amount_paid, Decimal('75.00'))
        self.assertEqual(p.balance_due, Decimal('75.00'))
        self.assertEqual(p.transaction, tx1)
        self.assertEqual(p.allocation_records.count(), 1)

        # Delete Tx1
        delete_payment_transaction(tx1)
        self.assertFalse(Payment.objects.filter(member=self.m3, gameweek=self.gw3).exists())

    def test_scenario_4b_late_installments_with_fines_and_deletions(self):
        late_time = self.gw3.start_time + timedelta(hours=1)

        # Tx1: 75.00 late
        allocate_payment_with_rollover(
            member=self.m2, start_gw=self.gw3, total_amount=Decimal('75.00'),
            timestamp=late_time, mpesa_code='LATE_TX1'
        )
        p = Payment.objects.get(member=self.m2, gameweek=self.gw3)
        self.assertTrue(p.is_late)
        self.assertEqual(p.amount_paid, Decimal('75.00'))
        self.assertFalse(p.fine_paid)
        self.assertEqual(p.balance_due, Decimal('125.00'))

        # Tx2: 75.00 late
        allocate_payment_with_rollover(
            member=self.m2, start_gw=self.gw3, total_amount=Decimal('75.00'),
            timestamp=late_time, mpesa_code='LATE_TX2'
        )
        p.refresh_from_db()
        self.assertEqual(p.amount_paid, Decimal('100.00'))
        self.assertTrue(p.fine_paid)
        self.assertEqual(p.balance_due, Decimal('50.00'))

        # Tx3: 50.00
        allocate_payment_with_rollover(
            member=self.m2, start_gw=self.gw3, total_amount=Decimal('50.00'),
            timestamp=late_time, mpesa_code='LATE_TX3'
        )
        p.refresh_from_db()
        self.assertEqual(p.amount_paid, Decimal('150.00'))
        self.assertTrue(p.fine_paid)
        self.assertEqual(p.balance_due, Decimal('0.00'))
        self.assertTrue(p.is_fully_cleared)

        # Delete Tx3
        tx3 = PaymentTransaction.objects.get(mpesa_code='LATE_TX3')
        delete_payment_transaction(tx3)
        p.refresh_from_db()
        self.assertEqual(p.amount_paid, Decimal('100.00'))
        self.assertTrue(p.fine_paid)
        self.assertEqual(p.balance_due, Decimal('50.00'))

        # Delete Tx2
        tx2 = PaymentTransaction.objects.get(mpesa_code='LATE_TX2')
        delete_payment_transaction(tx2)
        p.refresh_from_db()
        self.assertEqual(p.amount_paid, Decimal('75.00'))
        self.assertFalse(p.fine_paid)
        self.assertEqual(p.balance_due, Decimal('125.00'))

        # Delete Tx1
        tx1 = PaymentTransaction.objects.get(mpesa_code='LATE_TX1')
        delete_payment_transaction(tx1)
        self.assertFalse(Payment.objects.filter(member=self.m2, gameweek=self.gw3).exists())

    def test_scenario_5_combined_cash_and_prize_rollover(self):
        ontime = self.gw3.deadline_time - timedelta(hours=2)

        GameweekResult.objects.create(
            member=self.m1, gameweek=self.gw1, gw_points=80, net_points=80,
            gw_prize_won=Decimal('100.00'), is_top3=True, league_rank=1
        )
        self.assertEqual(get_member_available_prize_balance(self.m1), Decimal('100.00'))

        apply_winnings_to_future_gameweeks(self.m1, Decimal('75.00'), start_gw_number=3, timestamp=ontime)
        p = Payment.objects.get(member=self.m1, gameweek=self.gw3)
        self.assertEqual(p.amount_paid, Decimal('75.00'))
        self.assertEqual(get_member_available_prize_balance(self.m1), Decimal('25.00'))

        allocate_payment_with_rollover(
            member=self.m1, start_gw=self.gw3, total_amount=Decimal('75.00'),
            timestamp=ontime, mpesa_code='CASH75_REF'
        )
        p.refresh_from_db()
        self.assertEqual(p.amount_paid, Decimal('150.00'))
        self.assertTrue(p.is_fully_cleared)

        tx_cash = PaymentTransaction.objects.get(mpesa_code='CASH75_REF')
        tx_prize = PaymentTransaction.objects.get(transaction_type='PRIZE_ROLLOVER', member=self.m1)

        delete_payment_transaction(tx_cash)
        p.refresh_from_db()
        self.assertEqual(p.amount_paid, Decimal('75.00'))
        self.assertEqual(get_member_available_prize_balance(self.m1), Decimal('25.00'))

        delete_payment_transaction(tx_prize)
        self.assertFalse(Payment.objects.filter(member=self.m1, gameweek=self.gw3).exists())
        self.assertEqual(get_member_available_prize_balance(self.m1), Decimal('100.00'))

    def test_scenario_9_delete_gameweek_payment_direct(self):
        GameweekResult.objects.create(
            member=self.m1, gameweek=self.gw1, gw_points=80, net_points=80,
            gw_prize_won=Decimal('200.00'), is_top3=True, league_rank=1
        )
        self.assertEqual(get_member_available_prize_balance(self.m1), Decimal('200.00'))

        apply_winnings_to_future_gameweeks(self.m1, Decimal('150.00'), start_gw_number=2)
        p = Payment.objects.get(member=self.m1, gameweek=self.gw2)
        self.assertEqual(get_member_available_prize_balance(self.m1), Decimal('50.00'))

        delete_gameweek_payment(p)
        self.assertFalse(Payment.objects.filter(member=self.m1, gameweek=self.gw2).exists())
        self.assertEqual(get_member_available_prize_balance(self.m1), Decimal('200.00'))

    def test_scenario_6_payout_timing_and_disqualification_roll_down(self):
        Payment.objects.create(
            member=self.m1, gameweek=self.gw3, amount_paid=Decimal('150.00'),
            timestamp_received=self.gw3.start_time + timedelta(hours=2),
            is_late=True, late_fine_amount=Decimal('50.00'), fine_paid=False, verified=True
        )
        Payment.objects.create(
            member=self.m2, gameweek=self.gw3, amount_paid=Decimal('150.00'),
            timestamp_received=self.gw3.deadline_time - timedelta(hours=2),
            is_late=False, verified=True
        )
        Payment.objects.create(
            member=self.m3, gameweek=self.gw3, amount_paid=Decimal('150.00'),
            timestamp_received=self.gw3.deadline_time - timedelta(hours=2),
            is_late=False, verified=True
        )
        Payment.objects.create(
            member=self.m4, gameweek=self.gw3, amount_paid=Decimal('150.00'),
            timestamp_received=self.gw3.deadline_time - timedelta(hours=2),
            is_late=False, verified=True
        )

        r1 = GameweekResult.objects.create(member=self.m1, gameweek=self.gw3, gw_points=95, net_points=95, overall_rank=1)
        r2 = GameweekResult.objects.create(member=self.m2, gameweek=self.gw3, gw_points=85, net_points=85, overall_rank=2)
        r3 = GameweekResult.objects.create(member=self.m3, gameweek=self.gw3, gw_points=75, net_points=75, overall_rank=3)
        r4 = GameweekResult.objects.create(member=self.m4, gameweek=self.gw3, gw_points=65, net_points=65, overall_rank=4)

        self.assertFalse(is_member_eligible_for_prize(self.m1, self.gw3))
        self.assertTrue(is_member_eligible_for_prize(self.m2, self.gw3))
        self.assertTrue(is_member_eligible_for_prize(self.m3, self.gw3))
        self.assertTrue(is_member_eligible_for_prize(self.m4, self.gw3))

        calculate_gameweek_payouts(self.gw3)

        r1.refresh_from_db()
        r2.refresh_from_db()
        r3.refresh_from_db()
        r4.refresh_from_db()

        self.assertEqual(r1.gw_prize_won, Decimal('0.00'))
        self.assertFalse(r1.is_top3)

        self.assertEqual(r2.gw_prize_won, Decimal('250.00'))
        self.assertTrue(r2.is_top3)

        self.assertEqual(r3.gw_prize_won, Decimal('166.67'))
        self.assertTrue(r3.is_top3)

        self.assertEqual(r4.gw_prize_won, Decimal('83.33'))
        self.assertTrue(r4.is_top3)

    def test_scenario_7_financial_ledger_matrix_mathematical_consistency(self):
        Payment.objects.create(
            member=self.m1, gameweek=self.gw3, amount_paid=Decimal('150.00'),
            timestamp_received=self.gw3.deadline_time - timedelta(hours=1),
            verified=True
        )
        Payment.objects.create(
            member=self.m2, gameweek=self.gw3, amount_paid=Decimal('150.00'),
            timestamp_received=self.gw3.start_time + timedelta(hours=1),
            is_late=True, late_fine_amount=Decimal('50.00'), fine_paid=False, verified=True
        )
        Payment.objects.create(
            member=self.m3, gameweek=self.gw3, amount_paid=Decimal('75.00'),
            timestamp_received=self.gw3.deadline_time - timedelta(hours=1),
            verified=True
        )

        matrix = build_financial_ledger_matrix(max_gws=3)
        rows = matrix['rows']
        col_summaries = matrix['column_summaries']

        for r in rows:
            expected_due = sum(c['balance_due'] for c in r['cells'])
            self.assertEqual(r['total_due'], expected_due)

        for col_idx, col in enumerate(col_summaries):
            expected_col_due = sum(r['cells'][col_idx]['balance_due'] for r in rows)
            self.assertEqual(col['total_due'], expected_col_due)

        row_sum_due = sum(r['total_due'] for r in rows)
        col_sum_due = sum(c['total_due'] for c in col_summaries)
        self.assertEqual(row_sum_due, col_sum_due)
        self.assertEqual(matrix['grand_total_due'], row_sum_due)

    def test_scenario_8_pot_calculator_exactness_with_partial_payments(self):
        Payment.objects.create(
            member=self.m1, gameweek=self.gw3, amount_paid=Decimal('150.00'),
            verified=True
        )
        Payment.objects.create(
            member=self.m2, gameweek=self.gw3, amount_paid=Decimal('75.00'),
            verified=True
        )
        summary = get_treasury_summary()
        self.assertEqual(summary['total_revenue_collected'], Decimal('225.00'))
        self.assertEqual(summary['bbq_standard_portion'], Decimal('75.00'))
        self.assertEqual(summary['total_jackpot_pot'], Decimal('75.00'))
        self.assertEqual(summary['total_prize_pool_collected'], Decimal('75.00'))
        self.assertEqual(
            summary['bbq_standard_portion'] + summary['total_jackpot_pot'] + summary['total_prize_pool_collected'],
            Decimal('225.00')
        )

    def test_scenario_10_marvin_owino_prize_and_cash_deletion_flow(self):
        """
        Tests the exact Marvin Owino workflow:
        1. Manager wins GW3 (Ksh. 83.33).
        2. Applies Ksh. 83.33 prize to GW4 contribution.
           GW4 Payment is created with amount_paid = 83.33, status PARTIAL.
        3. Manager pays Ksh. 67.00 cash via M-Pesa ('UICBQ5X8CK').
           GW4 Payment increases to 150.00 (PAID), and 0.33 carries over to GW5.
           Payment mpesa_code becomes 'PRIZE / UICBQ5X8CK'.
        4. Treasurer deletes the M-Pesa cash transaction (Tx 'UICBQ5X8CK').
           VERIFICATION:
           - GW4 Payment is NOT deleted!
           - GW4 Payment retains Ksh. 83.33 (the prize portion).
           - GW4 mpesa_code cleanly reverts to 'PRIZE-WINNINGS'.
           - GW5 carryover (0.33) is cleanly reversed.
           - Available prize balance remains 0.00 (83.33 is still actively allocated in GW4).
        5. Treasurer re-enters Ksh. 67.00 cash ('UICBQ5X8CK').
           - GW4 Payment is once again 150.00 (PAID).
           - Payment mpesa_code is 'PRIZE / UICBQ5X8CK'.
        6. Treasurer deletes the PRIZE rollover transaction instead of cash:
           - GW4 Payment is NOT wiped out!
           - GW4 Payment retains Ksh. 66.67 (the cash portion).
           - Payment mpesa_code reverts to 'UICBQ5X8CK'.
           - Manager's available prize balance is IMMEDIATELY RESTORED to Ksh. 83.33!
        7. If Treasurer deletes the entire Gameweek Payment:
           - The 83.33 prize is restored to available prize balance.
        """
        m = Member.objects.create(fpl_entry_id=901, manager_name='Marvin Owino', team_name='Don Bosco')

        # 1. Marvin wins GW3 (83.33)
        GameweekResult.objects.create(
            member=m, gameweek=self.gw3, gw_points=70, net_points=70,
            gw_prize_won=Decimal('83.33'), is_top3=True, league_rank=3
        )
        self.assertEqual(get_member_available_prize_balance(m), Decimal('83.33'))

        # 2. Allocate 83.33 prize to GW4
        created_prize = apply_winnings_to_future_gameweeks(
            member=m, amount_to_apply=Decimal('83.33'), start_gw_number=4,
            timestamp=self.gw4.deadline_time - timedelta(hours=5)
        )
        self.assertEqual(len(created_prize), 1)
        p_gw4 = Payment.objects.get(member=m, gameweek=self.gw4)
        self.assertEqual(p_gw4.amount_paid, Decimal('83.33'))
        self.assertEqual(p_gw4.mpesa_code, 'PRIZE-WINNINGS')
        self.assertEqual(get_member_available_prize_balance(m), Decimal('0.00'))

        tx_prize = PaymentTransaction.objects.get(member=m, transaction_type='PRIZE_ROLLOVER')

        # 3. Marvin pays Ksh. 67.00 cash via M-Pesa ('UICBQ5X8CK')
        created_cash = allocate_payment_with_rollover(
            member=m, start_gw=self.gw4, total_amount=Decimal('67.00'),
            mpesa_code='UICBQ5X8CK', timestamp=self.gw4.deadline_time - timedelta(hours=1)
        )
        p_gw4.refresh_from_db()
        self.assertEqual(p_gw4.amount_paid, Decimal('150.00'))
        self.assertIn('PRIZE', p_gw4.mpesa_code)
        self.assertIn('UICBQ5X8CK', p_gw4.mpesa_code)

        tx_cash = PaymentTransaction.objects.get(member=m, mpesa_code='UICBQ5X8CK')
        self.assertEqual(tx_cash.amount, Decimal('67.00'))
        # 66.67 to GW4, 0.33 to GW5
        self.assertEqual(tx_cash.allocation_records.count(), 2)

        # 4. Treasurer deletes the cash transaction 'UICBQ5X8CK'
        delete_payment_transaction(tx_cash)

        # Verify GW4 payment is NOT deleted and retains 83.33 prize!
        p_gw4.refresh_from_db()
        self.assertEqual(p_gw4.amount_paid, Decimal('83.33'))
        self.assertEqual(p_gw4.mpesa_code, 'PRIZE-WINNINGS')
        self.assertEqual(p_gw4.transaction, tx_prize)
        self.assertEqual(Payment.objects.filter(member=m, gameweek__number=5).count(), 0)
        self.assertEqual(get_member_available_prize_balance(m), Decimal('0.00'))

        # 5. Treasurer re-enters Ksh. 67.00 cash
        created_cash_2 = allocate_payment_with_rollover(
            member=m, start_gw=self.gw4, total_amount=Decimal('67.00'),
            mpesa_code='UICBQ5X8CK', timestamp=self.gw4.deadline_time - timedelta(hours=1)
        )
        p_gw4.refresh_from_db()
        self.assertEqual(p_gw4.amount_paid, Decimal('150.00'))
        self.assertIn('PRIZE', p_gw4.mpesa_code)
        self.assertIn('UICBQ5X8CK', p_gw4.mpesa_code)

        tx_cash_2 = PaymentTransaction.objects.get(member=m, mpesa_code='UICBQ5X8CK')

        # 6. Treasurer deletes the PRIZE transaction instead of cash
        delete_payment_transaction(tx_prize)

        p_gw4.refresh_from_db()
        self.assertEqual(p_gw4.amount_paid, Decimal('66.67'))
        self.assertEqual(p_gw4.mpesa_code, 'UICBQ5X8CK')
        self.assertEqual(p_gw4.transaction, tx_cash_2)
        # Prize is immediately restored to available balance!
        self.assertEqual(get_member_available_prize_balance(m), Decimal('83.33'))

        # 7. Re-apply prize and then delete the entire GW4 payment
        apply_winnings_to_future_gameweeks(
            member=m, amount_to_apply=Decimal('83.33'), start_gw_number=4,
            timestamp=self.gw4.deadline_time - timedelta(hours=1)
        )
        self.assertEqual(get_member_available_prize_balance(m), Decimal('0.00'))

        p_gw4.refresh_from_db()
        self.assertEqual(p_gw4.amount_paid, Decimal('150.00'))

        # Delete the whole payment
        delete_gameweek_payment(p_gw4)
        self.assertEqual(Payment.objects.filter(member=m, gameweek=self.gw4).count(), 0)
        # Prize is once again restored!
        self.assertEqual(get_member_available_prize_balance(m), Decimal('83.33'))