import random
from decimal import Decimal
from django.utils import timezone
from django.db import connection, transaction
from league.models import Gameweek, GameweekResult, Member
from treasury.models import Payment
from news.models import RoastEdition, ManagerRoastItem


def ensure_news_tables_exist():
    """
    Guarantees SQLite tables for news models exist even if migrations haven't run on server.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS "news_roastedition" (
                "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                "edition_number" integer NOT NULL UNIQUE,
                "headline" varchar(255) NOT NULL,
                "subheadline" varchar(300) NOT NULL,
                "publish_date" datetime NOT NULL,
                "chief_editor" varchar(120) NOT NULL,
                "weather_report" varchar(200) NOT NULL,
                "editorial_lead" text NOT NULL,
                "clown_reason" text NOT NULL,
                "king_reason" text NOT NULL,
                "quote_of_the_week" text NOT NULL,
                "quote_author" varchar(120) NOT NULL,
                "defaulter_roast" text NOT NULL,
                "transfer_hit_roast" text NOT NULL,
                "classified_ads_raw" text NOT NULL,
                "is_published" bool NOT NULL,
                "created_at" datetime NOT NULL,
                "updated_at" datetime NOT NULL,
                "clown_of_the_week_id" bigint NULL REFERENCES "league_member" ("id") DEFERRABLE INITIALLY DEFERRED,
                "gameweek_id" bigint NOT NULL UNIQUE REFERENCES "league_gameweek" ("id") DEFERRABLE INITIALLY DEFERRED,
                "king_of_the_week_id" bigint NULL REFERENCES "league_member" ("id") DEFERRABLE INITIALLY DEFERRED
            );
            ''')
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS "news_managerroastitem" (
                "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                "rank_in_gw" integer NOT NULL,
                "net_points" integer NOT NULL,
                "badge" varchar(50) NOT NULL,
                "roast_title" varchar(255) NOT NULL,
                "roast_body" text NOT NULL,
                "verdict" varchar(200) NOT NULL,
                "order" integer NOT NULL,
                "edition_id" bigint NOT NULL REFERENCES "news_roastedition" ("id") DEFERRABLE INITIALLY DEFERRED,
                "member_id" bigint NOT NULL REFERENCES "league_member" ("id") DEFERRABLE INITIALLY DEFERRED
            );
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS "news_roastedition_clown_of_the_week_id_07bddf93" ON "news_roastedition" ("clown_of_the_week_id");')
            cursor.execute('CREATE INDEX IF NOT EXISTS "news_roastedition_king_of_the_week_id_0d129dbc" ON "news_roastedition" ("king_of_the_week_id");')
            cursor.execute('CREATE INDEX IF NOT EXISTS "news_managerroastitem_edition_id_73aea9f1" ON "news_managerroastitem" ("edition_id");')
            cursor.execute('CREATE INDEX IF NOT EXISTS "news_managerroastitem_member_id_91886d09" ON "news_managerroastitem" ("member_id");')
    except Exception:
        pass


SAMPLE_CLASSIFIEDS = [
    {
        'title': 'FOR SALE: Triple Captain Chip',
        'desc': 'Slightly used in GW 1. Yielded 3 points total. Comes with complimentary box of tissues and regret.',
        'contact': 'Call 0700-REGRET-FPL'
    },
    {
        'title': 'LOST & FOUND: Defending Pride',
        'desc': 'Lost somewhere between the 60th and 90th minute. If found, please return to bottom 3 managers.',
        'contact': 'Drop off at Relegation Zone desk'
    },
    {
        'title': 'WANTED: Ksh. 150 Contribution',
        'desc': 'Treasurer is actively scanning M-Pesa. Defaulters will be forced to buy the BBQ charcoal.',
        'contact': 'M-Pesa Paybill #542222'
    },
    {
        'title': 'SERVICES: Professional Excuse Generator',
        'desc': "Expert explanations for why 'Pep Roulette' ruined your weekend. Guaranteed to sound almost believable on WhatsApp.",
        'contact': 'Visit www.itsnotmyfaultfpl.com'
    },
]

WEATHER_REPORTS = [
    'Heavy storms over the relegation zone. 100% chance of bench regret and broken dreams.',
    'Scorching heat at the top of the table. Flukes are expected to cool down rapidly by next weekend.',
    'Foggy conditions throughout mid-table mediocrity. Zero tactical vision reported across all 10 managers.',
    'Flash flood warnings: River of tears flowing from managers who took -8 hits for 1 point.',
]


def generate_roast_edition(gameweek: Gameweek, force_update=True) -> RoastEdition:
    """
    Analyzes Gameweek results and payments to generate a savage, hilarious newspaper edition.
    """
    ensure_news_tables_exist()
    results = list(
        GameweekResult.objects.filter(gameweek=gameweek)
        .select_related('member')
        .order_by('league_rank', '-net_points')
    )
    if not results:
        raise ValueError(f"Cannot generate roasts for GW {gameweek.number}: No results found.")

    payments = {p.member_id: p for p in Payment.objects.filter(gameweek=gameweek, verified=True)}

    winner_res = results[0]
    last_res = results[-1]
    clown_res = last_res
    king_res = winner_res

    # Check for largest hit taker
    hit_takers = [r for r in results if r.transfer_cost > 0]
    hit_takers.sort(key=lambda r: r.transfer_cost, reverse=True)
    biggest_hit_taker = hit_takers[0] if hit_takers else None

    # Check defaulters / late payments
    late_or_unpaid = []
    for r in results:
        p = payments.get(r.member_id)
        if not p:
            late_or_unpaid.append((r.member, 'UNPAID'))
        elif p.is_late:
            late_or_unpaid.append((r.member, 'LATE (+50 Fine)'))

    gw_num = gameweek.number
    winner_name = winner_res.member.manager_name.upper()
    last_name = last_res.member.manager_name.upper()
    headline = f"GW {gw_num} MASSACRE: {winner_name} RIDES BLIND LUCK TO GLORY AS {last_name} ANCHORS THE CLOWN CAR!"
    subheadline = f"Official Issue #{gw_num}: A comprehensive autopsy of terrible captain choices, catastrophic benching blunders, and BBQ pot donations."

    # Editorial lead
    editorial_lead = (
        f"Welcome to Issue #{gw_num} of The FPL Boys Gazette, the only publication brave enough to tell you that your fantasy football acumen is comparable to a blindfolded monkey throwing darts at a fixture list. "
        f"This week, {winner_res.member.manager_name} ({winner_res.member.team_name}) somehow scraped together {winner_res.net_points} net points to finish atop the podium, proving once again that in this league, pure unadulterated luck beats tactical preparation every single day of the week. "
        f"Meanwhile at the rock bottom of the abyss, {last_res.member.manager_name} ({last_res.member.team_name}) put on a masterclass in embarrassment with a pitiful {last_res.net_points} points, successfully turning their team into a charity donation for the rest of the 10 managers. "
        f"Grab your coffee, read through the wreckage, and if your name is near the bottom, please remember to turn off your WhatsApp notifications before the group chat destroys whatever self-esteem you have left."
    )

    clown_reason = (
        f"{last_res.member.manager_name} secured rank #{last_res.league_rank} with an astounding {last_res.net_points} points. "
        f"Scientists are currently studying this performance to determine if it was physically possible to pick a worse lineup. "
        f"Verdict: Demotion to fantasy chess recommended."
    )

    king_reason = (
        f"{winner_res.member.manager_name} took top honors with {winner_res.net_points} net points, pocketing Ksh. {winner_res.gw_prize_won:,.2f}. "
        f"Don't let them convince you this was tactical genius—their captain barely touched the ball and their vice-captain was probably benched in real life. Enjoy the podium while it lasts!"
    )

    # Defaulter roast
    if late_or_unpaid:
        defaulter_names = ', '.join([f"{m.manager_name} ({status})" for m, status in late_or_unpaid])
        defaulter_roast = (
            f"The Treasurer sends special gratitude to our honorary BBQ Pot sponsors: {defaulter_names}. "
            f"Your inability to pay Ksh. 150 before the deadline has directly funded the nyama choma fund. We thank you for your voluntary financial sacrifice!"
        )
    else:
        defaulter_roast = "In an unprecedented miracle that shocked local economists, all 10 managers actually managed to pay on time. The Treasurer was seen crying tears of joy into their M-Pesa statements."

    # Hit roast
    if biggest_hit_taker:
        transfer_hit_roast = (
            f"Special Achievement in Financial Suicide: {biggest_hit_taker.member.manager_name} took a -{biggest_hit_taker.transfer_cost} point hit in transfers, "
            f"only to finish with {biggest_hit_taker.net_points} net points. That is roughly equivalent to burning a 1,000 shilling note to look for a 50-cent coin in the dark."
        )
    else:
        transfer_hit_roast = "Nobody took reckless transfer hits this week, robbing the Gazette of its favorite source of cheap comedy. Cowards, all of you."

    quote_of_the_week = f"\"I swear my team was mathematically optimized by an algorithm.\" — {last_res.member.manager_name} moments before scoring {last_res.net_points} points."
    quote_author = f"{last_res.member.manager_name} (Chief Tactical Clown)"

    weather = random.choice(WEATHER_REPORTS)

    with transaction.atomic():
        edition, created = RoastEdition.objects.update_or_create(
            gameweek=gameweek,
            defaults={
                'edition_number': gw_num,
                'headline': headline,
                'subheadline': subheadline,
                'publish_date': timezone.now(),
                'chief_editor': 'The Anonymous League Scribe',
                'weather_report': weather,
                'editorial_lead': editorial_lead,
                'clown_of_the_week': clown_res.member,
                'clown_reason': clown_reason,
                'king_of_the_week': king_res.member,
                'king_reason': king_reason,
                'quote_of_the_week': quote_of_the_week,
                'quote_author': quote_author,
                'defaulter_roast': defaulter_roast,
                'transfer_hit_roast': transfer_hit_roast,
                'classified_ads': SAMPLE_CLASSIFIEDS,
                'is_published': True,
            }
        )

        # Remove old manager roasts if updating
        edition.manager_roasts.all().delete()

        # Create individual manager roasts
        for r in results:
            rank = r.league_rank
            pts = r.net_points
            hits = r.transfer_cost
            manager = r.member

            is_last = (r == last_res)

            if rank == 1:
                badge = '👑 1ST PLACE (FLUKE WINNER)'
                title = f"{manager.manager_name} - King of the Jammy Bastards"
                body = (
                    f"{manager.manager_name}'s {manager.team_name} somehow scored {pts} points to take 1st place and Ksh. {r.gw_prize_won:,.2f}. "
                    f"Witnesses report zero tactical strategy—just pure, unadulterated cosmic fortune. Enjoy the bragging rights for the next 48 hours before reality sets in."
                )
                verdict = 'Verdict: Certified Lucky Fraud'
            elif is_last and len(results) > 1:
                badge = '🤡 CLOWN OF THE GAMEWEEK'
                title = f"{manager.manager_name} - The League Punchline"
                body = (
                    f"An unforgettable disasterclass of {pts} points to claim the undisputed wooden spoon at rank #{rank}. "
                    f"Please submit an apology letter to the group chat immediately. Your team didn't just underperform—it committed a footballing crime."
                )
                verdict = 'Verdict: Delete Team & Start Farming'
            elif rank == 2:
                badge = '🥈 2ND PLACE (FIRST LOSER)'
                title = f"{manager.manager_name} - The Consolation Prize Prince"
                body = (
                    f"Scored {pts} points to take 2nd place and Ksh. {r.gw_prize_won:,.2f}. "
                    f"So close to greatness, yet ultimately just the best of the losers. At least the M-Pesa payout covers lunch."
                )
                verdict = 'Verdict: Bronze Aspirations, Silver Reality'
            elif rank == 3:
                badge = '🥉 3RD PLACE (PODIUM SCRAPPER)'
                title = f"{manager.manager_name} - Scraped By On Skin of Teeth"
                body = (
                    f"Managed {pts} points to sneak onto the podium and grab Ksh. {r.gw_prize_won:,.2f}. "
                    f"One more yellow card from their defender and they would have been in the mid-table wasteland with the commoners."
                )
                verdict = 'Verdict: Barely Acceptable'
            elif 4 <= rank <= 7:
                badge = '😴 MID-TABLE MEDIOCRITY'
                title = f"{manager.manager_name} - The Definition of Irrelevance"
                hit_note = f" (including -{hits} in transfer hits)" if hits > 0 else ""
                body = (
                    f"Scored {pts} net points{hit_note} to settle comfortably into rank #{rank}. "
                    f"Neither good enough to win cash nor terrible enough to make front-page clown news. Just floating silently in the void of mid-table depression."
                )
                verdict = 'Verdict: Emotionally Numb'
            elif 8 <= rank <= 9:
                badge = '💀 RELEGATION TRENCH'
                title = f"{manager.manager_name} - Dangerously Close to Rock Bottom"
                body = (
                    f"Put up an abysmal {pts} points to land at rank #{rank}. "
                    f"Fans are already calling for emergency manager sackings. Your defenders conceded, your forwards blanked, and your midfield was basically doing cardio."
                )
                verdict = 'Verdict: Sinking Fast'
            else:
                badge = '🤡 CLOWN OF THE GAMEWEEK'
                title = f"{manager.manager_name} - The League Punchline"
                body = (
                    f"An unforgettable disasterclass of {pts} points to claim the undisputed wooden spoon at rank #{rank}. "
                    f"Please submit an apology letter to the group chat immediately. Your team didn't just underperform—it committed a footballing crime."
                )
                verdict = 'Verdict: Delete Team & Start Farming'

            ManagerRoastItem.objects.create(
                edition=edition,
                member=manager,
                rank_in_gw=rank,
                net_points=pts,
                badge=badge,
                roast_title=title,
                roast_body=body,
                verdict=verdict,
                order=rank
            )

    return edition
