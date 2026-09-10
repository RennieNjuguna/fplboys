from django.core.management.base import BaseCommand
from news.services.gazette_storage import sync_all_stored_editions, load_edition_from_disk


class Command(BaseCommand):
    help = "Loads and syncs curated Gazette editions from news/editions/*.json into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            '--gw',
            type=int,
            help='Specific gameweek number to load from disk (e.g. --gw 3)',
        )

    def handle(self, *args, **options):
        gw_num = options.get('gw')

        if gw_num:
            ed = load_edition_from_disk(gw_num, force_publish=True)
            if ed:
                self.stdout.write(self.style.SUCCESS(
                    f"[GAZETTE] Successfully loaded and published Issue #{ed.edition_number} for GW {gw_num} from disk."
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f"[GAZETTE] No stored file found for news/editions/gw{gw_num}.json"
                ))
        else:
            synced = sync_all_stored_editions()
            self.stdout.write(self.style.SUCCESS(
                f"[GAZETTE] Successfully synced {len(synced)} stored Gazette edition(s) into database."
            ))
