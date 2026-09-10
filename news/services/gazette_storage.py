import os
import json
import logging
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from league.models import Gameweek, Member
from news.models import RoastEdition, ManagerRoastItem
from news.services.roast_engine import ensure_news_tables_exist

logger = logging.getLogger(__name__)

EDITIONS_DIR = os.path.join(settings.BASE_DIR, 'news', 'editions')


def ensure_editions_dir():
    os.makedirs(EDITIONS_DIR, exist_ok=True)


def export_edition_to_disk(edition: RoastEdition) -> str:
    """
    Exports a RoastEdition and all its ManagerRoastItems to a version-controlled JSON file.
    Example: news/editions/gw3.json
    """
    ensure_editions_dir()
    gw_num = edition.gameweek.number
    filepath = os.path.join(EDITIONS_DIR, f"gw{gw_num}.json")

    roasts = []
    for r in edition.manager_roasts.select_related('member').order_by('order', 'rank_in_gw'):
        roasts.append({
            'manager_name': r.member.manager_name,
            'team_name': r.member.team_name,
            'rank_in_gw': r.rank_in_gw,
            'net_points': r.net_points,
            'badge': r.badge,
            'roast_title': r.roast_title,
            'roast_body': r.roast_body,
            'verdict': r.verdict,
            'order': r.order,
        })

    data = {
        'edition_number': edition.edition_number,
        'gameweek_number': gw_num,
        'headline': edition.headline,
        'subheadline': edition.subheadline,
        'publish_date': edition.publish_date.isoformat() if edition.publish_date else timezone.now().isoformat(),
        'chief_editor': edition.chief_editor,
        'weather_report': edition.weather_report,
        'editorial_lead': edition.editorial_lead,
        'clown_of_the_week_name': edition.clown_of_the_week.manager_name if edition.clown_of_the_week else None,
        'clown_reason': edition.clown_reason,
        'king_of_the_week_name': edition.king_of_the_week.manager_name if edition.king_of_the_week else None,
        'king_reason': edition.king_reason,
        'quote_of_the_week': edition.quote_of_the_week,
        'quote_author': edition.quote_author,
        'defaulter_roast': edition.defaulter_roast,
        'transfer_hit_roast': edition.transfer_hit_roast,
        'classified_ads': edition.classified_ads,
        'is_published': edition.is_published,
        'manager_roasts': roasts,
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return filepath


def load_edition_from_disk(gw_number: int, force_publish=True) -> RoastEdition:
    """
    Loads and upserts a curated Gazette edition from news/editions/gw{gw_number}.json into the database.
    """
    ensure_news_tables_exist()
    filepath = os.path.join(EDITIONS_DIR, f"gw{gw_number}.json")
    if not os.path.exists(filepath):
        return None

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    try:
        gw = Gameweek.objects.get(number=gw_number)
    except Gameweek.DoesNotExist:
        gw, _ = Gameweek.objects.get_or_create(
            number=gw_number,
            defaults={
                'name': f"Gameweek {gw_number}",
                'deadline_time': timezone.now(),
                'status': 'finished'
            }
        )

    clown_member = None
    if data.get('clown_of_the_week_name'):
        clown_member = Member.objects.filter(manager_name__icontains=data['clown_of_the_week_name'].split()[0]).first()

    king_member = None
    if data.get('king_of_the_week_name'):
        king_member = Member.objects.filter(manager_name__icontains=data['king_of_the_week_name'].split()[0]).first()

    with transaction.atomic():
        edition, _ = RoastEdition.objects.update_or_create(
            gameweek=gw,
            defaults={
                'edition_number': data.get('edition_number', gw_number),
                'headline': data.get('headline', f"THE GAMEWEEK {gw_number} GAZETTE"),
                'subheadline': data.get('subheadline', ''),
                'chief_editor': data.get('chief_editor', 'The League Scribe'),
                'weather_report': data.get('weather_report', ''),
                'editorial_lead': data.get('editorial_lead', ''),
                'clown_of_the_week': clown_member,
                'clown_reason': data.get('clown_reason', ''),
                'king_of_the_week': king_member,
                'king_reason': data.get('king_reason', ''),
                'quote_of_the_week': data.get('quote_of_the_week', ''),
                'quote_author': data.get('quote_author', ''),
                'defaulter_roast': data.get('defaulter_roast', ''),
                'transfer_hit_roast': data.get('transfer_hit_roast', ''),
                'classified_ads': data.get('classified_ads', []),
                'is_published': force_publish if force_publish is not None else data.get('is_published', True),
            }
        )

        edition.manager_roasts.all().delete()

        for rdata in data.get('manager_roasts', []):
            m_name = rdata.get('manager_name', '')
            member = Member.objects.filter(manager_name__icontains=m_name.split()[0]).first()
            if not member:
                member = Member.objects.filter(team_name__icontains=rdata.get('team_name', '')).first()

            if member:
                ManagerRoastItem.objects.create(
                    edition=edition,
                    member=member,
                    rank_in_gw=rdata.get('rank_in_gw', 1),
                    net_points=rdata.get('net_points', 0),
                    badge=rdata.get('badge', 'PARTICIPANT'),
                    roast_title=rdata.get('roast_title', f"{member.manager_name} Review"),
                    roast_body=rdata.get('roast_body', ''),
                    verdict=rdata.get('verdict', ''),
                    order=rdata.get('order', 0),
                )

    return edition


def sync_all_stored_editions(overwrite_existing=False):
    """
    Scans news/editions/*.json and syncs any missing or stored editions into SQLite.
    Guarantees that git-pulled JSON editions immediately appear online without clobbering existing DB editions.
    """
    import sys
    if 'test' in sys.argv:
        return []

    ensure_news_tables_exist()
    ensure_editions_dir()

    synced = []
    if not os.path.exists(EDITIONS_DIR):
        return synced

    for fname in sorted(os.listdir(EDITIONS_DIR)):
        if fname.startswith('gw') and fname.endswith('.json'):
            try:
                gw_str = fname.replace('gw', '').replace('.json', '')
                gw_num = int(gw_str)
                if not overwrite_existing and RoastEdition.objects.filter(edition_number=gw_num).exists():
                    continue
                ed = load_edition_from_disk(gw_num, force_publish=None)
                if ed:
                    synced.append(ed)
            except Exception as e:
                logger.warning(f"Failed to sync edition from {fname}: {e}")

    return synced
