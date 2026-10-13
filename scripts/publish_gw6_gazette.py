import os
import sys
import django
from decimal import Decimal
from django.utils import timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fpl_boys.settings')
django.setup()

from league.models import Gameweek, Member, GameweekResult
from news.models import RoastEdition, ManagerRoastItem
from news.services.roast_engine import ensure_news_tables_exist
from news.services.gazette_storage import export_edition_to_disk


def publish_gw6():
    ensure_news_tables_exist()
    gw = Gameweek.objects.get(number=6)

    # 1. Update GameweekResult prize allocations:
    # 1st: Bright Ottore (86 net pts) = Ksh. 250.00
    # 2nd: Marvin Owino (81 net pts) = Ksh. 166.67
    # 3rd: Samuel Wambua (72 net pts) = Ksh. 83.33
    # Flagged/Unpaid: Dennis and Chris -> Disqualified
    payout_map = {
        'Bright': Decimal('250.00'),
        'Marvin': Decimal('166.67'),
        'Samuel': Decimal('83.33'),
    }

    for res in GameweekResult.objects.filter(gameweek=gw).select_related('member'):
        m_name = res.member.manager_name
        prize = Decimal('0.00')
        is_top3 = False
        for k, p in payout_map.items():
            if k in m_name:
                prize = p
                is_top3 = True
                break
        res.gw_prize_won = prize
        res.is_top3 = is_top3
        res.save(update_fields=['gw_prize_won', 'is_top3'])

    # 2. Build Broadsheet Content (Post-International Break Theme + Savage Roasts)
    headline = "POST-BREAK CARNAGE: BRIGHT CONQUERS WITH 86 PTS, ARON'S 20-PT BENCH HORROR MISSES CASH BY 1, & KING CHRIS WILDCARDS STRAIGHT INTO THE SAME 48-PT GRAVE!"
    subheadline = "Issue #6 Post-Break Autopsy: Bright Ottore ends bench hoarding to claim Ksh. 250, Marvin & Samuel extend cash streaks, Benn trades bench sins for a 2-pt Bruno captaincy, and Chris & Dennis fund the meat pot."
    
    chief_editor = "The League Scribe & Chief Banter Executioner"
    weather_report = "Sunny skies for Don Bosco & Phill Me In FC, torrential tears in Arons dugout, and sub-zero financial frost on the Defaulters Ledger."

    editorial_lead = (
        "Two long weeks of tinkering, endless international break overthinking, and where did it lead? Straight into pure FPL comedy! "
        "Welcome to Gameweek 6, where Bright Ottore ('Phill Me In FC') finally stopped benching his superstars and unleashed Maxim De Cuyper (15 pts) and João Pedro (12 pts) to destroy the league with an 86-point masterclass and bag Ksh. 250.00! "
        "Close on his heels, Marvin Owino ('Don Bosco') put on another clinic of tactical purity with 81 points (leaving only 2 points on his bench) to claim 2nd place cash (Ksh. 166.67), while Samuel Wambua ('maggry shiners fc') secured his third consecutive podium finish with 72 points (Ksh. 83.33) despite benching a 10-point Rayan Cherki. "
        "But the heartbreak of the week belongs to Aron Mangati, who benched De Cuyper's 15 points (20 total on the pine!) to miss podium cash by a single point. "
        "And then there's our resident circus: Benn Mwangi, who started his players for once but captained Bruno Fernandes for 2 points, and King Chris, who burnt his precious WILDCARD chip after the 20-point horror show only to captain Morgan Gibbs-White for 4 points AGAIN and finish dead last on 48 points! "
        "Add in our flagged defaulters Dennis and Chris, and the boys are officially back in session!"
    )

    bright = Member.objects.filter(manager_name__icontains="Bright").first()
    chris = Member.objects.filter(manager_name__icontains="Chris").first()

    king = bright
    king_reason = (
        "Bright Ottore broke free from his chronic bench-hoarding curse! Zero hits, zero transfers over the break, and pure faith in De Cuyper (15 pts), João Pedro (12 pts), and captain Haaland (12 pts) led him to an unstoppable 86-point explosion and outright GW 6 glory (Ksh. 250.00)!"
    )

    clown = chris
    clown_reason = (
        "The greatest comedic timing in fantasy football history. After his historic 20-point catastrophe in GW 5, Chris used the 2-week international break to activate his WILDCARD... only to captain Morgan Gibbs-White for 4 points AGAIN, start Yalcouyé (1p) and Kostoulas (1p), finish dead last tied on 48 points, and remain FLAGGED on the defaulters ledger for the 4th consecutive week! Undisputed Clown of the Fortnight!"
    )

    quote_of_the_week = "\"I tore down my whole team with a Wildcard, rebuilt from scratch, and still captained Gibbs-White for 4 points. Some curses cannot be cured by chips.\" — King Chris"
    quote_author = "King Chris (The_Painter.. & 4-Peat Defaulter)"

    defaulter_roast = (
        "🚨 TREASURY WALL OF SHAME (GW 6): The Nyama Choma fund is looking healthier than the Kenyan economy! "
        "King Chris has cemented his legacy as the Four-Peat Patron of Defaulting, skipping payments for the 4th straight gameweek while finishing in the basement. "
        "Meanwhile, Torque Dennis marks his second straight week on the blacklist! Dennis scored an impressive 67 points, but thanks to his unpaid fine, he couldn't touch a single shilling of potential prize money even if he wanted to. "
        "Settle your debts, gentlemen—the treasurer is keeping receipts!"
    )

    transfer_hit_roast = (
        "💥 BENCH BLUNDERS & MARKET MADNESS: Gameweek 6 produced a historic mountain of benched points! "
        "Aron Mangati committed footballing treason by leaving Maxim De Cuyper's 15-point haul on the pine (20 bench pts total) to miss 3rd place cash by just 1 point! "
        "Samuel Wambua benched 10-point Rayan Cherki. Marve Mathingu burned another -4 hit, benched 9-point Verbruggen (13 bench pts total), and started Adrien Truffert for MINUS ONE point! "
        "Benn Mwangi finally started Groß, but handed the captain's armband to Bruno Fernandes for a staggering 2 points. "
        "And King Chris burned his Wildcard chip just to tie for last place!"
    )

    classifieds = [
        {
            'title': 'LOST & FOUND: Aron’s Missing Podium Shillings',
            'desc': 'Found sitting on the Brighton bench: Maxim De Cuyper’s 15 points. Could have earned Aron Ksh. 166.67. Currently gathering dust in 4th place.',
            'contact': 'Drop off at Arons Dugout'
        },
        {
            'title': 'HOTLINE: Wildcard Re-Wildcarding Service',
            'desc': 'Did you use your Wildcard only to captain Morgan Gibbs-White for 4 points and score 48 points? Certified therapists available 24/7.',
            'contact': 'Call 0800-PAINT-OVER-IT'
        },
        {
            'title': 'AUCTION: Bruno Fernandes Captaincy Armband',
            'desc': 'Barely used captaincy armband worn by Benn Mwangi for 90 minutes of pure cardio and 1 FPL point. Will swap for a pair of functioning eyes.',
            'contact': 'Odysseus Pawn Shop'
        },
        {
            'title': 'TREASURY NOTICE: Chris & Dennis Meat Platter',
            'desc': 'With Chris (4 weeks overdue) and Dennis (2 weeks overdue) maintaining their M-Pesa strike, the league goat is officially fully funded.',
            'contact': 'Treasury M-Pesa Desk'
        }
    ]

    edition, created = RoastEdition.objects.update_or_create(
        gameweek=gw,
        defaults={
            'edition_number': 6,
            'headline': headline,
            'subheadline': subheadline,
            'publish_date': timezone.now(),
            'chief_editor': chief_editor,
            'weather_report': weather_report,
            'editorial_lead': editorial_lead,
            'clown_of_the_week': clown,
            'clown_reason': clown_reason,
            'king_of_the_week': king,
            'king_reason': king_reason,
            'quote_of_the_week': quote_of_the_week,
            'quote_author': quote_author,
            'defaulter_roast': defaulter_roast,
            'transfer_hit_roast': transfer_hit_roast,
            'classified_ads': classifieds,
            'is_published': True,
        }
    )

    edition.manager_roasts.all().delete()

    roasts_data = [
        # Rank 1: Bright Ottore
        {
            'name_match': 'Bright',
            'rank': 1,
            'net_pts': 86,
            'badge': '👑 1ST PLACE (BENCH CURSE BROKEN & GW CHAMPION)',
            'title': "Bright Ottore - 'Phill Me In' Shuts the Bench Door & Banks Ksh. 250 Cash!",
            'body': "After weeks of hoarding double-digit hauls on his pine and finishing just outside the cash, Bright finally let his thoroughbreds run free! He didn't make a single transfer over the international break, trusting his core—and boy did they reward him. Maxim De Cuyper (15 pts with a goal and clean sheet), João Pedro (12 pts with a Chelsea brace), captain Haaland (12 pts), Bart Verbruggen (9 pts), and Riccardo Calafiori (9 pts) produced an electrifying 86 net points. Bright cleans up the league and takes home the 1st place jackpot of Ksh. 250.00!",
            'verdict': "Verdict: Outright Champion & Master of the Matchday (Ksh. 250.00)",
        },
        # Rank 2: Marvin Owino
        {
            'name_match': 'Marvin',
            'rank': 2,
            'net_pts': 81,
            'badge': '🥈 2ND PLACE (DON BOSCO CASH MACHINE)',
            'title': "Marvin Owino - 'Don Bosco' Efficiency Rolls On: 81 Pts & Ksh. 166 Cash!",
            'body': "The church of Don Bosco continues to dispense financial miracles! Fresh off splitting 1st place in GW 5 (Ksh. 208.34), Marvin returned from the break with another masterclass: 81 net points with just 2 points left on his bench. De Cuyper (15 pts), Haaland (12 pts cap), João Pedro (12 pts), Cherki (10 pts), and Calafiori (9 pts) fired on all cylinders. Even with Bruno Fernandes blanking for 1 point, Marvin comfortably locks down 2nd place and Ksh. 166.67. Marvin has now banked Ksh. 375 in two weeks!",
            'verdict': "Verdict: Ruthless Efficiency & Silver Podium Collector (Ksh. 166.67)",
        },
        # Rank 3: Samuel Wambua
        {
            'name_match': 'Samuel',
            'rank': 3,
            'net_pts': 72,
            'badge': '🥉 3RD PLACE (TRIPLE PODIUM RUNNER)',
            'title': "Samuel Wambua - 'maggry shiners' Claims 3rd Straight Podium Despite 10-pt Cherki Bench!",
            'body': "Samuel's podium residency continues! 1st in GW 4, tied 1st in GW 5, and now 3rd in GW 6 (Ksh. 83.33)—the man simply refuses to leave the money! De Cuyper (15 pts), João Pedro (12 pts), and captain Haaland (12 pts) led the charge. But Samuel nearly outsmarted himself: he BENCHED Rayan Cherki (10 pts) while starting Kevin Schade (1p), Bruno Fernandes (1p), and Kostoulas (1p)! Had Cherki played, Samuel would have had 82 points and taken 2nd place cash. Still, 3 consecutive cash payouts is a terrifying run.",
            'verdict': "Verdict: Serial Cash Hoarder Survived a Benched Cherki (Ksh. 83.33)",
        },
        # Rank 4: Aron Mangati
        {
            'name_match': 'Aron',
            'rank': 4,
            'net_pts': 71,
            'badge': '🤦 4TH PLACE (20 BENCH PTS & 1-PT TRAGEDY)',
            'title': "Aron Mangati - 'Arons' Benches 15-pt De Cuyper & Misses Podium Cash by ONE Point!",
            'body': "A tragedy of Shakespearean proportions! Aron sat in the driver's seat with Haaland (12 pts cap), João Pedro (12 pts), Cherki (10 pts), Donnarumma (9 pts), and Calafiori (9 pts). But looking at his subs bench will haunt him forever: he BENCHED MAXIM DE CUYPER (15 PTS) in favor of Calvert-Lewin (2p), Saka (2p), and Ajayi (1p)! Aron stranded a staggering 20 points on his bench and finished on 71 points—exactly ONE POINT behind Samuel's 72! Had Aron started De Cuyper, he would have had 84 points, finishing 2nd outright for Ksh. 166.67. Instead: zero shillings, 4th place, and endless agony.",
            'verdict': "Verdict: The Most Expensive 1-Point Bench Heartbreak in FPL History",
        },
        # Rank 5: Torque Dennis
        {
            'name_match': 'Dennis',
            'rank': 5,
            'net_pts': 67,
            'badge': '💸 5TH PLACE (SOLID SCORE, FROZEN WALLET)',
            'title': "Torque Dennis - 'DenniSkills' Bounces Back to 67 Pts But Stays Frozen in Debt!",
            'body': "Dennis recovered well on the pitch after his 45-point slump in GW 5, racking up 67 net points thanks to De Cuyper (15 pts), João Pedro (12 pts), and captain Haaland (12 pts). However, starting Dominik Szoboszlai (0 pts) and Lewis Hall (0 pts) gave the league plenty to chuckle at. More importantly, Dennis is still FLAGGED for unpaid fines for the 2nd week running! His wallet remains under sanctions, meaning even if he had topped the charts, his prize would have evaporated. Clear the balance, Dennis!",
            'verdict': "Verdict: Good Points, Zero Cash, Sanctioned on the Defaulter Ward",
        },
        # Rank 6: Renny Muragu
        {
            'name_match': 'Renny',
            'rank': 6,
            'net_pts': 66,
            'badge': '🎯 6TH PLACE (GROSS CAPTAINCY GAMBIT)',
            'title': "Renny Muragu - 'The Young Ones' Gambles on Groß Captain & Lands Mid-Table",
            'body': "After his miraculous Wildcard cash grab in GW 5 (55 pts, Ksh. 83.33), Renny tried to outsmart the galaxy by handing the captain's armband to Pascal Groß instead of Haaland! Groß delivered 6 points (12 as captain), exactly matching Haaland's 6 points, but the gamble didn't create the separation Renny needed. With João Pedro (12p), Cherki (10p), and Calafiori (9p) all firing, Renny's 66 points was respectable but couldn't keep him on the podium. A solid week, but the magic well ran dry.",
            'verdict': "Verdict: Safe Mid-Table Landing After Last Week's Lucky Heist",
        },
        # Rank 7: Erick Muchira
        {
            'name_match': 'Erick',
            'rank': 7,
            'net_pts': 57,
            'badge': '⚡ 7TH PLACE (16-PT MBEUMO CAPTAINCY ISOLATION)',
            'title': "Erick Muchira - 'mambaaa' Pulls Off 16-pt Mbeumo Masterstroke but Squad Collapses",
            'body': "Tactical brilliance meets total squad failure! Erick made the boldest captaincy call in the league, giving the armband to Bryan Mbeumo for 16 points (8 x 2) in Brentford's 2-2 draw with Aston Villa. Coupled with João Pedro (12 pts) and Calafiori (9 pts), Erick looked primed for glory. But the rest of his post-Wildcard team completely ghosted: Enzo Le Fée (2p), Kevin Schade (1p), Odegaard (1p), and a 4-man bench of duds left him marooned down in 7th on 57 points. When your captain scores 16 and your team gets 57, you need a full inquiry.",
            'verdict': "Verdict: Genius Captaincy Stranded on an Island of Incompetence",
        },
        # Rank 8: Benn Mwangi
        {
            'name_match': 'Benn',
            'rank': 8,
            'net_pts': 56,
            'badge': '🤡 8TH PLACE (FROM BENCH FELON TO 2-PT BRUNO CAPTAIN)',
            'title': "Benn Mwangi - 'Odysseus Reign' Solves Bench Curse Only to Captain 2-pt Bruno Fernandes!",
            'body': "You truly cannot make this up. After benching Leif Davis (14 pts) in GW 4 and benching Pascal Groß (14 pts) in GW 5, Benn finally put Groß on the pitch. Did he enjoy a peaceful gameweek? Absolutely not! Benn decided that Erling Haaland wasn't worthy of the armband and CAPTAINED BRUNO FERNANDES! Bruno proceeded to put on a 1-point cardio masterclass (2 pts as captain) in Man Utd's 1-1 draw with Spurs. Benn left vice-captain Haaland (6p), João Pedro (12p), and Verbruggen (9p) shaking their heads as he sank to 8th place on 56 points. Benn has traded bench misery for captaincy clowns!",
            'verdict': "Verdict: The Curse Simply Changed Uniforms",
        },
        # Rank 9: Marve Mathingu
        {
            'name_match': 'Marve',
            'rank': 9,
            'net_pts': 48,
            'badge': '💀 9TH PLACE (-4 HIT, -1 TRUFFERT, & 13 BENCH PTS)',
            'title': "Marve Mathingu - 'Marve of the Match' Burns -4 Hit, Benches Verbruggen & Starts -1 Truffert!",
            'body': "A chaotic cocktail of FPL self-harm! Marve took his second consecutive -4 transfer hit, gave the captain's armband to Bukayo Saka for 4 points (2 x 2 against Leeds), and watched Adrien Truffert score a majestic MINUS ONE POINT (-1)! To add insult to injury, Marve left 9-point Bart Verbruggen chilling on his bench alongside 13 total bench points. Dragged down to 48 net points, Marve only escaped the clown hat because King Chris exists in an alternate dimension of failure.",
            'verdict': "Verdict: Triple Whammy of Hits, Negative Points, and Pine Hoarding",
        },
        # Rank 10: King Chris
        {
            'name_match': 'Chris',
            'rank': 10,
            'net_pts': 48,
            'badge': '🤡 10TH PLACE (WILDCARD DISASTER & 4-PEAT DEFAULTER)',
            'title': "King Chris - The Wildcard Fiasco: Same Captain, Same 4 Points, 4-Peat Defaulter!",
            'body': "LADIES AND GENTLEMEN, STAND FOR THE CLOWN OF THE CENTURY! After his historic 20-point horror show in GW 5, King Chris spent two whole weeks of the international break staring into the void before finally activating his WILDCARD chip. With the entire Premier League player database at his disposal, what did Chris do? HE CAPTAINED MORGAN GIBBS-WHITE AGAIN! In GW 5, Gibbs-White gave him 4 points. In GW 6, Forest lost 1-3 to Crystal Palace, and Gibbs-White gave him... 4 POINTS! Chris rounded out his 'revamped' squad by starting Yalcouyé (1p), Kostoulas (1p), and Lewis Hall (0p), finishing dead last tied on 48 points. And for the grand finale: Chris is FLAGGED on the defaulters ledger for the 4TH CONSECUTIVE WEEK! Wildcard burned, rank buried, fines unpaid. Pure poetry.",
            'verdict': "Verdict: Crown Clown of the Season, Wildcard Squandered & Permanent BBQ Sponsor",
        },
    ]

    for idx, rdata in enumerate(roasts_data):
        member = Member.objects.filter(manager_name__icontains=rdata['name_match']).first()
        if not member:
            continue

        ManagerRoastItem.objects.create(
            edition=edition,
            member=member,
            rank_in_gw=rdata['rank'],
            net_points=rdata['net_pts'],
            badge=rdata['badge'],
            roast_title=rdata['title'],
            roast_body=rdata['body'],
            verdict=rdata['verdict'],
            order=idx + 1
        )

    export_edition_to_disk(edition)
    print(f"[SUCCESS] Gazette Issue #{edition.edition_number} for GW {gw.number} published and exported to news/editions/gw6.json successfully!")


if __name__ == '__main__':
    publish_gw6()
