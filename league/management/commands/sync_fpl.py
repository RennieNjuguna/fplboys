from django.core.management.base import BaseCommand
from django.conf import settings
from league.services.fpl_client import FPLSyncService
from league.models import Gameweek, Member, GameweekResult


class Command(BaseCommand):
    help = "Synchronizes Gameweek schedules, league standings, player scores, and calculates top 3 payouts from FPL API."

    def add_arguments(self, parser):
        parser.add_argument(
            '--league',
            type=int,
            default=settings.FPL_LEAGUE_ID,
            help=f"FPL Classic League ID (default: {settings.FPL_LEAGUE_ID})"
        )
        parser.add_argument(
            '--gw',
            type=int,
            default=None,
            help="Specific Gameweek number to sync"
        )

    def handle(self, *args, **options):
        league_id = options['league']
        target_gw = options['gw']

        self.stdout.write(self.style.NOTICE(f"Connecting to FPL API for League ID {league_id}..."))
        service = FPLSyncService(league_id=league_id)

        # 1. Sync Gameweeks
        self.stdout.write("1. Syncing Gameweek calendar & deadlines...")
        gws = service.sync_gameweeks()
        self.stdout.write(self.style.SUCCESS(f"   -> Synced {len(gws)} gameweeks successfully."))

        # 2. Sync Members
        self.stdout.write("2. Syncing mini-league members from standings...")
        members = service.sync_members()
        self.stdout.write(self.style.SUCCESS(f"   -> Synced {len(members)} league members."))

        # 3. Sync Results & Payouts
        self.stdout.write("3. Syncing manager points, hits, and calculating payouts...")
        res = service.sync_gameweek_results(target_gw_number=target_gw)
        self.stdout.write(self.style.SUCCESS(
            f"   -> Updated {res['results_updated']} result records across {res['gameweeks_processed']} gameweeks."
        ))

        # Print top 3 winners of completed gameweeks
        completed_gws = Gameweek.objects.filter(status='finished').order_by('-number')
        if completed_gws.exists():
            self.stdout.write(self.style.MIGRATE_HEADING("\n--- Recent Gameweek Winners & Payouts ---"))
            for gw in completed_gws[:3]:
                self.stdout.write(self.style.WARNING(f"\n{gw.name} Payouts (Prize Pool: Ksh. {gw.prize_pool_amount}):"))
                winners = gw.results.filter(is_top3=True).order_by('league_rank')
                for w in winners:
                    self.stdout.write(
                        f"   Rank {w.league_rank}: {w.member.manager_name} ({w.member.team_name}) "
                        f"- Net: {w.net_points} pts (Hits: -{w.transfer_cost}) -> Prize: Ksh. {w.gw_prize_won}"
                    )

        self.stdout.write(self.style.SUCCESS("\n[SUCCESS] FPL Synchronization completed successfully!"))
