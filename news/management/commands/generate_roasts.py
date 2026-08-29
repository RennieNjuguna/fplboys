from django.core.management.base import BaseCommand
from league.models import Gameweek
from news.services.roast_engine import generate_roast_edition


class Command(BaseCommand):
    help = "Generates or updates brutal newspaper roasts for Gameweek editions in The FPL Boys Gazette."

    def add_arguments(self, parser):
        parser.add_argument(
            '--gw',
            type=int,
            help='Specific gameweek number to generate roasts for (e.g. --gw 1)',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Generate roasts for all finished/active gameweeks',
        )

    def handle(self, *args, **options):
        gw_num = options.get('gw')
        all_gws = options.get('all')

        if gw_num:
            try:
                gw = Gameweek.objects.get(number=gw_num)
                edition = generate_roast_edition(gw, force_update=True)
                self.stdout.write(self.style.SUCCESS(f"[GAZETTE] Successfully generated Gazette Edition #{edition.edition_number} for GW {gw.number}!"))
            except Gameweek.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Gameweek {gw_num} does not exist."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error generating roasts for GW {gw_num}: {e}"))

        elif all_gws:
            finished_gws = Gameweek.objects.filter(status__in=['finished', 'active']).order_by('number')
            count = 0
            for gw in finished_gws:
                try:
                    edition = generate_roast_edition(gw, force_update=True)
                    self.stdout.write(self.style.SUCCESS(f"[GAZETTE] Generated Issue #{edition.edition_number} for GW {gw.number}"))
                    count += 1
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"Skipping GW {gw.number}: {e}"))
            self.stdout.write(self.style.SUCCESS(f"\n[DONE] Generated {count} Gazette editions."))

        else:
            # Default: latest finished or active gameweek
            latest_gw = Gameweek.objects.filter(status__in=['finished', 'active']).order_by('-number').first()
            if not latest_gw:
                self.stdout.write(self.style.WARNING("No finished or active gameweeks found."))
                return

            try:
                edition = generate_roast_edition(latest_gw, force_update=True)
                self.stdout.write(self.style.SUCCESS(f"[GAZETTE] Successfully generated Gazette Issue #{edition.edition_number} for latest GW {latest_gw.number}!"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error generating roasts: {e}"))

