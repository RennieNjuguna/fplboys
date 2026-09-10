import json
from django.core.management.base import BaseCommand
from news.services.gw_analyzer import analyze_gameweek_performance


class Command(BaseCommand):
    help = "Inspects tactical performance for all managers in a Gameweek (chips, captains, bench points, differentials, hits)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--gw',
            type=int,
            required=True,
            help='Gameweek number to inspect (e.g. --gw 1)',
        )
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output raw JSON payload',
        )

    def handle(self, *args, **options):
        gw_num = options['gw']
        as_json = options.get('json', False)

        data = analyze_gameweek_performance(gw_num)

        if as_json:
            self.stdout.write(json.dumps(data, indent=2, default=str))
            return

        self.stdout.write(self.style.SUCCESS(f"\n======================================================="))
        self.stdout.write(self.style.SUCCESS(f"  FPL BOYZ GAMEWEEK {gw_num} TACTICAL AUTOPSY"))
        self.stdout.write(self.style.SUCCESS(f"=======================================================\n"))

        for m in data['managers']:
            if m.get('pardon'):
                self.stdout.write(self.style.WARNING(
                    f"[*] {m['manager_name']} ({m['team_name']}): PARDONED (Joined in GW {m['joined_gw']})"
                ))
                continue

            cap = m.get('captain')
            cap_str = f"{cap['name']} ({cap['total_points']} pts)" if cap else "None"
            chip_str = f" [CHIP: {m['active_chip'].upper()}]" if m.get('active_chip') else ""
            hit_str = f" [HIT: -{m['transfer_cost']} pts]" if m.get('transfer_cost') else ""

            self.stdout.write(self.style.HTTP_INFO(
                f"Rank #{m.get('rank_in_gw')}: {m['manager_name']} ({m['team_name']}) - Net: {m['net_points']} pts{chip_str}{hit_str}"
            ))
            self.stdout.write(f"   - Captain: {cap_str}")
            self.stdout.write(f"   - Bench points wasted: {m.get('bench_points', 0)} pts")
            
            top_scorers = ", ".join([f"{p['name']} ({p['points']} pts)" for p in m.get('top_scorers', [])])
            self.stdout.write(f"   - Key Starters: {top_scorers}")
            if m.get('prize_won', 0) > 0:
                self.stdout.write(self.style.SUCCESS(f"   - Prize Won: Ksh. {m['prize_won']:,.2f}"))
            self.stdout.write("")
