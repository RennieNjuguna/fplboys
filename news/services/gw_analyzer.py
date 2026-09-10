import logging
from league.models import Member, Gameweek, GameweekResult
from league.services.fpl_client import FPLSyncService

logger = logging.getLogger(__name__)


def analyze_gameweek_performance(gw_number: int):
    """
    Performs an in-depth tactical autopsy of a specific Gameweek for all league members.
    Pulls:
    - Active chips (Wildcard, 3x Captain, Bench Boost, Free Hit)
    - Captain & Vice-Captain selections and points scored
    - Bench points left stranded
    - Transfers made and transfer hit costs
    - Top scorers and flop picks in the squad
    - League ranking and prize payouts
    """
    sync_service = FPLSyncService()
    bootstrap = sync_service.fetch_bootstrap()
    
    # Map element IDs to player info
    players = {}
    if bootstrap and 'elements' in bootstrap:
        for p in bootstrap['elements']:
            players[p['id']] = {
                'id': p['id'],
                'web_name': p.get('web_name', 'Player'),
                'full_name': f"{p.get('first_name', '')} {p.get('second_name', '')}".strip(),
                'team_id': p.get('team'),
                'element_type': p.get('element_type'),
            }

    # Map teams if available
    teams = {}
    if bootstrap and 'teams' in bootstrap:
        for t in bootstrap['teams']:
            teams[t['id']] = t.get('short_name', 'TEAM')

    # Fetch live event stats for player points in this GW
    live_event = sync_service.fetch_event_live(gw_number)
    live_stats = {}
    if live_event and 'elements' in live_event:
        for el in live_event['elements']:
            live_stats[el['id']] = el.get('stats', {}).get('total_points', 0)

    # Get Gameweek from DB
    try:
        gw = Gameweek.objects.get(number=gw_number)
    except Gameweek.DoesNotExist:
        gw = None

    members = Member.objects.filter(is_active=True).order_by('manager_name')
    results_map = {}
    if gw:
        for r in GameweekResult.objects.filter(gameweek=gw).select_related('member'):
            results_map[r.member_id] = r

    autopsy = []

    for member in members:
        # Check if joined later
        if gw and member.joined_gameweek > gw_number:
            autopsy.append({
                'member_id': member.id,
                'manager_name': member.manager_name,
                'team_name': member.team_name,
                'joined_gw': member.joined_gameweek,
                'pardon': True,
                'rank_in_gw': None,
                'net_points': 0,
                'gw_points': 0,
                'transfer_cost': 0,
                'active_chip': None,
                'captain': None,
                'vice_captain': None,
                'bench_points': 0,
                'top_scorers': [],
                'starters': [],
                'bench': [],
                'prize_won': 0.0,
            })
            continue

        picks_data = sync_service.fetch_entry_picks(member.fpl_entry_id, gw_number)
        db_res = results_map.get(member.id)

        if not picks_data:
            autopsy.append({
                'member_id': member.id,
                'manager_name': member.manager_name,
                'team_name': member.team_name,
                'pardon': False,
                'rank_in_gw': db_res.league_rank if db_res else None,
                'net_points': db_res.net_points if db_res else 0,
                'gw_points': db_res.gw_points if db_res else 0,
                'transfer_cost': db_res.transfer_cost if db_res else 0,
                'active_chip': None,
                'captain': None,
                'vice_captain': None,
                'bench_points': 0,
                'top_scorers': [],
                'starters': [],
                'bench': [],
                'prize_won': float(db_res.gw_prize_won) if db_res else 0.0,
            })
            continue

        active_chip = picks_data.get('active_chip')
        entry_history = picks_data.get('entry_history', {})
        gw_points = entry_history.get('points', db_res.gw_points if db_res else 0)
        transfer_cost = entry_history.get('event_transfers_cost', db_res.transfer_cost if db_res else 0)
        net_points = gw_points - transfer_cost
        bench_points = entry_history.get('points_on_bench', 0)
        transfers_made = entry_history.get('event_transfers', 0)

        captain_info = None
        vice_captain_info = None
        starters = []
        bench = []

        for pick in picks_data.get('picks', []):
            el_id = pick.get('element')
            p_info = players.get(el_id, {'web_name': f"Player #{el_id}", 'team_id': None})
            t_name = teams.get(p_info.get('team_id'), '')
            pts = live_stats.get(el_id, 0)
            multiplier = pick.get('multiplier', 1)
            total_pts = pts * multiplier
            pos = pick.get('position', 1)

            pick_obj = {
                'id': el_id,
                'name': p_info['web_name'],
                'team': t_name,
                'points': pts,
                'multiplier': multiplier,
                'total_points': total_pts,
                'is_captain': pick.get('is_captain', False),
                'is_vice_captain': pick.get('is_vice_captain', False),
                'position': pos,
            }

            if pick.get('is_captain'):
                captain_info = pick_obj
            if pick.get('is_vice_captain'):
                vice_captain_info = pick_obj

            if multiplier > 0:
                starters.append(pick_obj)
            else:
                bench.append(pick_obj)

        starters.sort(key=lambda x: x['total_points'], reverse=True)
        bench.sort(key=lambda x: x['points'], reverse=True)

        autopsy.append({
            'member_id': member.id,
            'manager_name': member.manager_name,
            'team_name': member.team_name,
            'pardon': False,
            'rank_in_gw': db_res.league_rank if db_res else None,
            'net_points': net_points,
            'gw_points': gw_points,
            'transfer_cost': transfer_cost,
            'transfers_made': transfers_made,
            'active_chip': active_chip,
            'captain': captain_info,
            'vice_captain': vice_captain_info,
            'bench_points': bench_points,
            'top_scorers': starters[:3] if starters else [],
            'starters': starters,
            'bench': bench,
            'prize_won': float(db_res.gw_prize_won) if db_res else 0.0,
        })

    # Sort by rank and net_points
    autopsy.sort(key=lambda x: (x.get('rank_in_gw') or 999, -(x.get('net_points') or 0)))
    return {
        'gameweek': gw_number,
        'managers': autopsy,
    }
