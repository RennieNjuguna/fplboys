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
    'Clear skies at the top of the table. Relegation zone experiencing severe thunder and tactical depression.',
    'Scorching heat on the podium. Mid-table floating in thick tactical fog.',
    'Heavy rain of green arrows for the champion; flash flood of tears in 10th place.',
    'Crisp footballing conditions across the league with high pressure on the bottom managers.',
]


def build_personalized_manager_review(manager, rank, pts, hits, prize_won, gw_num, is_last, winner_res, third_pts):
    name = manager.manager_name
    team = manager.team_name

    # 0. PARDONED / JOINED IN LATER GAMEWEEK
    if getattr(manager, 'joined_gameweek', 1) > gw_num:
        badge = f"🆕 JOINED GW {manager.joined_gameweek} (PARDON)"
        title = f"{name} - Official GW {gw_num} Pardon"
        body = f"{name} entered the league starting Gameweek {manager.joined_gameweek} and was granted an official committee pardon for GW {gw_num}. Zero points recorded, zero contributions owed, and ready to battle from GW {manager.joined_gameweek} onward!"
        verdict = f"Verdict: League Pardon / Joined GW {manager.joined_gameweek}"
        return badge, title, body, verdict

    # 1. CHAMPION (Rank 1)
    if rank == 1:
        badge = "👑 1ST PLACE (CHAMPION)"
        if "Marve" in name:
            title = f"{name} - Truly The 'Marve of the Match'"
            body = f"Living up to his team name with supreme swagger, Marve delivered the ultimate masterclass with {pts} points. Sits proudly atop the 10-man summit and banks Ksh. {prize_won:,.2f}."
            verdict = "Verdict: Certified Marve of the Match & Cash King"
        elif "Aron" in name:
            title = f"{name} - 'Arons' Seize The Crown"
            body = f"Aron completely flipped the script with an imperious {pts} points to seize 1st place and Ksh. {prize_won:,.2f}. From the trenches straight to the throne!"
            verdict = "Verdict: King of the Week"
        elif "Torque" in name or "Dennis" in name:
            title = f"{name} - 'DenniSkills' Put On A Masterclass"
            body = f"Dennis unleashed the full torque of DenniSkills with {pts} points to conquer 1st place and Ksh. {prize_won:,.2f} in prize money."
            verdict = "Verdict: Master Tactician & Champion"
        elif "Samuel" in name:
            title = f"{name} - 'maggry shiners' Outshine Everyone"
            body = f"Samuel's shiners blinded the competition with {pts} points, seizing 1st place and taking home Ksh. {prize_won:,.2f}."
            verdict = "Verdict: Crowned Champion"
        elif "King Chris" in name:
            title = f"{name} - The King Takes His Throne"
            body = f"King Chris painted a championship masterpiece with {pts} points to reign supreme atop the league, pocketing Ksh. {prize_won:,.2f}."
            verdict = "Verdict: Royal Victory"
        elif "Erick" in name:
            title = f"{name} - 'mambaaa' Delivers The Fatal Bite"
            body = f"Erick's 'mambaaa' struck with deadly precision for {pts} points to secure top spot and Ksh. {prize_won:,.2f}."
            verdict = "Verdict: Lethal Strike & GW Champion"
        elif "Renny" in name:
            title = f"{name} - The Young Ones Dominate The League"
            body = f"Renny's 'The Young Ones' outclassed every veteran manager with {pts} points to capture 1st place and Ksh. {prize_won:,.2f}."
            verdict = "Verdict: Class In Session"
        elif "Marvin" in name:
            title = f"{name} - Miracle At 'Don Bosco'"
            body = f"A miraculous resurgence! Marvin's 'Don Bosco' stunned the league with {pts} points to take 1st place and Ksh. {prize_won:,.2f}."
            verdict = "Verdict: Divine Masterclass"
        else:
            title = f"{name} - Tactical Masterclass & GW Winner"
            body = f"{name}'s '{team}' delivered a statement performance with {pts} points, taking 1st place and Ksh. {prize_won:,.2f}."
            verdict = "Verdict: Certified Baller & League Leader"

    # 2. WOODEN SPOON CLOWN (Last Place)
    elif is_last:
        badge = "🤡 CLOWN OF THE GAMEWEEK"
        if "Marvin" in name:
            title = f"{name} - 'Don Bosco' In Urgent Need Of Prayers"
            body = f"The undisputed Clown of the Gameweek! Marvin's 'Don Bosco' crashed and burned with {pts} points. Emergency pilgrimage to Don Bosco church advised."
            verdict = "Verdict: Undisputed Wooden Spoon Clown"
        elif "Aron" in name:
            title = f"{name} - 'Arons' Hit Rock Bottom"
            body = f"Aron put up an unforgettable disasterclass of {pts} points to anchor the clown car at rank #{rank}. Time to delete the team and take up gardening."
            verdict = "Verdict: Certified Wooden Spoon Clown"
        elif "King Chris" in name:
            title = f"{name} - The Painter Drops The Brush"
            body = f"King Chris suffered a complete canvas catastrophe with {pts} points at rank #{rank}. From royal aspirations straight to clown town."
            verdict = "Verdict: Dethroned Clown"
        elif "Erick" in name:
            title = f"{name} - 'mambaaa' Bites Own Tail"
            body = f"Erick's 'mambaaa' turned on itself with a pitiful {pts} points to claim last place. The group chat is going to show zero mercy."
            verdict = "Verdict: Harmless Worm"
        elif "Bright" in name:
            title = f"{name} - 'Phill Me In' Completely Emptied"
            body = f"Bright's team got utterly demolished with {pts} points to anchor the bottom. Relegation panic has officially set in."
            verdict = "Verdict: Sunk In The Depths"
        elif "Benn" in name:
            title = f"{name} - 'Benn's Team' Forgets How To Play"
            body = f"Benn managed a league-worst {pts} points to take home the wooden spoon. Group chat apologies are expected immediately."
            verdict = "Verdict: Tactical Meltdown"
        else:
            title = f"{name} - The League Punchline"
            body = f"An unforgettable disasterclass of {pts} points to claim the wooden spoon at rank #{rank}. Footballing crime committed."
            verdict = "Verdict: Needs Divine Intervention"

    # 3. PODIUM (Ranks 2 & 3)
    elif rank <= 3:
        badge = "🥈 2ND PLACE (SILVER)" if rank == 2 else "🥉 3RD PLACE (BRONZE)"
        if "Samuel" in name:
            title = f"{name} - 'maggry shiners' Bag The Podium Cash"
            body = f"Samuel's '{team}' shone under the lights with {pts} points, clinching {badge.split()[0]} place and Ksh. {prize_won:,.2f}."
            verdict = "Verdict: Silver Shiner & Title Contender"
        elif "Renny" in name:
            title = f"{name} - The Young Ones Schooling The Elders"
            body = f"Renny's 'The Young Ones' showed mature nerve with {pts} points to pocket Ksh. {prize_won:,.2f} on the podium."
            verdict = "Verdict: Clutch Podium Scrapper"
        elif "Torque" in name or "Dennis" in name:
            title = f"{name} - DenniSkills Paying Dividends"
            body = f"Dennis delivered high skill and cold hard cash, scoring {pts} points to take home Ksh. {prize_won:,.2f} on the podium."
            verdict = "Verdict: Master Tactician"
        elif "Marve" in name:
            title = f"{name} - 'Marve of the Match' In The Money"
            body = f"Marve stayed right in the prize zone with {pts} points, taking home Ksh. {prize_won:,.2f} on the podium."
            verdict = "Verdict: Consistent Heavyweight"
        else:
            title = f"{name} - Money In The Bank"
            body = f"{name}'s '{team}' secured {badge.split()[0]} place with {pts} points and Ksh. {prize_won:,.2f}."
            verdict = "Verdict: Podium Secured"

    # 4. RANK 4 HEARTBREAK
    elif rank == 4:
        badge = "💔 4TH PLACE (HEARTBREAK)"
        if "Torque" in name or "Dennis" in name:
            title = f"{name} - 'DenniSkills' In The Heartbreak Hotel"
            body = f"Dennis brought pure skill with {pts} points, but '{team}' missed out on the podium money by a razor-thin margin. High skill, zero shillings."
            verdict = "Verdict: High Skill, Zero Shillings"
        else:
            title = f"{name} - Agonizingly Close To The Money"
            body = f"{name}'s '{team}' scored {pts} points to finish rank #4, missing the podium cash by just a few points. Pure agony."
            verdict = "Verdict: Heartbreak Purgatory"

    # 5. MID-TABLE (Ranks 5-7)
    elif rank <= 7:
        badge = f"😴 RANK #{rank} (MID-TABLE)"
        if "King Chris" in name:
            title = f"{name} - The Painter Strokes A Neutral Canvas"
            body = f"King Chris entered with royal ambitions, but '{team}' painted a very beige mid-table portrait with {pts} points."
            verdict = "Verdict: 50/50 Mid-Table Masterpiece"
        elif "Erick" in name:
            title = f"{name} - 'mambaaa' Strikes Without Venom"
            body = f"Erick's '{team}' didn't deliver the fatal bite promised, slithering into rank #{rank} with {pts} points."
            verdict = "Verdict: Harmless Grass Snake"
        elif "Benn" in name:
            title = f"{name} - Minimalist Name, Minimalist Points"
            body = f"With a team name as creatively minimal as '{team}', his {pts}-point tally was equally subdued at rank #{rank}."
            verdict = "Verdict: Needs Tactical Ignition"
        else:
            title = f"{name} - Floating In Mid-Table"
            body = f"{name}'s '{team}' registered {pts} points to settle into rank #{rank}."
            verdict = "Verdict: Sleeping Giant"

    # 6. RELEGATION TRENCH (Ranks 8-9)
    else:
        badge = f"💀 RANK #{rank} (RELEGATION TRENCH)"
        if "Bright" in name:
            title = f"{name} - 'Phill Me In' Got Filled With Regret"
            body = f"Bright was anything but cheerful as '{team}' got thoroughly dismantled for {pts} points at rank #{rank}."
            verdict = "Verdict: Sinking in the Trench"
        elif "Aron" in name:
            title = f"{name} - Saved From The Clown Hat By A Whisker"
            body = f"Aron's {pts}-point return left him lingering dangerously at rank #{rank}, barely escaping the wooden spoon."
            verdict = "Verdict: One Foot In The Abyss"
        else:
            title = f"{name} - Dangerously Close To The Bottom"
            body = f"{name}'s '{team}' finished with {pts} points at rank #{rank}. Urgent tactical surgery required."
            verdict = "Verdict: Code Red Alert"

    return badge, title, body, verdict


def generate_roast_edition(gameweek: Gameweek, force_update=True) -> RoastEdition:
    """
    Analyzes Gameweek results and payments to generate a savage, hilarious newspaper edition.
    Includes GW1/GW2 fine waiver notices, celebrates winners with swagger, and savages the clowns.
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

    active_participants = [r for r in results if getattr(r.member, 'joined_gameweek', 1) <= gameweek.number]
    if active_participants:
        winner_res = active_participants[0]
        last_res = active_participants[-1]
    else:
        winner_res = results[0]
        last_res = results[-1]
    clown_res = last_res
    king_res = winner_res

    # Check for largest hit taker
    hit_takers = [r for r in results if r.transfer_cost > 0]
    hit_takers.sort(key=lambda r: r.transfer_cost, reverse=True)
    biggest_hit_taker = hit_takers[0] if hit_takers else None

    gw_num = gameweek.number
    winner_name = winner_res.member.manager_name.upper()
    last_name = last_res.member.manager_name.upper()

    headline = f"GW {gw_num} CROWN: {winner_name} CLAIMS SUPREME GLORY AS {last_name} ANCHORS THE CLOWN CAR!"
    subheadline = f"Official Issue #{gw_num}: Masterclass at the summit, carnage at the bottom, and an unfiltered autopsy of the weekend."

    # Editorial lead
    editorial_lead = (
        f"Welcome to Issue #{gw_num} of The FPL Boys Gazette! "
        f"Gameweek {gw_num} kicked off with high drama and tactical showdowns across all 10 managers. "
        f"Leading from the front, {winner_res.member.manager_name} ({winner_res.member.team_name}) put on a championship display, amassing a league-high {winner_res.net_points} points to secure top honors and pocket Ksh. {winner_res.gw_prize_won:,.2f} in prize money. "
        f"However, for every champion standing proudly on the podium, there is a casualty in the trenches. "
        f"At the very bottom of the table, {last_res.member.manager_name} ({last_res.member.team_name}) suffered a complete tactical meltdown with only {last_res.net_points} points, officially earning the unwanted wooden spoon. "
        f"Read through the full breakdown below for the complete manager-by-manager autopsy!"
    )

    king_reason = (
        f"{winner_res.member.manager_name} dominated the round with {winner_res.net_points} net points, bagging Ksh. {winner_res.gw_prize_won:,.2f}. "
        f"An imperious showing that sets the early benchmark for the rest of the league to chase!"
    )

    clown_reason = (
        f"{last_res.member.manager_name} collapsed to rank #{last_res.league_rank} with just {last_res.net_points} points. "
        f"A textbook disasterclass that will be studied in tactical defense academies as what NOT to do."
    )

    # Defaulter roast / waiver rules
    if gw_num in [1, 2]:
        defaulter_roast = (
            f"🚨 LEAGUE GRACE PERIOD (GW {gw_num}): The League Committee has officially declared a full grace period for GW 1 & GW 2! "
            f"Zero late penalty fines apply for all managers. Defaulters get a clean slate for the opening fortnight—strict Ksh. 50 fines will be enforced by the Treasurer starting GW 3!"
        )
    else:
        # Check actual late payments
        late_members = [r.member for r in results if payments.get(r.member_id) and payments.get(r.member_id).is_late]
        unpaid_members = [r.member for r in results if not payments.get(r.member_id)]
        if late_members or unpaid_members:
            names = ', '.join([f"{m.manager_name} ({'LATE' if m in late_members else 'UNPAID'})" for m in (late_members + unpaid_members)])
            defaulter_roast = (
                f"Special gratitude to our voluntary BBQ Pot sponsors: {names}. "
                f"Your contributions to the fine fund are deeply appreciated by the meat committee!"
            )
        else:
            defaulter_roast = "All 10 managers paid on time! The Treasurer extends sincere congratulations to the entire league."

    # Hit roast
    if gw_num == 1:
        transfer_hit_roast = (
            "Season Kickoff Window: All 10 managers launched with unlimited free squad selections prior to the GW 1 deadline. "
            "Point-deducting transfer hits unlock from GW 2 onward, where panic transfers and tactical chaos will officially commence!"
        )
    elif biggest_hit_taker:
        transfer_hit_roast = (
            f"Transfer Market Alert: {biggest_hit_taker.member.manager_name} took a -{biggest_hit_taker.transfer_cost} point hit in transfers, "
            f"finishing with {biggest_hit_taker.net_points} net points. A costly gamble that did not quite deliver the expected dividends."
        )
    else:
        transfer_hit_roast = "Zero transfer hits taken this week. Clean discipline across the entire mini-league!"

    quote_of_the_week = f"\"My rank is only temporary. By Gameweek 38, they will see the vision.\" — {last_res.member.manager_name}"
    quote_author = f"{last_res.member.manager_name} (Post-Match Presser)"

    weather = random.choice(WEATHER_REPORTS)

    with transaction.atomic():
        edition, created = RoastEdition.objects.update_or_create(
            gameweek=gameweek,
            defaults={
                'edition_number': gw_num,
                'headline': headline,
                'subheadline': subheadline,
                'publish_date': timezone.now(),
                'chief_editor': 'The League Scribe & Chief Correspondent',
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
                'classified_ads': [],
                'is_published': True,
            }
        )

        # Remove old manager roasts if updating
        edition.manager_roasts.all().delete()

        # Create individual manager roasts
        third_pts = results[2].net_points if len(results) >= 3 else 0
        for r in results:
            rank = r.league_rank
            pts = r.net_points
            hits = r.transfer_cost
            manager = r.member
            is_last = (r == last_res)

            badge, title, body, verdict = build_personalized_manager_review(
                manager=manager,
                rank=rank,
                pts=pts,
                hits=hits,
                prize_won=r.gw_prize_won,
                gw_num=gw_num,
                is_last=is_last,
                winner_res=winner_res,
                third_pts=third_pts
            )

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

