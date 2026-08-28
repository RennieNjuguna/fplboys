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
        """Payment received after deadline on standard GW has is_late=True and fine=50.00"""
        p = Payment.objects.create(
            member=self.m2,
            gameweek=self.gw3,
            amount_paid=Decimal('200.00'),
            timestamp_received=self.deadline + timedelta(hours=1),
            mpesa_code="LATE123"
        )
        self.assertTrue(p.is_late)
        self.assertEqual(p.late_fine_amount, Decimal('50.00'))

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
            'amount_paid': '175.00',
            'timestamp_received': (self.deadline - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'),
            'mpesa_code': 'UPDATEDREF',
            'verified': True,
            'notes': 'Edited in test'
        })
        self.assertEqual(resp_edit_post.status_code, 302)
        p.refresh_from_db()
        self.assertEqual(p.amount_paid, Decimal('175.00'))
        self.assertEqual(p.mpesa_code, 'UPDATEDREF')

        # Delete payment
        del_url = f'/treasury/payment/{p.id}/delete/'
        resp_del_get = self.client.get(del_url)
        self.assertEqual(resp_del_get.status_code, 200)

        resp_del_post = self.client.post(del_url)
        self.assertEqual(resp_del_post.status_code, 302)
        self.assertFalse(Payment.objects.filter(id=p.id).exists())

    def test_bulk_payment_carryover_across_gameweeks(self):
        """Paying Ksh. 450 for GW3 automatically funds GW3, GW4, and GW5"""
        gw4 = Gameweek.objects.create(number=4, name="Gameweek 4", deadline_time=self.deadline + timedelta(days=7), status='upcoming')
        gw5 = Gameweek.objects.create(number=5, name="Gameweek 5", deadline_time=self.deadline + timedelta(days=14), status='upcoming')

        self.client.post('/treasury/unlock/', {'password': '@FPLBoyz254??', 'next': '/treasury/portal/'})

        resp = self.client.post('/treasury/portal/', {
            'action': 'save_payment',
            'member': self.m1.id,
            'gameweek': self.gw3.id,
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
        """Posting Ksh. 300 in portal disburses Ksh. 150 to current GW and Ksh. 150 to next GW"""
        gw4 = Gameweek.objects.create(number=4, name="Gameweek 4", deadline_time=self.deadline + timedelta(days=7), status='upcoming')
        self.client.post('/treasury/unlock/', {'password': '@FPLBoyz254??', 'next': '/treasury/portal/'})

        resp = self.client.post('/treasury/portal/', {
            'action': 'save_payment',
            'member': self.m2.id,
            'gameweek': self.gw3.id,
            'amount_paid': '300.00',
            'timestamp_received': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'mpesa_code': 'PAY300REF',
            'verified': True,
        })
        self.assertEqual(resp.status_code, 302)

        p3 = Payment.objects.get(member=self.m2, gameweek=self.gw3)
        p4 = Payment.objects.get(member=self.m2, gameweek=gw4)

        self.assertEqual(p3.amount_paid, Decimal('150.00'))
        self.assertEqual(p4.amount_paid, Decimal('150.00'))

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




