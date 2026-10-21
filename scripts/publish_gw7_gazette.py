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


def publish_gw7():
    ensure_news_tables_exist()
    gw = Gameweek.objects.get(number=7)

    # 1. Update GameweekResult prize allocations:
    # 1st: Samuel Wambua (77 net pts) = Ksh. 250.00
    # 2nd (Rolled down past Dennis): Bright Ottore (71 net pts) = Ksh. 167.00
    # 3rd (Rolled down past Dennis, Erick, Chris): Benn Mwangi (66 net pts) = Ksh. 83.00
    # Flagged / Ineligible: Dennis, Erick, Chris, Marve
    payout_map = {
        'Samuel': Decimal('250.00'),
        'Bright': Decimal('167.00'),
        'Benn': Decimal('83.00'),
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

    # 2. Build Broadsheet Content (The Great Treasury Roll-Down Heist)
    headline = "GW 7 ROLL-DOWN HEIST: SAMUEL'S TRIPLE CAPTAIN CRUSHES WITH 77 PTS, DENNIS & CHRIS BURN CASH AS DEFAULTERS, & BENN CASHES FROM 6TH PLACE!"
    subheadline = "Issue #7 Treasury Meltdown: 4 managers flagged ineligible as Dennis burns a 39-pt Triple Captain, Chris auto-subs into 71 pts but stays broke, Erick misses podium cash, and Benn pulls off the luckiest roll-down in FPL history."
    
    chief_editor = "The League Scribe & Chief Banter Executioner"
    weather_report = "Raining free money on Benn Mwangi's porch, hurricane winds tearing through the Defaulter Ward, and boiling hot meat in the Nyama Choma pot."

    editorial_lead = (
        "Welcome to the most chaotic, legally scandalous, and financially punitive gameweek in FPL Boys history! "
        "Gameweek 7 will forever be remembered as the Great Treasury Roll-Down Heist. "
        "At the pinnacle, Samuel Wambua ('maggry shiners fc') unleashed his TRIPLE CAPTAIN chip on Erling Haaland against Ipswich Town for 39 explosive points, backed up by Charalampos Kostoulas's 12-point masterclass in Brighton's 5-0 destruction of Palace, storming to 77 net points to bank Ksh. 250.00—his FOURTH consecutive week collecting prize money! "
        "But the real drama unfolded in the Defaulter Ward: Torque Dennis also played his Triple Captain chip on Haaland, scoring 75 points to finish 2nd, ONLY TO DISCOVER HE IS FLAGGED AS INELIGIBLE, watching his Ksh. 167 evaporate into the Nyama Choma fund! "
        "It didn't stop there: Erick Muchira and King Chris both scored 71 points (tied for 3rd), but BOTH ARE INELIGIBLE! "
        "With Dennis, Erick, and Chris all disqualified, the prize money cascade fell right into the lap of Bright Ottore (Ksh. 167) and rolled all the way down to BENN MWANGI in 6th place (66 points), who benched a 9-point Calvert-Lewin and STILL pocketed Ksh. 83! "
        "Meanwhile, Marve Mathingu captained Morgan Rogers for 4 points while vice-captaining Haaland, took a -4 hit, benched 6-point Verbruggen, finished dead last on 44 points, and was flagged ineligible to complete the comedy. "
        "Settle your dues, gentlemen—the bank always wins!"
    )

    samuel = Member.objects.filter(manager_name__icontains="Samuel").first()
    marve = Member.objects.filter(manager_name__icontains="Marve").first()

    king = samuel
    king_reason = (
        "Samuel 'maggry shiners' Wambua timed his TRIPLE CAPTAIN chip to perfection! 39 points from Erling Haaland plus a 12-point differential in Kostoulas powered him to 77 net points, outright GW 7 victory, and Ksh. 250.00 cash—marking an incredible FOUR straight weeks of collecting league prize money!"
    )

    clown = marve
    clown_reason = (
        "A textbook disasterclass in FPL self-sabotage: Marve took his 3rd consecutive -4 hit, captained Morgan Rogers for 4 points (2 x 2) while benching Haaland's armband (13 pts), benched clean-sheet goalkeeper Bart Verbruggen (6 pts), finished DEAD LAST on 44 net points, and was FLAGGED AS INELIGIBLE on the defaulters ledger! The undisputed Crown Clown of GW 7!"
    )

    quote_of_the_week = "\"I played my Triple Captain on Haaland, scored 75 points, finished 2nd in the league, and made exactly zero shillings because of an unpaid fine. The meat at the end of the season better be grass-fed.\" — Torque Dennis"
    quote_author = "Torque Dennis (DenniSkills & Generous BBQ Meat Pot Sponsor)"

    defaulter_roast = (
        "🚨 TREASURY WALL OF SHAME (GW 7 — 4-MAN SPECIAL): The penalty box has become a full hostel! "
        "Four managers were officially FLAGGED AS INELIGIBLE this week: Torque Dennis, Erick Muchira, King Chris, and Marve Mathingu. "
        "Dennis threw away Ksh. 167 by playing his Triple Captain while in default. "
        "King Chris achieved the historic 5-PEAT OF SHAME (5 consecutive weeks unpaid) and watched his 71-point revival produce zero cash. "
        "Erick lost out on podium dividends on 71 points. And Marve capped off a last-place 44-point stinker with an unpaid fine. "
        "Together, these four philanthropists have guaranteed the league's end-of-season banquet will feature premium goat ribs. Settle up or keep subsidizing Benn's retirement fund!"
    )

    transfer_hit_roast = (
        "💥 THE CHIP WARS & BENCH BLUNDERS: Gameweek 7 saw the heavy artillery deployed! "
        "Two managers activated their TRIPLE CAPTAIN chips: Samuel Wambua (77 pts, Ksh. 250) and Torque Dennis (75 pts, 0 cash due to default). Both reaped 39 points from Erling Haaland's Ipswich brace. "
        "Meanwhile, King Chris accidentally galaxy-brained his captaincy: he captained Rayan Cherki (who played 0 minutes for City), meaning his vice-captain Haaland auto-subbed in for 26 points! "
        "On the benches, Benn Mwangi committed his weekly tradition by benching 9-point Dominic Calvert-Lewin (9 bench pts total), yet won cash anyway due to defaulters above him! "
        "Marve Mathingu burned another -4 hit and benched 6-point Verbruggen."
    )

    classifieds = [
        {
            'title': "AUCTION: Dennis's Triple Captain Shillings",
            'desc': "One slightly used Triple Captain chip on Haaland (39 pts). Generated 75 total points and Ksh. 167 in potential cash, all donated directly to the Treasurer. Non-refundable.",
            'contact': "M-Pesa Fine Collection Box"
        },
        {
            'title': "CHARITY APPEAL: The King Chris 5-Week Nyama Choma Foundation",
            'desc': "Celebrate 5 straight weeks of King Chris defaulting on his league dues. All donations go directly toward prime cuts of meat for the eligible top 3.",
            'contact': "Visit www.chrisbuysthegoat.co.ke"
        },
        {
            'title': "LOST & FOUND: Benn Mwangi's Shame",
            'desc': "Lost somewhere between 6th place, a benched 9-point Calvert-Lewin, and an unearned Ksh. 83 roll-down cash payout. If found, please do not return—Benn doesn't care.",
            'contact': "Drop off at Odysseus Bank Account"
        },
        {
            'title': "WORKSHOP: How to Pick a Captain by Marve Mathingu",
            'desc': "Learn the art of ignoring a 13-point Erling Haaland on your pitch to captain Morgan Rogers for 4 points while taking a -4 transfer hit. Free admission.",
            'contact': "Call 0800-WHY-ROGERS"
        }
    ]

    edition, created = RoastEdition.objects.update_or_create(
        gameweek=gw,
        defaults={
            'edition_number': 7,
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
        # Rank 1: Samuel Wambua
        {
            'name_match': 'Samuel',
            'rank': 1,
            'net_pts': 77,
            'badge': '👑 1ST PLACE (TRIPLE CAPTAIN MASTERCLASS)',
            'title': "Samuel Wambua - 'maggry shiners' TC Haaland for 39 Pts & Banks 4th Straight Cash Prize!",
            'body': "An absolute titan of the league! While others squander their chips or forget to pay their dues, Samuel executed a textbook TRIPLE CAPTAIN masterclass on Erling Haaland against Ipswich Town for an astonishing 39 points. If that wasn't enough, he unleashed Charalampos Kostoulas (12 pts with 1G, 1A, and 3 bonus in Brighton's 5-0 destruction of Palace) to cruise to 77 net points. Samuel takes 1st place and Ksh. 250.00 cash—his FOURTH consecutive week on the podium, taking his total winnings to Ksh. 791.66 in a single month!",
            'verdict': "Verdict: Undisputed League Heavyweight & Tactical Maestro (Ksh. 250.00)",
        },
        # Rank 2: Torque Dennis
        {
            'name_match': 'Dennis',
            'rank': 2,
            'net_pts': 75,
            'badge': '💸 2ND PLACE (TRIPLE CAPTAIN TRAGEDY & DEFAULTER)',
            'title': "Torque Dennis - 'DenniSkills' Plays 39-pt Triple Captain Only to Watch Ksh. 167 Evaporate!",
            'body': "The most painful screenshot in the history of fantasy football! Dennis timed his TRIPLE CAPTAIN on Haaland to perfection for 39 points, backed by Bryan Mbeumo (8p), Verbruggen (6p), and De Cuyper (6p) to amass 75 net points and 2nd place overall. But when the prize money was distributed, Dennis was slapped with a big red 'INELIGIBLE'! Because of an unpaid fine, his Ksh. 167.00 prize vanished into the ether, rolling down to Bright and Benn. He burned his most lethal chip and got paid in pure embarrassment. Dennis, your M-Pesa is crying!",
            'verdict': "Verdict: 75 Points on the Pitch, 0 Shillings in the Pocket, Pure Defaulter Agony",
        },
        # Rank 3 (Tied on pts, 2nd Eligible): Bright Ottore
        {
            'name_match': 'Bright',
            'rank': 3,
            'net_pts': 71,
            'badge': '🥈 2ND ELIGIBLE (THE BENEFICIARY OF DENNIS\'S SINS)',
            'title': "Bright Ottore - 'Phill Me In' Finishes Tied 3rd But Rolls Into Ksh. 167 Silver Cash!",
            'body': "The golden touch continues for Bright! Coming off his 86-point GW 6 triumph (Ksh. 250), Bright trusted Haaland (26p cap), Mbeumo (8p), Verbruggen (6p), De Cuyper (6p), and Calafiori (6p) to post 71 points. On raw points, he was tied for 3rd with Erick and Chris. But because Dennis above him was disqualified for defaulting, Bright was bumped up into the 2nd place payout, banking another Ksh. 167.00! That is Ksh. 417.00 collected across two weeks. Paying your dues pays dividends!",
            'verdict': "Verdict: Righteous Cash Collector & 2nd Place Beneficiary (Ksh. 167.00)",
        },
        # Rank 4 (Tied 3rd on pts, Ineligible): Erick Muchira
        {
            'name_match': 'Erick',
            'rank': 3,
            'net_pts': 71,
            'badge': '🚨 TIED 3RD (71 PTS STRANDED IN THE DEFAULTERS WARD)',
            'title': "Erick Muchira - 'mambaaa' Hits 71 Pts Only to Be Locked Out of the Treasury!",
            'body': "Cruel, unusual, and completely self-inflicted punishment! After struggling for weeks, Erick finally had his team firing: Haaland cap (26p), Dominic Calvert-Lewin (9p), Mbeumo (8p), De Cuyper (6p), and Calafiori (6p) delivered an outstanding 71 net points, tying with Bright Ottore. Under normal circumstances, Erick would be splitting silver and bronze cash. Instead, Erick saw the dreaded red 'INELIGIBLE' stamp next to his name! All that hard work and brilliant scouting, only to donate his winnings to Benn Mwangi. Settle the ledger, Erick!",
            'verdict': "Verdict: Brilliant Score, Frozen Wallet, Charity Donor to Odysseus Reign",
        },
        # Rank 5 (Tied 3rd on pts, Ineligible): King Chris
        {
            'name_match': 'Chris',
            'rank': 3,
            'net_pts': 71,
            'badge': '🤡 TIED 3RD (CHERKI AUTO-SUB BLUNDER & 5-PEAT DEFAULTER)',
            'title': "King Chris - The Painter Accidentally Scores 71 Pts via Auto-Sub but Remains 5-Peat Defaulter!",
            'body': "You cannot write a script this absurd! After scoring 20 in GW 5 and 48 in GW 6, Chris tried to captain Rayan Cherki... but Cherki played 0 minutes for Man City! The armband auto-subbed to vice-captain Erling Haaland for 26 points! Add in Charalampos Kostoulas (12 pts) and David Raya (9 pts), and Chris miraculously stumbled into 71 net points—tied for 3rd place! But did Chris win money? ABSOLUTELY NOT! Chris is FLAGGED FOR THE 5TH CONSECUTIVE WEEK! Five straight weeks of dodging the treasurer means Chris has officially achieved legendary status as the Permanent Patron of Nyama Choma!",
            'verdict': "Verdict: Accidental 71-Point Miracle Denied by 5 Consecutive Weeks of Debt",
        },
        # Rank 6 (3rd Eligible): Benn Mwangi
        {
            'name_match': 'Benn',
            'rank': 6,
            'net_pts': 66,
            'badge': '💰 3RD ELIGIBLE (THE GREATEST ROLL-DOWN HEIST IN HISTORY)',
            'title': "Benn Mwangi - 'Odysseus Reign' Benches Calvert-Lewin (9p), Finishes 6th, and STILL GETS PAID!",
            'body': "Ladies and gentlemen, behold the jammiest manager in Kenya! Benn scored a very modest 66 points, benched 9-point Dominic Calvert-Lewin (his 3rd consecutive week benching a big return!), and finished down in SIXTH PLACE. By all laws of physics and fantasy, Benn should have gone home empty-handed. But Dennis in 2nd was ineligible. Erick in 3rd was ineligible. Chris in 3rd was ineligible. The prize money rolled all the way down the stairs and into Benn's pocket for Ksh. 83.00! Benn benched his top striker, finished 6th, and got paid. You have to laugh!",
            'verdict': "Verdict: The Luckiest Roll-Down Cash Grab in FPL History (Ksh. 83.00)",
        },
        # Rank 7: Marvin Owino
        {
            'name_match': 'Marvin',
            'rank': 7,
            'net_pts': 63,
            'badge': '📉 7TH PLACE (CLEAN BENCH, DRY CASH REGISTER)',
            'title': "Marvin Owino - 'Don Bosco' Scouts Tavernier (10p) But Slumps to 7th Place",
            'body': "A rare bump in the road for the church of Don Bosco. Marvin made an astute transfer for Marcus Tavernier (10 pts in Bournemouth's 2-0 win over Sunderland) and kept his bench impeccably clean with 0 points wasted. But with João Pedro (2p), King (2p), and Gvardiol (0p) failing to provide backup to Haaland (26p cap), Marvin managed only 63 points and slipped 5 places to 7th. After pocketing Ksh. 375 across the last two weeks, the Don Bosco cash register was finally silenced for a week.",
            'verdict': "Verdict: Tactical Purity Without the Fireworks, Cash Streak Halted",
        },
        # Rank 8 (Tied): Aron Mangati
        {
            'name_match': 'Aron',
            'rank': 8,
            'net_pts': 59,
            'badge': '🧊 TIED 8TH PLACE (STALLED ENGINE)',
            'title': "Aron Mangati - 'Arons' Starts Calvert-Lewin (9p) But Sinks to 59 Pts",
            'body': "After the heartbreak of GW 6 where he benched 15-point De Cuyper and missed cash by 1 point, Aron made sure to start Dominic Calvert-Lewin (9 pts against Leeds). Unfortunately, the rest of his squad decided to take the week off: Gianluigi Donnarumma got 1 point, James Tarkowski got 0 points, and Saka managed just 3 points. With 59 net points, Aron shares 8th place and stays well away from the money.",
            'verdict': "Verdict: Out of the Bench Nightmare, Straight into Midfield Stagnation",
        },
        # Rank 8 (Tied): Renny Muragu
        {
            'name_match': 'Renny',
            'rank': 8,
            'net_pts': 59,
            'badge': '🛡️ TIED 8TH PLACE (TRIPLE DEFENDER ZERO-POINT DUCK)',
            'title': "Renny Muragu - 'The Young Ones' Battered by Triple 0-Point Defensive Blanks",
            'body': "A defensive horror show for Renny! While captain Haaland (26p), Calvert-Lewin (9p), Calafiori (6p), and De Cuyper (6p) did their jobs, Renny had THREE starting defenders score absolute ZEROS: Josko Gvardiol (0p), James Tarkowski (0p), and Leif Davis (0p)! That goose egg trio dragged his total down to 59 net points, leaving him tied with Aron in 8th place. When three defenders combine for zero points, you're lucky not to end up with the wooden spoon.",
            'verdict': "Verdict: The Triple Zero Duck Sinks The Young Ones to 8th",
        },
        # Rank 10: Marve Mathingu
        {
            'name_match': 'Marve',
            'rank': 10,
            'net_pts': 44,
            'badge': '🤡 10TH PLACE (-4 HIT, ROGERS CAPTAIN BLUNDER, & FLAGGED)',
            'title': "Marve Mathingu - 'Marve of the Match' Captains Rogers Over Haaland, Benches Verbruggen, Takes -4, and Lands on the Fine Ledger!",
            'body': "THE SUPREME DISASTERCLASS OF GAMEWEEK 7! Marve put together a masterclass in FPL comedy: he burned his 3rd consecutive -4 transfer hit, gave the captain's armband to MORGAN ROGERS for 4 points (2 x 2) while Erling Haaland scored 13 points on his pitch, left clean-sheet goalkeeper Bart Verbruggen (6 pts) on his bench (9 bench pts total), and watched Mitchell (0p) and Schade (0p) ghost. That dragged his score down to a league-worst 44 net points. And to put the golden clown crown on his head: MARVE WAS FLAGGED AS INELIGIBLE ON THE DEFAULTERS LIST! Dead last, captain disaster, bench crime, and unpaid fines. Marve of the Match is the undisputed King of the Circus!",
            'verdict': "Verdict: Crown Clown of GW 7, Tactical Catastrophe & Defaulters Ward Resident",
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
    print(f"[SUCCESS] Gazette Issue #{edition.edition_number} for GW {gw.number} published and exported to news/editions/gw7.json successfully!")


if __name__ == '__main__':
    publish_gw7()
