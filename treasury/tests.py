from decimal import Decimal
from datetime import timedelta
from django.test import TestCase, Client
from django.utils import timezone
from django.urls import reverse
from league.models import Member, Gameweek, GameweekResult
from treasury.models import Payment, TreasuryConfig
from treasury.services.pot_calculator import get_treasury_summary, get_member_financial_leaderboard
from treasury.services.ledger_matrix import build_financial_ledger_matrix


class TreasuryFinancialTests(TestCase):
    def setUp(self):
        self.deadline = timezone.now() - timedelta(days=1)
        self.gw3 = Gameweek.objects.create(
            number=3,
            name="Gameweek 3",
            deadline_time=self.deadline,
            status='finished'
        )
        self.gw1 = Gameweek.objects.create(
            number=1,
            name="Gameweek 1",
            deadline_time=self.deadline,
            status='finished'
        )
        self.gw2 = Gameweek.objects.create(
            number=2,
            name="Gameweek 2",
            deadline_time=self.deadline,
            status='finished'
        )
        self.m1 = Member.objects.create(fpl_entry_id=101, manager_name="Manager One", team_name="Team One", phone_number="254711111111")
        self.m2 = Member.objects.create(fpl_entry_id=102, manager_name="Manager Two", team_name="Team Two", phone_number="254722222222")
        self.client = Client()

    def test_on_time_payment_no_fine(self):
        """Payment received before deadline has is_late=False and fine=0"""
        p = Payment.objects.create(
            member=self.m1,
            gameweek=self.gw3,
            amount_paid=Decimal('150.00'),
            timestamp_received=self.deadline - timedelta(hours=2),
            mpesa_code="ONTIME123"
        )
        self.assertFalse(p.is_late)
        self.assertEqual(p.late_fine_amount, Decimal('0.00'))

    def test_late_payment_auto_fine_on_standard_gw(self):
        """
        Payment received before GW kickoff (within 90m transfer window) is on-time (is_late=False).
        Payment received strictly after the first match kicks off (gw.start_time) has is_late=True and fine=50.00.
        """
        # On-time during 90m transfer closure before kickoff
        p_ontime = Payment.objects.create(
            member=self.m1,
            gameweek=self.gw3,
            amount_paid=Decimal('150.00'),
            timestamp_received=self.deadline + timedelta(minutes=45),
            mpesa_code="ONTIME123"
        )
        self.assertFalse(p_ontime.is_late)
        self.assertEqual(p_ontime.late_fine_amount, Decimal('0.00'))

        # Late after kickoff (start_time = deadline + 90m)
        p_late = Payment.objects.create(
            member=self.m2,
            gameweek=self.gw3,
            amount_paid=Decimal('200.00'),
            timestamp_received=self.deadline + timedelta(hours=2),
            mpesa_code="LATE123"
        )
        self.assertTrue(p_late.is_late)
        self.assertEqual(p_late.late_fine_amount, Decimal('50.00'))

    def test_fine_waiver_for_gw1_gw2_gw19_gw38(self):
        """Payments after deadline for GW1 and GW2 have fine waived (is_late=False, fine=0)"""
        p1 = Payment.objects.create(
            member=self.m1,
            gameweek=self.gw1,
            amount_paid=Decimal('150.00'),
            timestamp_received=self.deadline + timedelta(hours=5),
            mpesa_code="WAIVED1"
        )
        self.assertFalse(p1.is_late)
        self.assertEqual(p1.late_fine_amount, Decimal('0.00'))

        p2 = Payment.objects.create(
            member=self.m2,
            gameweek=self.gw2,
            amount_paid=Decimal('150.00'),
            timestamp_received=self.deadline + timedelta(hours=10),
            mpesa_code="WAIVED2"
        )
        self.assertFalse(p2.is_late)
        self.assertEqual(p2.late_fine_amount, Decimal('0.00'))

    def test_pot_breakdown_and_fine_routing_to_bbq(self):
        Payment.objects.create(
            member=self.m1,
            gameweek=self.gw3,
            amount_paid=Decimal('150.00'),
            timestamp_received=self.deadline - timedelta(hours=1),
            mpesa_code="CODE1"
        )
        Payment.objects.create(
            member=self.m2,
            gameweek=self.gw3,
            amount_paid=Decimal('200.00'),
            timestamp_received=self.deadline + timedelta(hours=2),
            mpesa_code="CODE2"
        )

        summary = get_treasury_summary()

        self.assertEqual(summary['total_revenue_collected'], Decimal('350.00'))
        self.assertEqual(summary['total_bbq_pot'], Decimal('150.00'))
        self.assertEqual(summary['bbq_fines_portion'], Decimal('50.00'))
        self.assertEqual(summary['total_jackpot_pot'], Decimal('100.00'))
        self.assertEqual(summary['total_prize_pool_collected'], Decimal('100.00'))

    def test_member_net_profit_loss(self):
        Payment.objects.create(
            member=self.m1,
            gameweek=self.gw3,
            amount_paid=Decimal('150.00'),
            timestamp_received=self.deadline - timedelta(hours=1),
            mpesa_code="CODE1"
        )
        Payment.objects.create(
            member=self.m2,
            gameweek=self.gw3,
            amount_paid=Decimal('200.00'),
            timestamp_received=self.deadline + timedelta(hours=2),
            mpesa_code="CODE2"
        )

        GameweekResult.objects.create(
            member=self.m1,
            gameweek=self.gw3,
            gw_points=70,
            transfer_cost=0,
            gw_prize_won=Decimal('250.00'),
            league_rank=1,
            is_top3=True
        )
        GameweekResult.objects.create(
            member=self.m2,
            gameweek=self.gw3,
            gw_points=40,
            transfer_cost=0,
            gw_prize_won=Decimal('0.00'),
            league_rank=2,
            is_top3=False
        )

        leaderboard = get_member_financial_leaderboard()

        m1_stat = next(item for item in leaderboard if item['member'] == self.m1)
        m2_stat = next(item for item in leaderboard if item['member'] == self.m2)

        self.assertEqual(m1_stat['net_pl'], Decimal('100.00'))
        self.assertEqual(m2_stat['net_pl'], Decimal('-200.00'))
        self.assertEqual(leaderboard[0]['member'], self.m1)

    def test_public_financial_ledger_access(self):
        """Financial Ledger is publicly accessible without login"""
        resp = self.client.get('/treasury/ledger/')
        self.assertEqual(resp.status_code, 200)

    def test_treasury_security_lock_and_unlock(self):
        """Test password protection for Treasury Admin Portal only"""
        config = TreasuryConfig.get_config()
        self.assertTrue(config.check_admin_password("@FPLBoyz254??"))

        # 1. Access portal without unlocking redirects to unlock page
        resp = self.client.get('/treasury/portal/')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/treasury/unlock/', resp.url)

        # 2. Try wrong password
        resp_fail = self.client.post('/treasury/unlock/', {'password': 'wrongpassword', 'next': '/treasury/portal/'})
        self.assertEqual(resp_fail.status_code, 200)

        # 3. Post correct password
        resp_auth = self.client.post('/treasury/unlock/', {'password': '@FPLBoyz254??', 'next': '/treasury/portal/'})
        self.assertEqual(resp_auth.status_code, 302)
        self.assertEqual(resp_auth.url, '/treasury/portal/')

        # 4. Portal access now succeeds
        resp_success = self.client.get('/treasury/portal/')
        self.assertEqual(resp_success.status_code, 200)

        # 5. Lock treasury
        resp_lock = self.client.get('/treasury/lock/')
        self.assertEqual(resp_lock.status_code, 302)

        # 6. Portal is locked again
        resp_after_lock = self.client.get('/treasury/portal/')
        self.assertEqual(resp_after_lock.status_code, 302)

    def test_payment_crud_operations(self):
        """Test editing and deleting payments in Treasury Portal"""
        self.client.post('/treasury/unlock/', {'password': '@FPLBoyz254??', 'next': '/treasury/portal/'})

        p = Payment.objects.create(
            member=self.m1,
            gameweek=self.gw3,
            amount_paid=Decimal('150.00'),
            timestamp_received=self.deadline - timedelta(hours=1),
            mpesa_code="TESTREF123"
        )

        # Edit payment
        edit_url = f'/treasury/payment/{p.id}/edit/'
        resp_edit_get = self.client.get(edit_url)
        self.assertEqual(resp_edit_get.status_code, 200)

        resp_edit_post = self.client.post(edit_url, {
            'member': self.m1.id,
            'gameweek': self.gw3.id,
            'amount_paid': '120.00',
            'timestamp_received': (self.deadline - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'),
            'mpesa_code': 'UPDATEDREF',
            'verified': True,
            'notes': 'Edited in test'
        })
        self.assertEqual(resp_edit_post.status_code, 302)
        p.refresh_from_db()
        self.assertEqual(p.amount_paid, Decimal('120.00'))
        self.assertEqual(p.mpesa_code, 'UPDATEDREF')

        # Delete payment
        del_url = f'/treasury/payment/{p.id}/delete/'
        resp_del_get = self.client.get(del_url)
        self.assertEqual(resp_del_get.status_code, 200)

        resp_del_post = self.client.post(del_url)
        self.assertEqual(resp_del_post.status_code, 302)
        self.assertFalse(Payment.objects.filter(id=p.id).exists())

    def test_bulk_payment_carryover_across_gameweeks(self):
        """Paying Ksh. 450 when GW1 & GW2 are paid automatically funds GW3, GW4, and GW5 in FIFO order"""
        Payment.objects.create(member=self.m1, gameweek=self.gw1, amount_paid=Decimal('150.00'), verified=True)
        Payment.objects.create(member=self.m1, gameweek=self.gw2, amount_paid=Decimal('150.00'), verified=True)

        gw4 = Gameweek.objects.create(number=4, name="Gameweek 4", deadline_time=self.deadline + timedelta(days=7), status='upcoming')
        gw5 = Gameweek.objects.create(number=5, name="Gameweek 5", deadline_time=self.deadline + timedelta(days=14), status='upcoming')

        self.client.post('/treasury/unlock/', {'password': '@FPLBoyz254??', 'next': '/treasury/portal/'})

        resp = self.client.post('/treasury/portal/', {
            'action': 'save_payment',
            'member': self.m1.id,
            'amount_paid': '450.00',
            'timestamp_received': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'mpesa_code': 'BULK450REF',
            'verified': True,
        })
        self.assertEqual(resp.status_code, 302)

        # Verify 3 payments exist of 150 each
        p3 = Payment.objects.get(member=self.m1, gameweek=self.gw3)
        p4 = Payment.objects.get(member=self.m1, gameweek=gw4)
        p5 = Payment.objects.get(member=self.m1, gameweek=gw5)

        self.assertEqual(p3.amount_paid, Decimal('150.00'))
        self.assertEqual(p4.amount_paid, Decimal('150.00'))
        self.assertEqual(p5.amount_paid, Decimal('150.00'))

    def test_apply_winnings_to_future_gameweeks(self):
        """Member uses cash prize winnings to fund future unpaid gameweek"""
        # Give member 1 a prize win of Ksh. 250 in GW1
        GameweekResult.objects.create(
            member=self.m1,
            gameweek=self.gw1,
            gw_points=80,
            transfer_cost=0,
            gw_prize_won=Decimal('250.00'),
            league_rank=1,
            is_top3=True
        )
        gw4 = Gameweek.objects.create(number=4, name="Gameweek 4", deadline_time=self.deadline + timedelta(days=7), status='upcoming')

        self.client.post('/treasury/unlock/', {'password': '@FPLBoyz254??', 'next': '/treasury/portal/'})

        resp = self.client.post('/treasury/portal/', {
            'action': 'apply_winnings',
            'member_id': self.m1.id,
            'amount_to_apply': '150.00',
            'start_gw': '4',
        })
        self.assertEqual(resp.status_code, 302)

        p4 = Payment.objects.get(member=self.m1, gameweek=gw4)
        self.assertEqual(p4.amount_paid, Decimal('150.00'))
        self.assertEqual(p4.mpesa_code, 'PRIZE-WINNINGS')
        self.assertFalse(p4.is_late)

    def test_partial_payment_ledger_status(self):
        """Paying Ksh. 83.33 results in PARTIAL status and balance due of 66.67"""
        Payment.objects.create(
            member=self.m1,
            gameweek=self.gw3,
            amount_paid=Decimal('83.33'),
            timestamp_received=self.deadline - timedelta(hours=1),
            mpesa_code="PARTIAL83"
        )
        matrix = build_financial_ledger_matrix(max_gws=3)
        row_m1 = next(r for r in matrix['rows'] if r['member'] == self.m1)
        cell_gw3 = next(c for c in row_m1['cells'] if c['gw_id'] == self.gw3.id)

        self.assertEqual(cell_gw3['status'], 'PARTIAL')
        self.assertEqual(cell_gw3['amount_paid'], Decimal('83.33'))
        self.assertEqual(cell_gw3['balance_due'], Decimal('66.67'))

    def test_excess_payment_300_disbursement_via_portal(self):
        """Posting Ksh. 300 in portal when GW1 is paid disburses Ksh. 150 to GW2 and Ksh. 150 to GW3"""
        Payment.objects.create(member=self.m2, gameweek=self.gw1, amount_paid=Decimal('150.00'), verified=True)
        self.client.post('/treasury/unlock/', {'password': '@FPLBoyz254??', 'next': '/treasury/portal/'})

        resp = self.client.post('/treasury/portal/', {
            'action': 'save_payment',
            'member': self.m2.id,
            'amount_paid': '300.00',
            'timestamp_received': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'mpesa_code': 'PAY300REF',
            'verified': True,
        })
        self.assertEqual(resp.status_code, 302)

        p2 = Payment.objects.get(member=self.m2, gameweek=self.gw2)
        p3 = Payment.objects.get(member=self.m2, gameweek=self.gw3)

        self.assertEqual(p2.amount_paid, Decimal('150.00'))
        self.assertEqual(p3.amount_paid, Decimal('150.00'))

    def test_record_cash_payout_deduction(self):
        """Recording a cash prize payout (M-Pesa sent) clears the member's available rollover balance"""
        from treasury.services.payment_allocation import get_member_available_prize_balance
        # Member 1 wins 250 in GW 1
        GameweekResult.objects.create(
            member=self.m1,
            gameweek=self.gw1,
            gw_points=90,
            transfer_cost=0,
            gw_prize_won=Decimal('250.00'),
            league_rank=1,
            is_top3=True
        )
        self.assertEqual(get_member_available_prize_balance(self.m1), Decimal('250.00'))

        self.client.post('/treasury/unlock/', {'password': '@FPLBoyz254??', 'next': '/treasury/portal/'})

        # Disburse cash via portal
        resp = self.client.post('/treasury/portal/', {
            'action': 'disburse_payout',
            'member_id': self.m1.id,
            'amount_to_disburse': '250.00',
            'mpesa_reference': 'MPESA250REF',
            'notes': 'Sent cash via M-Pesa to winner',
        })
        self.assertEqual(resp.status_code, 302)

        # Available balance is now 0
        self.assertEqual(get_member_available_prize_balance(self.m1), Decimal('0.00'))

    def test_delete_cash_prize_payout_restores_balance(self):
        """
        Deleting a cash prize disbursement deletes the PrizePayout record
        and immediately restores the money back to the winner's available balance.
        """
        from treasury.models import PrizePayout
        from treasury.services.payment_allocation import get_member_available_prize_balance, record_cash_payout

        # Member 1 wins 250 in GW 1
        GameweekResult.objects.create(
            member=self.m1,
            gameweek=self.gw1,
            gw_points=90,
            transfer_cost=0,
            gw_prize_won=Decimal('250.00'),
            league_rank=1,
            is_top3=True
        )
        self.assertEqual(get_member_available_prize_balance(self.m1), Decimal('250.00'))

        # Disburse Ksh. 150
        payout = record_cash_payout(
            member=self.m1,
            amount=Decimal('150.00'),
            mpesa_reference='DISBURSE150',
            notes='Test payout'
        )
        self.assertEqual(get_member_available_prize_balance(self.m1), Decimal('100.00'))

        # Now delete the payout via delete view
        self.client.post('/treasury/unlock/', {'password': '@FPLBoyz254??', 'next': '/treasury/portal/'})
        resp = self.client.post(f'/treasury/payout/{payout.id}/delete/')
        self.assertEqual(resp.status_code, 302)

        # PrizePayout is deleted and available balance is restored to 250.00
        self.assertFalse(PrizePayout.objects.filter(id=payout.id).exists())
        self.assertEqual(get_member_available_prize_balance(self.m1), Decimal('250.00'))

    def test_partial_payment_top_up_after_prize_rollover(self):
        """
        Manager has GW1 paid, wins Ksh. 83.33 in GW1 -> rolls over to GW2 (amount_paid=83.33).
        Then treasurer logs Ksh. 66.67 via portal (no GW selected).
        GW2 amount_paid becomes 150.00 (PAID in full).
        """
        Payment.objects.create(member=self.m1, gameweek=self.gw1, amount_paid=Decimal('150.00'), verified=True)
        # Give member 1 a prize of 83.33
        GameweekResult.objects.create(
            member=self.m1,
            gameweek=self.gw1,
            gw_points=85,
            transfer_cost=0,
            gw_prize_won=Decimal('83.33'),
            league_rank=1,
            is_top3=True
        )
        from treasury.services.payment_allocation import apply_winnings_to_future_gameweeks, get_member_available_prize_balance
        apply_winnings_to_future_gameweeks(self.m1, Decimal('83.33'), start_gw_number=2)
        p_gw2 = Payment.objects.get(member=self.m1, gameweek=self.gw2)
        self.assertEqual(p_gw2.amount_paid, Decimal('83.33'))
        self.assertEqual(get_member_available_prize_balance(self.m1), Decimal('0.00'))

        # Now member pays the remaining balance of Ksh. 66.67 via portal (FIFO auto-targets GW2)
        self.client.post('/treasury/unlock/', {'password': '@FPLBoyz254??', 'next': '/treasury/portal/'})
        resp = self.client.post('/treasury/portal/', {
            'action': 'save_payment',
            'member': self.m1.id,
            'amount_paid': '66.67',
            'timestamp_received': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'mpesa_code': 'CASH66REF',
            'verified': True,
        })
        self.assertEqual(resp.status_code, 302)

        p_gw2.refresh_from_db()
        self.assertEqual(p_gw2.amount_paid, Decimal('150.00'))
        self.assertIn('PRIZE', p_gw2.mpesa_code)
        self.assertIn('CASH66REF', p_gw2.mpesa_code)

        # Available prize balance is STILL 0.00 (not corrupted or double counted)
        self.assertEqual(get_member_available_prize_balance(self.m1), Decimal('0.00'))

        # Financial ledger matrix confirms GW2 status is PAID
        matrix = build_financial_ledger_matrix(max_gws=3)
        row_m1 = next(r for r in matrix['rows'] if r['member'] == self.m1)
        cell_gw2 = next(c for c in row_m1['cells'] if c['gw_id'] == self.gw2.id)
        self.assertEqual(cell_gw2['status'], 'PAID')
        self.assertEqual(cell_gw2['amount_paid'], Decimal('150.00'))
        self.assertEqual(cell_gw2['balance_due'], Decimal('0.00'))

    def test_partial_payment_with_excess_rollover(self):
        """
        Manager has GW1 paid, and partial contribution of Ksh. 100 in GW2.
        When member pays standard Ksh. 150.00, GW2 receives Ksh. 50 (reaching 150) and GW3 receives Ksh. 100 in FIFO order.
        """
        Payment.objects.create(member=self.m2, gameweek=self.gw1, amount_paid=Decimal('150.00'), verified=True)
        Payment.objects.create(
            member=self.m2,
            gameweek=self.gw2,
            amount_paid=Decimal('100.00'),
            timestamp_received=timezone.now(),
            mpesa_code='PRIZE-WINNINGS',
            verified=True
        )

        self.client.post('/treasury/unlock/', {'password': '@FPLBoyz254??', 'next': '/treasury/portal/'})
        resp = self.client.post('/treasury/portal/', {
            'action': 'save_payment',
            'member': self.m2.id,
            'amount_paid': '150.00',
            'timestamp_received': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'mpesa_code': 'EXCESS150REF',
            'verified': True,
        })
        self.assertEqual(resp.status_code, 302)

        p2 = Payment.objects.get(member=self.m2, gameweek=self.gw2)
        p3 = Payment.objects.get(member=self.m2, gameweek=self.gw3)

        self.assertEqual(p2.amount_paid, Decimal('150.00'))
        self.assertEqual(p3.amount_paid, Decimal('100.00'))

    def test_excess_payment_never_exceeds_150_per_gw(self):
        """
        Paying Ksh. 500 across empty GWs caps each GW at 150 and rolls over excess.
        """
        gw4 = Gameweek.objects.create(number=4, name="Gameweek 4", deadline_time=self.deadline + timedelta(days=7), status='upcoming')
        self.client.post('/treasury/unlock/', {'password': '@FPLBoyz254??', 'next': '/treasury/portal/'})

        resp = self.client.post('/treasury/portal/', {
            'action': 'save_payment',
            'member': self.m1.id,
            'amount_paid': '500.00',
            'timestamp_received': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'mpesa_code': 'BULK500REF',
            'verified': True,
        })
        self.assertEqual(resp.status_code, 302)

        p1 = Payment.objects.get(member=self.m1, gameweek=self.gw1)
        p2 = Payment.objects.get(member=self.m1, gameweek=self.gw2)
        p3 = Payment.objects.get(member=self.m1, gameweek=self.gw3)
        p4 = Payment.objects.get(member=self.m1, gameweek=gw4)

        self.assertEqual(p1.amount_paid, Decimal('150.00'))
        self.assertEqual(p2.amount_paid, Decimal('150.00'))
        self.assertEqual(p3.amount_paid, Decimal('150.00'))
        self.assertEqual(p4.amount_paid, Decimal('50.00'))

    def test_payment_edit_excess_rollover(self):
        """
        Editing a payment from 150 to 300 caps current GW at 150 and rolls over remaining 150 to next GW.
        """
        p1 = Payment.objects.create(
            member=self.m1,
            gameweek=self.gw1,
            amount_paid=Decimal('150.00'),
            timestamp_received=timezone.now(),
            mpesa_code="ORIG150",
            verified=True
        )

        self.client.post('/treasury/unlock/', {'password': '@FPLBoyz254??', 'next': '/treasury/portal/'})
        edit_url = f'/treasury/payment/{p1.id}/edit/'

        resp = self.client.post(edit_url, {
            'member': self.m1.id,
            'gameweek': self.gw1.id,
            'amount_paid': '300.00',
            'timestamp_received': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'mpesa_code': 'EDIT300REF',
            'verified': True,
            'notes': 'Edited in test'
        })
        self.assertEqual(resp.status_code, 302)

        p1.refresh_from_db()
        p2 = Payment.objects.get(member=self.m1, gameweek=self.gw2)

        self.assertEqual(p1.amount_paid, Decimal('150.00'))
        self.assertEqual(p2.amount_paid, Decimal('150.00'))

    def test_api_check_deadline_with_member_existing_balance(self):
        """
        API returns existing partial payment, balance due, and recommended amount.
        """
        Payment.objects.create(
            member=self.m1,
            gameweek=self.gw2,
            amount_paid=Decimal('83.33'),
            timestamp_received=timezone.now(),
            mpesa_code="PRIZE83",
            verified=True
        )

        self.client.post('/treasury/unlock/', {'password': '@FPLBoyz254??', 'next': '/treasury/portal/'})
        resp = self.client.get(f'/treasury/api/check-deadline/?gw_id={self.gw2.id}&member_id={self.m1.id}')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertTrue(data['has_existing'])
        self.assertAlmostEqual(data['existing_paid'], 83.33, places=2)
        self.assertAlmostEqual(data['balance_due'], 66.67, places=2)
        self.assertAlmostEqual(data['recommended_amount'], 66.67, places=2)

    def test_member_joined_gw2_pardon_in_matrix(self):
        """
        Member who joined in GW2 has status 'PARDON' for GW1, 0 balance due, and not counted in unpaid.
        """
        self.m2.joined_gameweek = 2
        self.m2.save()

        matrix = build_financial_ledger_matrix(max_gws=3)
        m2_row = [r for r in matrix['rows'] if r['member'].id == self.m2.id][0]
        gw1_cell = m2_row['cells'][0]

        self.assertEqual(gw1_cell['status'], 'PARDON')
        self.assertEqual(gw1_cell['balance_due'], Decimal('0.00'))
        self.assertEqual(gw1_cell['amount_paid'], Decimal('0.00'))
        self.assertFalse(gw1_cell['is_due'])
        self.assertEqual(m2_row['unpaid_count'], 2)  # GW2 and GW3 (since both are finished in setup)

    def test_active_gw_flagged_summary_defaulters_and_cleared(self):
        """
        Test get_active_gw_flagged_summary identifies actually flagged defaulters and cleared members.
        """
        from treasury.services.ledger_matrix import get_active_gw_flagged_summary

        # Member 1 pays for GW1, GW2, GW3 (fully cleared)
        Payment.objects.create(
            member=self.m1,
            gameweek=self.gw1,
            amount_paid=Decimal('150.00'),
            timestamp_received=self.deadline - timedelta(hours=2),
            verified=True,
            mpesa_code="ONTIME1"
        )
        Payment.objects.create(
            member=self.m1,
            gameweek=self.gw2,
            amount_paid=Decimal('150.00'),
            timestamp_received=self.deadline - timedelta(hours=2),
            verified=True,
            mpesa_code="ONTIME2"
        )
        Payment.objects.create(
            member=self.m1,
            gameweek=self.gw3,
            amount_paid=Decimal('150.00'),
            timestamp_received=self.deadline - timedelta(hours=2),
            verified=True,
            mpesa_code="ONTIME3"
        )
        # Member 2 is unpaid for GW1, GW2, GW3

        summary = get_active_gw_flagged_summary(target_gw_num=3)
        self.assertIsNotNone(summary)
        self.assertEqual(summary['gw'].number, 3)
        self.assertEqual(summary['cleared_count'], 1)
        self.assertEqual(summary['defaulters_count'], 1)
        self.assertEqual(summary['current_gw_cleared'][0]['member'], self.m1)
        self.assertEqual(summary['flagged_defaulters'][0]['member'], self.m2)
        # For m2: GW1 waived (fine 0), GW2 waived (fine 0), GW3 standard (fine 50)
        self.assertEqual(summary['flagged_defaulters'][0]['total_fines'], Decimal('50.00'))
        self.assertEqual(summary['flagged_defaulters'][0]['total_due'], Decimal('500.00'))

    def test_active_gw_flagged_summary_ticking_bomb(self):
        """
        Test get_active_gw_flagged_summary detects Ticking Bomb (<24h to deadline) for upcoming GW.
        """
        from treasury.services.ledger_matrix import get_active_gw_flagged_summary

        # Create upcoming GW4 with deadline in 12 hours
        upcoming_deadline = timezone.now() + timedelta(hours=12)
        gw4 = Gameweek.objects.create(
            number=4,
            name="Gameweek 4",
            deadline_time=upcoming_deadline,
            status='upcoming'
        )

        # Member 1 has paid in advance
        Payment.objects.create(
            member=self.m1,
            gameweek=gw4,
            amount_paid=Decimal('150.00'),
            timestamp_received=timezone.now(),
            verified=True,
            mpesa_code="ADVANCE"
        )

        summary = get_active_gw_flagged_summary(target_gw_num=4)
        self.assertIsNotNone(summary)
        self.assertEqual(summary['gw_state'], 'ticking_bomb')
        self.assertTrue(summary['is_within_24h'])
        self.assertEqual(summary['cleared_count'], 1)
        self.assertEqual(summary['pending_count'], 1)
        self.assertEqual(summary['current_gw_pending'][0]['member'], self.m2)
        self.assertEqual(summary['current_gw_pending'][0]['balance_due'], Decimal('150.00'))

    def test_fine_waiver_for_gw1_and_gw2(self):
        """
        Test that defaults in GW1 or GW2 carry Ksh. 0 late fine.
        """
        from treasury.services.ledger_matrix import get_active_gw_flagged_summary
        
        # Member 2 is unpaid for GW1 and GW2
        summary = get_active_gw_flagged_summary(target_gw_num=3)
        self.assertIsNotNone(summary)
        
        # Check m2 in flagged_defaulters
        m2_default = next((d for d in summary['flagged_defaulters'] if d['member'] == self.m2), None)
        self.assertIsNotNone(m2_default)
        
        # For GW1 and GW2 in m2_default['defaulted_gws'], late_fine should be 0.00
        for gwd in m2_default['defaulted_gws']:
            if gwd['gw_number'] in (1, 2, 19, 38):
                self.assertEqual(gwd['late_fine'], Decimal('0.00'))
                self.assertTrue(gwd['is_waived'])

    def test_lump_sum_400_payment_transaction_creation_and_breakdown(self):
        """
        Test that logging a payment of Ksh. 400 creates a single PaymentTransaction of 400,
        linked to 3 allocations (GW1: 150, GW2: 150, GW3: 100), and visible in manager & portal views.
        """
        from treasury.models import PaymentTransaction
        from treasury.services.payment_allocation import allocate_payment_with_rollover

        created = allocate_payment_with_rollover(
            member=self.m1,
            start_gw=self.gw1,
            total_amount=Decimal('400.00'),
            timestamp=timezone.now(),
            mpesa_code="QJH78291KL",
            notes="400 payment test",
            verified=True
        )

        self.assertEqual(len(created), 3)
        tx = PaymentTransaction.objects.filter(member=self.m1, mpesa_code="QJH78291KL").first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, Decimal('400.00'))
        self.assertEqual(tx.allocations.count(), 3)

        # Check allocations summary
        summary_text = tx.allocations_summary_text
        self.assertIn("GW 1 (Ksh. 150)", summary_text)
        self.assertIn("GW 2 (Ksh. 150)", summary_text)
        self.assertIn("GW 3 (Ksh. 100)", summary_text)

        # Check manager profile view shows transaction
        resp = self.client.get(f'/manager/{self.m1.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Ksh. 400")
        self.assertContains(resp, "QJH78291KL")

    def test_auto_fifo_payment_allocation_without_start_gw(self):
        """
        Test that allocating payment without start_gw automatically finds the earliest
        unpaid GW (e.g. GW2 if GW1 is paid) and distributes sequentially in FIFO order.
        """
        from treasury.models import PaymentTransaction
        from treasury.services.payment_allocation import allocate_payment_with_rollover

        # Pay GW1 in advance
        Payment.objects.create(
            member=self.m1,
            gameweek=self.gw1,
            amount_paid=Decimal('150.00'),
            verified=True,
            mpesa_code="GW1PAID"
        )

        # Log Ksh. 250 without specifying start_gw
        created = allocate_payment_with_rollover(
            member=self.m1,
            start_gw=None,
            total_amount=Decimal('250.00'),
            timestamp=timezone.now(),
            mpesa_code="FIFO250",
            verified=True
        )

        self.assertEqual(len(created), 2)
        # GW2 gets 150 (paid in full)
        p_gw2 = Payment.objects.get(member=self.m1, gameweek=self.gw2)
        self.assertEqual(p_gw2.amount_paid, Decimal('150.00'))
        # GW3 gets 100 (partial balance)
        p_gw3 = Payment.objects.get(member=self.m1, gameweek=self.gw3)
        self.assertEqual(p_gw3.amount_paid, Decimal('100.00'))

        # Transaction starting gameweek should be GW2
        tx = PaymentTransaction.objects.get(mpesa_code="FIFO250")
        self.assertEqual(tx.starting_gameweek, self.gw2)

    def test_auto_fifo_interplay_with_prize_rollover(self):
        """
        Test that prize winnings rollover and cash payments work together in FIFO order.
        If a prize rollover pays GW1 (150) and partially pays GW2 (100),
        a new M-Pesa payment of 150 automatically completes GW2 (with 50) and rolls 100 into GW3.
        """
        from treasury.services.payment_allocation import allocate_payment_with_rollover

        # 1. Prize rollover: Ksh. 250 across GW1 (150) and GW2 (100)
        allocate_payment_with_rollover(
            member=self.m2,
            start_gw=None,
            total_amount=Decimal('250.00'),
            timestamp=timezone.now(),
            verified=True,
            is_prize=True
        )

        p1 = Payment.objects.get(member=self.m2, gameweek=self.gw1)
        self.assertEqual(p1.amount_paid, Decimal('150.00'))
        p2 = Payment.objects.get(member=self.m2, gameweek=self.gw2)
        self.assertEqual(p2.amount_paid, Decimal('100.00'))

        # 2. Cash M-Pesa payment: Ksh. 150 with start_gw=None
        allocate_payment_with_rollover(
            member=self.m2,
            start_gw=None,
            total_amount=Decimal('150.00'),
            timestamp=timezone.now(),
            mpesa_code="TOPUP150",
            verified=True,
            is_prize=False
        )

        p2.refresh_from_db()
        self.assertEqual(p2.amount_paid, Decimal('150.00')) # GW2 is now fully paid at 150
        self.assertIn("PRIZE", p2.mpesa_code)
        self.assertIn("TOPUP150", p2.mpesa_code)

        p3 = Payment.objects.get(member=self.m2, gameweek=self.gw3)
        self.assertEqual(p3.amount_paid, Decimal('100.00')) # GW3 received the remaining 100
        self.assertIn("TOPUP150", p3.mpesa_code)

    def test_flagged_at_gw_start_kickoff_not_deadline(self):
        """
        Tests that:
        1. Gameweek.start_time is 90 minutes after Gameweek.deadline_time.
        2. A member who pays within the 90m window between deadline and kickoff is ON-TIME (is_late=False).
        3. A member who pays after the first match kicks off is LATE (is_late=True, late_fine=50).
        4. In the Active Radar, a member is NOT in Flagged Defaulters when transfers close (90m before kickoff),
           but only becomes flagged once the match actually starts.
        """
        from treasury.services.ledger_matrix import get_active_gw_flagged_summary
        # Create GW5 with deadline 1 hour ago (so deadline has passed, but match has NOT kicked off since kickoff is in 30 mins)
        now = timezone.now()
        gw_kickoff_soon = Gameweek.objects.create(
            number=5,
            name="Gameweek 5",
            deadline_time=now - timedelta(minutes=60),  # Deadline passed 60m ago
            status='upcoming'
        )
        # Verify kickoff is 90 mins after deadline (so kickoff is in 30 mins)
        self.assertEqual(gw_kickoff_soon.start_time, gw_kickoff_soon.deadline_time + timedelta(minutes=90))
        self.assertTrue(gw_kickoff_soon.is_past_deadline)
        self.assertFalse(gw_kickoff_soon.is_past_start)

        # Payment made now (between deadline and kickoff)
        p = Payment.objects.create(
            member=self.m1,
            gameweek=gw_kickoff_soon,
            amount_paid=Decimal('150.00'),
            timestamp_received=now,
            mpesa_code="TRANSFER_CLOSURE_PAY"
        )
        # Should NOT be late since match hasn't started yet!
        self.assertFalse(p.is_late)
        self.assertEqual(p.late_fine_amount, Decimal('0.00'))

        # Payment made 2 hours after kickoff
        p_late = Payment.objects.create(
            member=self.m2,
            gameweek=gw_kickoff_soon,
            amount_paid=Decimal('200.00'),
            timestamp_received=gw_kickoff_soon.start_time + timedelta(hours=2),
            mpesa_code="POST_KICKOFF_PAY"
        )
        self.assertTrue(p_late.is_late)
        self.assertEqual(p_late.late_fine_amount, Decimal('50.00'))







