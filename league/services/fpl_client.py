import logging
from datetime import datetime
from decimal import Decimal
import requests
from django.utils import timezone
from django.utils.dateparse import parse_datetime
import pytz

from league.models import Member, Gameweek, GameweekResult
from league.services.payout_engine import calculate_gameweek_payouts
from treasury.models import AuditLog

logger = logging.getLogger(__name__)

FPL_BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
FPL_LEAGUE_STANDINGS_URL = "https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/"
FPL_ENTRY_HISTORY_URL = "https://fantasy.premierleague.com/api/entry/{entry_id}/history/"
FPL_EVENT_LIVE_URL = "https://fantasy.premierleague.com/api/event/{event_id}/live/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}


class FPLSyncService:
    def __init__(self, league_id=1868934, timeout=15):
        self.league_id = league_id
        self.timeout = timeout

    def fetch_bootstrap(self):
        """Fetch bootstrap static data including all gameweek events"""
        try:
            resp = requests.get(FPL_BOOTSTRAP_URL, headers=HEADERS, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Error fetching FPL bootstrap data: {e}")
            return None

    def fetch_league_standings(self):
        """Fetch classic league standings for FPL Boys"""
        url = FPL_LEAGUE_STANDINGS_URL.format(league_id=self.league_id)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Error fetching FPL league standings: {e}")
            return None

    def fetch_entry_history(self, entry_id):
        """Fetch historical gameweek results for a specific manager entry"""
        url = FPL_ENTRY_HISTORY_URL.format(entry_id=entry_id)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Error fetching FPL history for entry {entry_id}: {e}")
            return None

    def sync_gameweeks(self, bootstrap_data=None):
        """
        Creates or updates all 38 Gameweeks from FPL bootstrap-static data.
        """
        if not bootstrap_data:
            bootstrap_data = self.fetch_bootstrap()

        if not bootstrap_data or 'events' not in bootstrap_data:
            logger.warning("No events found in FPL bootstrap data.")
            return []

        synced_gws = []
        for event in bootstrap_data['events']:
            gw_num = event['id']
            gw_name = event.get('name', f"Gameweek {gw_num}")
            deadline_str = event.get('deadline_time')

            if deadline_str:
                deadline_dt = parse_datetime(deadline_str)
                if timezone.is_naive(deadline_dt):
                    deadline_dt = timezone.make_aware(deadline_dt, pytz.UTC)
            else:
                deadline_dt = timezone.now()

            # Determine status
            is_finished = event.get('finished', False)
            is_current = event.get('is_current', False)
            is_next = event.get('is_next', False)

            if is_finished:
                status = 'finished'
            elif is_current or (timezone.now() >= deadline_dt and not is_finished):
                status = 'active'
            else:
                status = 'upcoming'

            month = deadline_dt.month if deadline_dt else 8

            gw, created = Gameweek.objects.update_or_create(
                number=gw_num,
                defaults={
                    'name': gw_name,
                    'deadline_time': deadline_dt,
                    'status': status,
                    'is_current': is_current,
                    'is_next': is_next,
                    'month': month,
                    'prize_pool_amount': Decimal('500.00'),
                }
            )
            synced_gws.append(gw)

        return synced_gws

    def sync_members(self, standings_data=None):
        """
        Syncs members from league standings and new_entries.
        """
        if not standings_data:
            standings_data = self.fetch_league_standings()

        if not standings_data:
            logger.warning("No standings data returned from FPL API.")
            return []

        synced_members = []

        # 1. Existing standings results
        results = standings_data.get('standings', {}).get('results', [])
        for item in results:
            entry_id = item.get('entry')
            team_name = item.get('entry_name', f"Team {entry_id}")
            player_name = item.get('player_name', 'FPL Manager')
            avatar_url = item.get('club_badge_src')

            member, _ = Member.objects.update_or_create(
                fpl_entry_id=entry_id,
                defaults={
                    'team_name': team_name,
                    'manager_name': player_name,
                    'avatar_url': avatar_url,
                    'is_active': True,
                }
            )
            synced_members.append(member)

        # 2. New entries (e.g. 10th member who joined)
        new_entries = standings_data.get('new_entries', {}).get('results', [])
        for item in new_entries:
            entry_id = item.get('entry')
            team_name = item.get('entry_name', f"Team {entry_id}")
            first_name = item.get('player_first_name', '')
            last_name = item.get('player_last_name', '')
            player_name = f"{first_name} {last_name}".strip() or "FPL Manager"

            member, _ = Member.objects.update_or_create(
                fpl_entry_id=entry_id,
                defaults={
                    'team_name': team_name,
                    'manager_name': player_name,
                    'is_active': True,
                }
            )
            if member not in synced_members:
                synced_members.append(member)

        return synced_members

    def sync_gameweek_results(self, target_gw_number=None):
        """
        Fetches member scores and transfer costs, updates GameweekResult records,
        and triggers payout calculations for finished/active gameweeks.
        """
        members = Member.objects.filter(is_active=True)
        if not members.exists():
            self.sync_members()
            members = Member.objects.filter(is_active=True)

        if target_gw_number:
            gameweeks = Gameweek.objects.filter(number=target_gw_number)
        else:
            # Sync for all gameweeks that are not 'upcoming' (i.e. active or finished)
            gameweeks = Gameweek.objects.filter(status__in=['active', 'finished']).order_by('number')

        updated_results_count = 0

        for member in members:
            history = self.fetch_entry_history(member.fpl_entry_id)
            if not history or 'current' not in history:
                continue

            current_events = {item['event']: item for item in history['current']}

            for gw in gameweeks:
                if gw.number < member.joined_gameweek:
                    gw_res, _ = GameweekResult.objects.update_or_create(
                        member=member,
                        gameweek=gw,
                        defaults={
                            'gw_points': 0,
                            'transfer_cost': 0,
                            'net_points': 0,
                            'overall_rank': 0,
                        }
                    )
                    updated_results_count += 1
                elif gw.number in current_events:
                    ev_data = current_events[gw.number]
                    points = ev_data.get('points', 0)
                    transfers_cost = ev_data.get('event_transfers_cost', 0)
                    overall_rank = ev_data.get('overall_rank', 0)

                    gw_res, _ = GameweekResult.objects.update_or_create(
                        member=member,
                        gameweek=gw,
                        defaults={
                            'gw_points': points,
                            'transfer_cost': transfers_cost,
                            'net_points': points - transfers_cost,
                            'overall_rank': overall_rank,
                        }
                    )
                    updated_results_count += 1

        # Now calculate payouts for each synced gameweek
        for gw in gameweeks:
            calculate_gameweek_payouts(gw)

        AuditLog.objects.create(
            action='FPL_SYNC',
            description=f"Successfully synced {len(members)} members and results for {gameweeks.count()} gameweeks.",
            performed_by='FPLSyncService'
        )

        return {
            'members_synced': members.count(),
            'gameweeks_processed': gameweeks.count(),
            'results_updated': updated_results_count,
        }
