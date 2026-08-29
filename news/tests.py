from decimal import Decimal
from datetime import timedelta
from django.test import TestCase, Client
from django.utils import timezone
from django.urls import reverse
from league.models import Member, Gameweek, GameweekResult
from treasury.models import Payment
from news.models import RoastEdition, ManagerRoastItem
from news.services.roast_engine import generate_roast_edition


class NewsGazetteTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.deadline = timezone.now() - timedelta(days=2)
        self.gw1 = Gameweek.objects.create(
            number=1,
            name="Gameweek 1",
            deadline_time=self.deadline,
            status='finished'
        )
        self.m1 = Member.objects.create(fpl_entry_id=101, manager_name="Winner Alpha", team_name="Alpha Stars")
        self.m2 = Member.objects.create(fpl_entry_id=102, manager_name="Clown Beta", team_name="Beta Flops")
        self.m3 = Member.objects.create(fpl_entry_id=103, manager_name="Mid Gamma", team_name="Gamma Mid")

        # Create results: m1=1st, m3=2nd, m2=last
        GameweekResult.objects.create(
            member=self.m1,
            gameweek=self.gw1,
            gw_points=75,
            transfer_cost=0,
            gw_prize_won=Decimal('250.00'),
            league_rank=1,
            is_top3=True
        )
        GameweekResult.objects.create(
            member=self.m3,
            gameweek=self.gw1,
            gw_points=50,
            transfer_cost=0,
            gw_prize_won=Decimal('166.67'),
            league_rank=2,
            is_top3=True
        )
        GameweekResult.objects.create(
            member=self.m2,
            gameweek=self.gw1,
            gw_points=25,
            transfer_cost=4,
            gw_prize_won=Decimal('0.00'),
            league_rank=3,
            is_top3=False
        )

        Payment.objects.create(
            member=self.m1,
            gameweek=self.gw1,
            amount_paid=Decimal('150.00'),
            verified=True,
            is_late=False
        )
        Payment.objects.create(
            member=self.m2,
            gameweek=self.gw1,
            amount_paid=Decimal('200.00'),
            verified=True,
            is_late=True,
            late_fine_amount=Decimal('50.00')
        )

    def test_generate_roast_edition_service(self):
        """Test roast engine generates complete edition with king, clown, and manager roasts"""
        edition = generate_roast_edition(self.gw1, force_update=True)
        self.assertEqual(edition.edition_number, 1)
        self.assertEqual(edition.gameweek, self.gw1)
        self.assertEqual(edition.king_of_the_week, self.m1)
        self.assertEqual(edition.clown_of_the_week, self.m2)
        self.assertIn("WINNER ALPHA", edition.headline)
        self.assertIn("CLOWN BETA", edition.headline)

        roasts = edition.manager_roasts.all()
        self.assertEqual(roasts.count(), 3)

        r_winner = roasts.filter(member=self.m1).first()
        self.assertIn("1ST PLACE", r_winner.badge)
        self.assertEqual(r_winner.net_points, 75)

        r_clown = roasts.filter(member=self.m2).first()
        self.assertIn("CLOWN", r_clown.badge)
        self.assertEqual(r_clown.net_points, 21)  # 25 - 4 hits = 21

    def test_gazette_view_renders_successfully(self):
        """Test the public Gazette newspaper view returns 200 and displays newspaper content"""
        resp = self.client.get('/news/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "THE FPL BOYZ GAZETTE")
        self.assertContains(resp, "Winner Alpha")
        self.assertContains(resp, "Clown Beta")

    def test_gazette_view_edition_switcher(self):
        """Test querying a specific edition via ?gw=1"""
        generate_roast_edition(self.gw1)
        resp = self.client.get('/news/?gw=1')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Issue #1")

    def test_gazette_api_data(self):
        """Test JSON API for edition returns structured roast fields"""
        edition = generate_roast_edition(self.gw1)
        resp = self.client.get(f'/news/api/edition/{edition.edition_number}/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['edition_number'], 1)
        self.assertEqual(data['king_of_the_week']['name'], "Winner Alpha")
        self.assertEqual(data['clown_of_the_week']['name'], "Clown Beta")
        self.assertEqual(len(data['manager_roasts']), 3)

