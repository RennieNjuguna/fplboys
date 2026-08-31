from decimal import Decimal
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
import pytz

from league.models import Member, Gameweek, GameweekResult
from league.services.payout_engine import calculate_gameweek_payouts
from treasury.models import Payment


class PayoutEngineTests(TestCase):
    def setUp(self):
        self.deadline = timezone.now() - timedelta(days=2)
        self.gw = Gameweek.objects.create(
            number=10,
            name="Gameweek 10",
            deadline_time=self.deadline,
            status='finished',
            prize_pool_amount=Decimal('500.00')
        )
        self.members = []
        for i in range(1, 11):
            m = Member.objects.create(
                fpl_entry_id=1000 + i,
                manager_name=f"Manager {i}",
                team_name=f"Team {i}",
                phone_number=f"25470000000{i}"
            )
            self.members.append(m)
            # Create on-time verified payment by default for GW10
            Payment.objects.create(
                member=m,
                gameweek=self.gw,
                amount_paid=Decimal('150.00'),
                timestamp_received=self.deadline - timedelta(hours=2),
                verified=True
            )

    def test_distinct_top3_payouts(self):
        scores = [60, 50, 40, 30, 25, 20, 15, 10, 5, 0]
        for m, score in zip(self.members, scores):
            GameweekResult.objects.create(
                member=m,
                gameweek=self.gw,
                gw_points=score,
                transfer_cost=0
            )

        calculate_gameweek_payouts(self.gw)

        res_1 = GameweekResult.objects.get(member=self.members[0], gameweek=self.gw)
        res_2 = GameweekResult.objects.get(member=self.members[1], gameweek=self.gw)
        res_3 = GameweekResult.objects.get(member=self.members[2], gameweek=self.gw)
        res_4 = GameweekResult.objects.get(member=self.members[3], gameweek=self.gw)

        self.assertEqual(res_1.league_rank, 1)
        self.assertEqual(res_1.gw_prize_won, Decimal('250.00'))
        self.assertTrue(res_1.is_top3)

        self.assertEqual(res_2.league_rank, 2)
        self.assertEqual(res_2.gw_prize_won, Decimal('166.67'))
        self.assertTrue(res_2.is_top3)

        self.assertEqual(res_3.league_rank, 3)
        self.assertEqual(res_3.gw_prize_won, Decimal('83.33'))
        self.assertTrue(res_3.is_top3)

        self.assertEqual(res_4.league_rank, 4)
        self.assertEqual(res_4.gw_prize_won, Decimal('0.00'))
        self.assertFalse(res_4.is_top3)

    def test_late_contributor_disqualified_from_prize(self):
        """
        Manager 1 scores 80 pts (highest), but paid late -> Disqualified (Ksh. 0.00 prize).
        Manager 2 scores 70 pts (on time) -> Gets 1st Prize (Ksh. 250.00).
        Manager 3 scores 60 pts (on time) -> Gets 2nd Prize (Ksh. 166.67).
        Manager 4 scores 50 pts (on time) -> Gets 3rd Prize (Ksh. 83.33).
        """
        # Set Manager 1 payment to late
        p1 = Payment.objects.get(member=self.members[0], gameweek=self.gw)
        p1.timestamp_received = self.deadline + timedelta(hours=4)
        p1.is_late = True
        p1.late_fine_amount = Decimal('50.00')
        p1.save()

        scores = [80, 70, 60, 50, 40, 30, 20, 10, 5, 0]
        for m, score in zip(self.members, scores):
            GameweekResult.objects.create(
                member=m,
                gameweek=self.gw,
                gw_points=score,
                transfer_cost=0
            )

        calculate_gameweek_payouts(self.gw)

        res_1 = GameweekResult.objects.get(member=self.members[0], gameweek=self.gw)
        res_2 = GameweekResult.objects.get(member=self.members[1], gameweek=self.gw)
        res_3 = GameweekResult.objects.get(member=self.members[2], gameweek=self.gw)
        res_4 = GameweekResult.objects.get(member=self.members[3], gameweek=self.gw)

        # Manager 1 has rank 1 on points but disqualified from cash prize
        self.assertEqual(res_1.league_rank, 1)
        self.assertEqual(res_1.gw_prize_won, Decimal('0.00'))
        self.assertFalse(res_1.is_top3)

        # Manager 2 takes 1st prize (250)
        self.assertEqual(res_2.gw_prize_won, Decimal('250.00'))
        self.assertTrue(res_2.is_top3)

        # Manager 3 takes 2nd prize (166.67)
        self.assertEqual(res_3.gw_prize_won, Decimal('166.67'))
        self.assertTrue(res_3.is_top3)

        # Manager 4 takes 3rd prize (83.33)
        self.assertEqual(res_4.gw_prize_won, Decimal('83.33'))
        self.assertTrue(res_4.is_top3)

    def test_two_way_tie_for_first(self):
        scores = [60, 60, 50, 40, 30, 20, 10, 5, 0, 0]
        for m, score in zip(self.members, scores):
            GameweekResult.objects.create(
                member=m,
                gameweek=self.gw,
                gw_points=score,
                transfer_cost=0
            )

        calculate_gameweek_payouts(self.gw)

        res_1 = GameweekResult.objects.get(member=self.members[0], gameweek=self.gw)
        res_2 = GameweekResult.objects.get(member=self.members[1], gameweek=self.gw)
        res_3 = GameweekResult.objects.get(member=self.members[2], gameweek=self.gw)

        self.assertEqual(res_1.league_rank, 1)
        self.assertEqual(res_2.league_rank, 1)
        self.assertEqual(res_1.gw_prize_won, Decimal('208.34'))
        self.assertEqual(res_2.gw_prize_won, Decimal('208.34'))

        self.assertEqual(res_3.league_rank, 3)
        self.assertEqual(res_3.gw_prize_won, Decimal('83.33'))

    def test_member_joined_gw2_ineligible_for_gw1_prize(self):
        gw1 = Gameweek.objects.create(
            number=1,
            name="Gameweek 1",
            deadline_time=self.deadline,
            status='finished',
            prize_pool_amount=Decimal('500.00')
        )
        # Member 1 joined in GW2
        self.members[0].joined_gameweek = 2
        self.members[0].save()

        # Member 1 has a result for GW1
        GameweekResult.objects.create(
            member=self.members[0],
            gameweek=gw1,
            gw_points=0,
            transfer_cost=0
        )
        from league.services.payout_engine import is_member_eligible_for_prize
        self.assertFalse(is_member_eligible_for_prize(self.members[0], gw1))
