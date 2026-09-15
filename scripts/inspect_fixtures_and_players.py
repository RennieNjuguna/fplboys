import os
import sys
import django
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fpl_boys.settings')
django.setup()

from league.services.fpl_client import FPLSyncService
from league.models import Member

def inspect_all():
    s = FPLSyncService()
    bootstrap = s.fetch_bootstrap()
    teams = {t['id']: t['name'] for t in bootstrap['teams']}
    team_shorts = {t['id']: t['short_name'] for t in bootstrap['teams']}
    players = {p['id']: p for p in bootstrap['elements']}

    # Fixtures
    fixtures_resp = requests.get('https://fantasy.premierleague.com/api/fixtures/?event=4', headers={"User-Agent": "Mozilla/5.0"}).json()
    print("=================== OFFICIAL GW 4 FIXTURES & SCORES ===================")
    for f in fixtures_resp:
        h_name = teams.get(f['team_h'], f"Team {f['team_h']}")
        a_name = teams.get(f['team_a'], f"Team {f['team_a']}")
        h_score = f.get('team_h_score', 0)
        a_score = f.get('team_a_score', 0)
        print(f"  {h_name} {h_score} - {a_score} {a_name}")

    # Live stats
    live_resp = s.fetch_event_live(4)
    live_stats = {el['id']: el for el in live_resp.get('elements', [])}

    print("\n=================== TOP PERFORMING PLAYERS IN GW 4 ===================")
    top_players = []
    for el_id, el_data in live_stats.items():
        p_info = players.get(el_id, {})
        pts = el_data.get('stats', {}).get('total_points', 0)
        stats = el_data.get('stats', {})
        goals = stats.get('goals_scored', 0)
        assists = stats.get('assists', 0)
        clean_sheets = stats.get('clean_sheets', 0)
        bonus = stats.get('bonus', 0)
        t_short = team_shorts.get(p_info.get('team'), '')
        top_players.append((p_info.get('web_name', f"Player {el_id}"), t_short, pts, goals, assists, clean_sheets, bonus))

    top_players.sort(key=lambda x: x[2], reverse=True)
    for p in top_players[:15]:
        print(f"  {p[0]} ({p[1]}): {p[2]} pts | Goals: {p[3]}, Assists: {p[4]}, CS: {p[5]}, Bonus: {p[6]}")

    print("\n=================== SQUAD DETAILS BY MANAGER ===================")
    for m in Member.objects.all():
        picks = s.fetch_entry_picks(m.fpl_entry_id, 4)
        hist = picks.get('entry_history', {})
        pts = hist.get('points', 0)
        cap = None
        for p in picks.get('picks', []):
            if p.get('is_captain'):
                p_info = players.get(p['element'], {})
                pts_p = live_stats.get(p['element'], {}).get('stats', {}).get('total_points', 0)
                cap = f"{p_info.get('web_name')} ({pts_p} x {p.get('multiplier')} = {pts_p * p.get('multiplier')} pts)"
        print(f"{m.manager_name} ({m.team_name}) - Total: {pts} pts | Captain: {cap}")

if __name__ == '__main__':
    inspect_all()
