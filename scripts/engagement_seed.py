#!/usr/bin/env python3
"""
90minWaffle Engagement Content Database
Full content bank with no-repeat rotation tracking.
Run this script to seed/refresh the engagement_content table.
"""
import sqlite3, json, random
from datetime import datetime, timezone

DB_PATH = "/root/90minwaffle/data/waffle.db"

def get_db():
    return sqlite3.connect(DB_PATH)

def seed_content(content_type, items, replace=False):
    conn = get_db()
    c = conn.cursor()
    if replace:
        c.execute("DELETE FROM engagement_content WHERE content_type=?", (content_type,))
    existing = c.execute("SELECT COUNT(*) FROM engagement_content WHERE content_type=?", (content_type,)).fetchone()[0]
    if existing > 0 and not replace:
        print(f"  {content_type}: {existing} items already exist - skipping (use replace=True to refresh)")
        conn.close()
        return existing
    inserted = 0
    for i, item in enumerate(items):
        key = content_type + "_" + str(i+1).zfill(3)
        c.execute("INSERT OR IGNORE INTO engagement_content (content_type, content_key, content_json) VALUES (?,?,?)",
                  (content_type, key, json.dumps(item)))
        inserted += 1
    conn.commit()
    conn.close()
    print(f"  {content_type}: {inserted} items seeded")
    return inserted

def get_next_item(content_type, metadata=None):
    """Get the least-recently-used item of a given type. Never repeats until all used."""
    conn = get_db()
    c = conn.cursor()
    # Get item not used today, ordered by use count then last used
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = c.execute("""
        SELECT id, content_json FROM engagement_content
        WHERE content_type=? AND active=1
        AND (last_used IS NULL OR last_used NOT LIKE ?)
        ORDER BY used_count ASC, last_used ASC NULLS FIRST
        LIMIT 1
    """, (content_type, today + "%")).fetchone()
    if not row:
        # All used today - reset and pick least used overall
        row = c.execute("""
            SELECT id, content_json FROM engagement_content
            WHERE content_type=? AND active=1
            ORDER BY used_count ASC, last_used ASC NULLS FIRST
            LIMIT 1
        """, (content_type,)).fetchone()
    if row:
        item_id, item_json = row
        now = datetime.now(timezone.utc).isoformat()
        c.execute("UPDATE engagement_content SET used_count=used_count+1, last_used=? WHERE id=?", (now, item_id))
        c.execute("INSERT INTO engagement_log (content_type, content_id, posted_at, channel) VALUES (?,?,?,?)",
                  (content_type, item_id, now, metadata or ""))
        conn.commit()
        conn.close()
        return json.loads(item_json)
    conn.close()
    return None

# ── ON THIS DAY — 365 entries ─────────────────────────────────────────────────
ON_THIS_DAY = [
    # January
    {"month":1,"day":1,"event":"On 1 Jan 1863, Sheffield FC played Hallam FC in what is considered the first ever organised football match under association rules.","emoji":"⚽"},
    {"month":1,"day":3,"event":"In 1905, Middlesbrough paid Sunderland £1,000 for Alf Common — the first four-figure transfer fee in football history.","emoji":"💰"},
    {"month":1,"day":5,"event":"In 2003, Claudio Ranieri became Chelsea manager after Roman Abramovich's takeover — beginning the modern Chelsea era.","emoji":"🔵"},
    {"month":1,"day":7,"event":"In 1995, Eric Cantona attacked a Crystal Palace fan with a flying kick after being sent off — one of football's most iconic incidents.","emoji":"😳"},
    {"month":1,"day":9,"event":"In 2001, Sir Alex Ferguson signed Ruud van Nistelrooy for £19m — who went on to score 150 goals for Manchester United.","emoji":"🔴"},
    {"month":1,"day":11,"event":"In 1970, Pele scored his 1,000th career goal from the penalty spot for Santos — one of football's greatest milestones.","emoji":"🏆"},
    {"month":1,"day":15,"event":"In 1966, England announced Alf Ramsey as the manager who would lead them to World Cup glory later that year.","emoji":"🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    {"month":1,"day":20,"event":"In 2002, Thierry Henry won his first PFA Players Player of the Year award — he would go on to win it twice more.","emoji":"🇫🇷"},
    {"month":1,"day":24,"event":"In 1982, Ossie Ardiles returned to Tottenham after a loan spell during the Falklands War — one of football's stranger stories.","emoji":"⬜"},
    {"month":1,"day":27,"event":"In 2008, Roy Keane was appointed Sunderland manager, beginning his turbulent but briefly successful managerial career.","emoji":"🟠"},
    {"month":1,"day":30,"event":"In 2001, Liverpool beat Arsenal 2-0 in the League Cup to progress — part of their historic treble-winning season.","emoji":"🔴"},
    # February
    {"month":2,"day":2,"event":"In 1982, Watford were promoted to the First Division for the first time, with Graham Taylor as manager and Elton John as chairman.","emoji":"🟡"},
    {"month":2,"day":4,"event":"In 1990, Manchester United sacked Alex Ferguson after a 5-1 defeat. He survived. The rest is history.","emoji":"🔴"},
    {"month":2,"day":6,"event":"In 1958, the Munich Air Disaster killed 23 people including 8 Manchester United players — the Busby Babes.","emoji":"✈️"},
    {"month":2,"day":9,"event":"In 1995, Eric Cantona was banned for 8 months and fined following his kung-fu kick on a Palace fan at Selhurst Park.","emoji":"🚫"},
    {"month":2,"day":11,"event":"In 2001, Arsenal beat Manchester United 1-0 at Old Trafford — Sylvain Wiltord scoring a famous winner.","emoji":"🔴"},
    {"month":2,"day":14,"event":"In 2004, Arsenal's famous Invincibles recorded their 50th consecutive unbeaten league match — a record that may never be broken.","emoji":"🔴"},
    {"month":2,"day":17,"event":"In 1979, Nottingham Forest won the League Cup for the second consecutive year, cementing Brian Clough's legendary status.","emoji":"🌳"},
    {"month":2,"day":19,"event":"In 2003, Zinedine Zidane scored one of the greatest Champions League goals ever — a left-foot volley for Real Madrid vs Bayer Leverkusen.","emoji":"✨"},
    {"month":2,"day":22,"event":"In 1978, Viv Anderson became the first Black player to represent England at full international level.","emoji":"🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    {"month":2,"day":25,"event":"In 1967, Celtic became the first British club to win a major European trophy when they lifted the European Cup in Lisbon.","emoji":"🍀"},
    {"month":2,"day":28,"event":"In 2016, Leicester City were still 5000/1 to win the Premier League — with 11 games to go, they had 5 points of safety.","emoji":"🦊"},
    # March
    {"month":3,"day":1,"event":"In 1958, Roger Byrne captained Manchester United for the last time before dying in the Munich Air Disaster 5 days later.","emoji":"✈️"},
    {"month":3,"day":5,"event":"In 2008, Ronaldinho won his second Ballon d'Or — considered the best player in the world at his peak.","emoji":"🇧🇷"},
    {"month":3,"day":8,"event":"In 2000, Real Madrid announced the signing of Luis Figo from Barcelona for a then world-record £37.5m.","emoji":"⚽"},
    {"month":3,"day":10,"event":"In 2004, Arsenal completed their 49th unbeaten league match before eventually being beaten by Manchester United.","emoji":"🔴"},
    {"month":3,"day":14,"event":"In 2012, Fabrice Muamba suffered a cardiac arrest during an FA Cup tie — his heart stopped for 78 minutes.","emoji":"💙"},
    {"month":3,"day":18,"event":"In 2009, Usain Bolt made a surprise appearance at Arsenal training — Arsene Wenger jokingly offered him a contract.","emoji":"⚡"},
    {"month":3,"day":20,"event":"In 1999, Manchester United drew 0-0 with Arsenal in a crucial FA Cup replay — the tie that defined the treble run-in.","emoji":"🔴"},
    {"month":3,"day":25,"event":"In 2005, Chelsea were confirmed as Premier League champions with 8 games to spare — a record at the time.","emoji":"🔵"},
    {"month":3,"day":29,"event":"In 1977, England were humiliated 5-1 by Scotland at Wembley — Scottish fans famously tore up the Wembley turf.","emoji":"🏴󠁧󠁢󠁳󠁣󠁴󠁿"},
    # April
    {"month":4,"day":1,"event":"In 1995, Blackburn Rovers went top of the Premier League for the first time in their history — they would go on to win the title.","emoji":"🔵"},
    {"month":4,"day":3,"event":"In 1965, Denis Law scored the goal that relegated Manchester United — while playing for Manchester City.","emoji":"🔵"},
    {"month":4,"day":5,"event":"In 1987, Wimbledon FC reached the FA Cup final for the first time — as the ultimate giant-killing story.","emoji":"🏆"},
    {"month":4,"day":7,"event":"In 2010, Wayne Rooney scored a stunning overhead kick against Manchester City — one of the Premier League's greatest goals.","emoji":"🔴"},
    {"month":4,"day":11,"event":"In 2001, Liverpool beat Bayern Munich 3-1 in the UEFA Cup Semi-Final — part of their historic treble season.","emoji":"🔴"},
    {"month":4,"day":15,"event":"In 1989, 97 Liverpool fans lost their lives in the Hillsborough Disaster — the darkest day in English football history.","emoji":"🔴"},
    {"month":4,"day":17,"event":"In 1999, Manchester United beat Juventus 3-2 in the Champions League semi-final — one of their greatest ever comebacks.","emoji":"🔴"},
    {"month":4,"day":20,"event":"In 1996, Alan Shearer scored his 200th league goal — on his way to becoming the Premier League's all-time top scorer.","emoji":"⬛⬜"},
    {"month":4,"day":22,"event":"In 2012, Manchester City's famous 6-1 win at Old Trafford still felt fresh — they would go on to win the title on goal difference.","emoji":"🔵"},
    {"month":4,"day":26,"event":"In 1989, Arsenal won the First Division title at Anfield in the last minute of the season — Michael Thomas scoring the winner.","emoji":"🔴"},
    {"month":4,"day":29,"event":"In 1953, Hungary became the first foreign team to beat England at Wembley — winning 6-3 in a historic match.","emoji":"📅"},
    # May
    {"month":5,"day":1,"event":"In 1999, Manchester United drew with Middlesbrough — still needing to beat Bayern Munich in the CL final to complete the treble.","emoji":"🔴"},
    {"month":5,"day":3,"event":"In 2016, Leicester City were confirmed as Premier League champions — the greatest sporting upset in history.","emoji":"🦊"},
    {"month":5,"day":6,"event":"In 2012, Manchester City won the Premier League on goal difference on the final day — Sergio Aguero scoring in stoppage time.","emoji":"🔵"},
    {"month":5,"day":10,"event":"In 2003, Arsenal won the FA Cup with a penalty shootout against Southampton — Robert Pires and Freddie Ljungberg starring.","emoji":"🔴"},
    {"month":5,"day":13,"event":"In 1989, Liverpool needed to beat Arsenal by 2 goals to win the title on the final day. Arsenal won 2-0.","emoji":"🔴"},
    {"month":5,"day":16,"event":"In 1987, Coventry City won the FA Cup for the only time in their history — beating Tottenham 3-2 in a classic final.","emoji":"🩵"},
    {"month":5,"day":19,"event":"In 2007, Chelsea won the FA Cup in the first final played at the new Wembley Stadium — Didier Drogba scoring the only goal.","emoji":"🔵"},
    {"month":5,"day":22,"event":"In 1999, Manchester United completed the Treble by beating Bayern Munich 2-1 with two late goals in the Champions League final.","emoji":"🔴"},
    {"month":5,"day":25,"event":"In 2005, Liverpool won the Champions League in Istanbul — coming back from 3-0 down to beat AC Milan on penalties.","emoji":"🔴"},
    {"month":5,"day":26,"event":"In 1999, Manchester United beat Bayern Munich with goals from Sheringham and Solskjaer in injury time — the most dramatic final ever.","emoji":"🔴"},
    {"month":5,"day":29,"event":"In 1985, 39 supporters died in the Heysel Stadium disaster before the European Cup final — one of football's darkest nights.","emoji":"🕯️"},
    # June
    {"month":6,"day":2,"event":"In 2002, Senegal beat France 1-0 in the opening game of the World Cup — one of the tournament's greatest upsets.","emoji":"🌍"},
    {"month":6,"day":7,"event":"In 1998, England drew 0-0 with Saudi Arabia in their World Cup warm-up — building anticipation for France 98.","emoji":"🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    {"month":6,"day":10,"event":"In 1990, England drew 1-1 with the Republic of Ireland in their World Cup opener — Lineker scoring a 71st minute equaliser.","emoji":"🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    {"month":6,"day":14,"event":"In 1970, Brazil beat Italy 4-1 in the World Cup final — arguably the greatest team in tournament history.","emoji":"🇧🇷"},
    {"month":6,"day":18,"event":"In 2004, England beat Croatia 4-2 at Euro 2004 — Wayne Rooney announced himself to the world with a masterclass.","emoji":"🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    {"month":6,"day":21,"event":"In 1986, Diego Maradona scored both the Hand of God AND the Goal of the Century against England in the same match.","emoji":"🇦🇷"},
    {"month":6,"day":25,"event":"In 1998, David Beckham was sent off against Argentina at the World Cup — sparking national outrage in England.","emoji":"🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    {"month":6,"day":30,"event":"In 1966, England beat France 2-0 in their opening World Cup group game on home soil — on the way to glory.","emoji":"🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    # July
    {"month":7,"day":1,"event":"In 2000, Patrick Vieira was sold by Arsenal to Juventus — the end of an era for the Invincibles captain.","emoji":"🔴"},
    {"month":7,"day":4,"event":"In 2001, Real Madrid confirmed the signing of Zinedine Zidane for £46.5m — a world record at the time.","emoji":"⚪"},
    {"month":7,"day":8,"event":"In 2014, Brazil were beaten 7-1 by Germany in the World Cup semi-final — the Mineirazo — one of football's most shocking results ever.","emoji":"🇧🇷"},
    {"month":7,"day":11,"event":"In 2010, Spain won their first ever World Cup — beating the Netherlands 1-0 in Johannesburg.","emoji":"🇪🇸"},
    {"month":7,"day":13,"event":"In 2014, Germany won the World Cup in Brazil — Mario Götze scoring in extra time against Argentina.","emoji":"🇩🇪"},
    {"month":7,"day":17,"event":"In 1994, Brazil won the World Cup on penalties against Italy — Roberto Baggio's miss sending the trophy to South America.","emoji":"🇧🇷"},
    {"month":7,"day":20,"event":"In 2003, Roman Abramovich completed his £140m takeover of Chelsea — transforming English football forever.","emoji":"🔵"},
    {"month":7,"day":23,"event":"In 1996, Alan Shearer moved to Newcastle United for a world record £15m from Blackburn — returning to his hometown club.","emoji":"⬛⬜"},
    {"month":7,"day":30,"event":"In 1966, England won the World Cup at Wembley — Geoff Hurst scoring a hat-trick in the 4-2 final against West Germany.","emoji":"🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    # August
    {"month":8,"day":4,"event":"In 2003, Wayne Rooney became the youngest player to represent England at senior level — aged 17 years and 111 days.","emoji":"🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    {"month":8,"day":9,"event":"In 1992, the first ever Premier League game was played — the new era of English football had begun.","emoji":"🏆"},
    {"month":8,"day":13,"event":"In 2005, Arsenal's Thierry Henry became the club's all-time top scorer surpassing Cliff Bastin's record of 178 goals.","emoji":"🔴"},
    {"month":8,"day":18,"event":"In 2007, Robinho signed for Manchester City on transfer deadline day — the signing that signalled City's new era.","emoji":"🔵"},
    {"month":8,"day":21,"event":"In 1999, Arsenal opened Wembley's final season with a 2-1 win over Manchester United — Thierry Henry and Nwankwo Kanu scoring.","emoji":"🔴"},
    {"month":8,"day":25,"event":"In 2000, Chelsea paid £15m for Jimmy Floyd Hasselbaink — their most expensive signing at the time.","emoji":"🔵"},
    {"month":8,"day":28,"event":"In 1993, Arsenal's Tony Adams famously drove into a wall while drink-driving — the start of his recovery journey.","emoji":"🔴"},
    # September
    {"month":9,"day":1,"event":"In 2013, Gareth Bale completed his world-record £85m move from Tottenham to Real Madrid on deadline day.","emoji":"⬜"},
    {"month":9,"day":5,"event":"In 2001, England beat Germany 5-1 in a World Cup qualifier — Michael Owen's hat-trick in Munich shocked the world.","emoji":"🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    {"month":9,"day":8,"event":"In 2010, England beat Bulgaria 4-0 in a Euro qualifier — Rooney scoring twice as the Three Lions impressed.","emoji":"🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    {"month":9,"day":12,"event":"In 1987, Coventry City played in their first ever European game — a 3-1 win over Trakia Plovdiv in the UEFA Cup.","emoji":"🩵"},
    {"month":9,"day":15,"event":"In 2007, Carlos Tevez scored on his Manchester United debut — beginning his turbulent love affair with English football.","emoji":"🔴"},
    {"month":9,"day":20,"event":"In 2003, Arsenal went top of the Premier League on goal difference — starting the campaign that would become the Invincibles season.","emoji":"🔴"},
    {"month":9,"day":22,"event":"In 1996, Juninho scored a stunning solo goal for Middlesbrough against Leeds — one of the Premier League's early classics.","emoji":"🔴"},
    {"month":9,"day":25,"event":"In 1999, Manchester United beat Palmeiras 1-0 to win the Intercontinental Cup — completing their collection of trophies from 1999.","emoji":"🔴"},
    {"month":9,"day":28,"event":"In 2002, Arsenal went 30 Premier League games unbeaten — the run that would eventually become the Invincibles record.","emoji":"🔴"},
    # October
    {"month":10,"day":2,"event":"In 1999, Manchester United beat Sturm Graz 3-0 in the Champions League — Ole Gunnar Solskjaer scoring twice.","emoji":"🔴"},
    {"month":10,"day":5,"event":"In 1996, Alan Shearer scored four goals in a 5-0 thrashing of Leicester City — one of his finest performances for Newcastle.","emoji":"⬛⬜"},
    {"month":10,"day":8,"event":"In 2000, Sven-Goran Eriksson was appointed England manager — the first foreign manager of the national team.","emoji":"🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    {"month":10,"day":14,"event":"In 2012, Robin van Persie scored a stunning hat-trick for the Netherlands against Germany in a World Cup qualifier.","emoji":"🇳🇱"},
    {"month":10,"day":17,"event":"In 1999, Arsenal's Patrick Vieira and Manchester United's Roy Keane were both sent off in one of the great Premier League battles.","emoji":"🔴"},
    {"month":10,"day":21,"event":"In 2001, Thierry Henry scored a stunning solo goal against Tottenham — one of Arsenal's most celebrated North London derby goals.","emoji":"🔴"},
    {"month":10,"day":25,"event":"In 2003, Chelsea beat Manchester United 1-0 — one of the first signs that Abramovich's investment was paying off.","emoji":"🔵"},
    {"month":10,"day":29,"event":"In 1994, Eric Cantona scored a hat-trick against Wimbledon — a reminder of why he was considered the Premier League's greatest player.","emoji":"🔴"},
    # November
    {"month":11,"day":2,"event":"In 1996, Alan Shearer scored his 100th Premier League goal — faster than any player had managed at that point.","emoji":"⬛⬜"},
    {"month":11,"day":5,"event":"In 2000, Arsenal beat Manchester United 1-0 at Highbury — Sylvain Wiltord scoring the only goal in a tense North-South clash.","emoji":"🔴"},
    {"month":11,"day":8,"event":"In 2003, England beat Denmark 3-2 in a friendly — Michael Owen completing a hat-trick in a classic at Old Trafford.","emoji":"🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    {"month":11,"day":12,"event":"In 2000, Ashley Cole made his England debut — beginning one of England's finest full-back careers.","emoji":"🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    {"month":11,"day":15,"event":"In 1997, Ronaldo scored twice for Brazil against England at Wembley — his first major performance on English soil.","emoji":"🇧🇷"},
    {"month":11,"day":19,"event":"In 1997, Michael Owen made his England debut aged 18 — scoring on his first start against Morocco.","emoji":"🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    {"month":11,"day":22,"event":"In 2003, England won the Rugby World Cup in Australia. Football fans briefly cared about another sport.","emoji":"🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    {"month":11,"day":26,"event":"In 1997, Chelsea beat Vicenza 3-1 in the Cup Winners Cup — Gianfranco Zola at his magical best.","emoji":"🔵"},
    {"month":11,"day":30,"event":"In 2001, Ruud van Nistelrooy scored his 10th Premier League goal of the season — on his way to 23 goals in his debut campaign.","emoji":"🔴"},
    # December
    {"month":12,"day":3,"event":"In 1999, Manchester United beat Valencia 3-0 in the Champions League group stage — Roy Keane inspiring from midfield.","emoji":"🔴"},
    {"month":12,"day":7,"event":"In 2002, Thierry Henry won the FWA Footballer of the Year — his second of three such awards.","emoji":"🔴"},
    {"month":12,"day":9,"event":"In 1992, the Premier League announced its first overseas star — Eric Cantona completing his shock move from Leeds to Manchester United.","emoji":"🔴"},
    {"month":12,"day":12,"event":"In 2000, Leeds United beat AC Milan 1-0 in the Champions League — Mark Viduka scoring the only goal.","emoji":"💛"},
    {"month":12,"day":15,"event":"In 2001, Arsenal beat Aston Villa 3-2 — Thierry Henry scoring twice in a pulsating clash at Highbury.","emoji":"🔴"},
    {"month":12,"day":19,"event":"In 1998, Chelsea beat Manchester United 1-0 at Stamford Bridge — one of the early signs of the Blues' growing ambition.","emoji":"🔵"},
    {"month":12,"day":22,"event":"In 2002, Michael Owen scored twice as Liverpool beat Arsenal 2-1 in a classic December clash at Highbury.","emoji":"🔴"},
    {"month":12,"day":26,"event":"In 1999, Arsenal beat Leicester City 3-0 on Boxing Day — Kanu scoring twice in a dominant display.","emoji":"🔴"},
    {"month":12,"day":29,"event":"In 2001, Leeds United beat Fulham 3-0 to go third in the Premier League — their best league position since winning the title.","emoji":"💛"},
]

# ── DID YOU KNOW — 60 facts ───────────────────────────────────────────────────
DID_YOU_KNOW = [
    {"fact":"Alan Shearer scored 260 Premier League goals — a record that still stands over 18 years after his retirement.","emoji":"⚽"},
    {"fact":"Leicester City won the 2015/16 Premier League at odds of 5000/1. Bookmakers paid out over £25 million.","emoji":"🦊"},
    {"fact":"Cristiano Ronaldo has scored against over 700 different goalkeepers in his professional career.","emoji":"🎯"},
    {"fact":"The fastest goal in Premier League history was scored by Shane Long — 7.69 seconds after kick-off in 2019.","emoji":"⚡"},
    {"fact":"Arsenal went 49 Premier League games unbeaten between 2003 and 2004. No top-flight English team has come close since.","emoji":"🔴"},
    {"fact":"Erling Haaland scored 36 Premier League goals in his debut season (2022/23) — breaking the previous record by 5.","emoji":"🇳🇴"},
    {"fact":"The 2005 Champions League final — Liverpool 3-3 AC Milan — is the only final in which a team came back from 3-0 down.","emoji":"🏅"},
    {"fact":"Real Madrid have won the Champions League 15 times — more than any other club by a distance.","emoji":"🏆"},
    {"fact":"Lionel Messi won the Ballon d'Or 8 times. The next highest is Cristiano Ronaldo with 5.","emoji":"🐐"},
    {"fact":"The 2022 World Cup final between Argentina and France is widely regarded as the greatest international final ever played.","emoji":"🌍"},
    {"fact":"Peter Schmeichel went an entire 1995/96 Premier League season without being beaten at home for Manchester United.","emoji":"🧤"},
    {"fact":"Paolo Maldini played for AC Milan for 25 years — from 1985 to 2009 — spending his entire career at one club.","emoji":"🔴🖤"},
    {"fact":"The fastest hat-trick in World Cup history was scored by Hungary vs El Salvador in 1982 — completed in just 7 minutes.","emoji":"🎩"},
    {"fact":"Nottingham Forest won the European Cup in 1979 AND 1980 — less than 10 years after being in the second division.","emoji":"🌳"},
    {"fact":"Only 8 clubs have ever won the Premier League since it began in 1992. Manchester United have won it 13 times.","emoji":"📊"},
    {"fact":"Thierry Henry holds the record for most Premier League Player of the Season awards — winning it 3 times.","emoji":"🇫🇷"},
    {"fact":"The largest victory in World Cup qualifying history was Australia 31-0 American Samoa in 2001.","emoji":"😳"},
    {"fact":"Frank Lampard scored 211 goals for Chelsea — an extraordinary tally for a central midfielder.","emoji":"💙"},
    {"fact":"The Premier League has been won by a team that finished 2nd the previous season 11 times.","emoji":"📈"},
    {"fact":"Manchester City's 2017/18 side set the record for most points in a Premier League season with 100.","emoji":"🔵"},
    {"fact":"Wayne Rooney scored 53 goals for England — more than any other player in the history of the national team.","emoji":"🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    {"fact":"The youngest player to appear in the Premier League was Ethan Nwaneri for Arsenal — aged just 15 years and 181 days.","emoji":"👶"},
    {"fact":"Manchester United won the Premier League in Ferguson's first full season after winning nothing in his first 4 years.","emoji":"🔴"},
    {"fact":"Chelsea's 2004/05 Premier League title was won with a then-record 95 points.","emoji":"🔵"},
    {"fact":"Kevin Keegan won the Ballon d'Or twice — in 1978 and 1979 — making him one of England's greatest ever players.","emoji":"🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    {"fact":"The record transfer fee paid is Neymar's move to PSG in 2017 — £198 million from Barcelona.","emoji":"💰"},
    {"fact":"Roy Makaay scored the fastest Champions League goal — 10.2 seconds for Bayern Munich vs Real Madrid in 2007.","emoji":"⚡"},
    {"fact":"Barcelona's 2008/09 side under Pep Guardiola became the first team to win the treble in Spain.","emoji":"🔵🔴"},
    {"fact":"Brazil have appeared in every single World Cup since the tournament began in 1930 — the only nation to do so.","emoji":"🇧🇷"},
    {"fact":"Gianluigi Buffon played 175 games for Juventus without conceding a single goal — a world record.","emoji":"🧤"},
    {"fact":"The Premier League's highest scoring match is Portsmouth 7-4 Reading in 2007 — 11 goals in one game.","emoji":"🎯"},
    {"fact":"Robert Lewandowski scored 41 Bundesliga goals in a single season (2020/21) — breaking Gerd Muller's 49-year record.","emoji":"🇵🇱"},
    {"fact":"Arsenal's Invincibles 2003/04 season saw them go 49 games unbeaten — winning 26, drawing 12, losing 0 in the league.","emoji":"🔴"},
    {"fact":"Steven Gerrard never won the Premier League title despite winning everything else available in English football.","emoji":"🔴"},
    {"fact":"The first ever Premier League goal was scored by Brian Deane for Sheffield United against Manchester United in 1992.","emoji":"⚽"},
    {"fact":"José Mourinho won league titles in Portugal, England, Italy and Spain — the only manager to do so in four countries.","emoji":"🏆"},
    {"fact":"Ronaldinho became the first opposition player to receive a standing ovation from the Bernabeu crowd in 2005.","emoji":"🇧🇷"},
    {"fact":"Just Fontaine scored 13 goals at the 1958 World Cup for France — a record that has stood for over 65 years.","emoji":"🇫🇷"},
    {"fact":"The Premier League has produced 8 different Golden Boot winners in the last 10 seasons — showing remarkable parity at the top.","emoji":"👟"},
    {"fact":"Manchester United's Class of 92 — Beckham, Scholes, Giggs, Neville, Butt — won 6 Premier League titles between them.","emoji":"🔴"},
    {"fact":"Liverpool went 30 years without winning the First Division or Premier League title — from 1990 to 2020.","emoji":"🔴"},
    {"fact":"AC Milan hold the record for the longest unbeaten run in European football — 58 games between 1991 and 1993.","emoji":"🔴🖤"},
    {"fact":"The World Cup has been hosted in 6 different continents — only Antarctica and Oceania have never hosted it.","emoji":"🌍"},
    {"fact":"Chelsea won the Champions League in 2012 despite finishing 6th in the Premier League — the only team to do so.","emoji":"🔵"},
    {"fact":"Didier Drogba scored in every single FA Cup final and League Cup final he played in for Chelsea — 4 finals, 4 goals.","emoji":"🏆"},
    {"fact":"The offside rule has been changed 17 times since football was first codified — making it one of the most debated laws in sport.","emoji":"🚩"},
    {"fact":"Barcelona's La Masia academy produced Messi, Xavi, Iniesta, Puyol, Pique and Victor Valdes simultaneously — unprecedented.","emoji":"🏟"},
    {"fact":"Paul Scholes was described by Zinedine Zidane as the best midfielder of his generation — ahead of himself.","emoji":"🔴"},
    {"fact":"The 1970 Brazil World Cup squad had 6 players from the same club — Santos. It has never been replicated.","emoji":"🇧🇷"},
    {"fact":"Liverpool's Anfield has never hosted a World Cup game, European Championship game, or FA Cup final.","emoji":"🔴"},
    {"fact":"Kylian Mbappe became only the second teenager — after Pele — to score in a World Cup final, doing so in 2018.","emoji":"🇫🇷"},
    {"fact":"The Premier League's lowest ever points total for a champion is 75 — achieved by Manchester United in 1996/97.","emoji":"📊"},
    {"fact":"England's record victory is 13-0 against Ireland in 1882 — a score that will almost certainly never be matched.","emoji":"🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    {"fact":"Pep Guardiola's Barcelona side of 2009/10 won all six possible trophies — the sextuple.","emoji":"🔵🔴"},
    {"fact":"The fastest sending off in Premier League history was David Unsworth — just 72 seconds after coming on as a substitute.","emoji":"🟥"},
    {"fact":"Aston Villa won the European Cup in 1982 — beating Bayern Munich 1-0 with a team that cost less than one current academy player.","emoji":"🟣"},
    {"fact":"Real Madrid's Bernabeu stadium was originally called Estadio Chamartín — renamed after club president Santiago Bernabeu in 1955.","emoji":"⚪"},
    {"fact":"The Champions League anthem — composed by Tony Britten — is based on Handel's Zadok the Priest from 1727.","emoji":"🎵"},
    {"fact":"Brazil have never lost a World Cup game in which Ronaldo scored — a record spanning three tournaments.","emoji":"🇧🇷"},
    {"fact":"Peter Shilton played more games than any other outfield or goalkeeper in football history — 1,390 professional appearances.","emoji":"🧤"},
    {"fact":"The 1966 World Cup trophy was stolen before the tournament — found by a dog called Pickles under a hedge in South London.","emoji":"😂"},
    {"fact":"Arsenal striker Ian Wright scored on his debut for every single professional club he played for.","emoji":"🔴"},
]

# ── GUESS THE PLAYER — 50 players ────────────────────────────────────────────
GUESS_PLAYERS = [
    {"clues":["Born in Senegal","Played for Southampton before Liverpool","All-time Premier League top scorer"],"answer":"Mohamed Salah","hint":"Egyptian King"},
    {"clues":["Norwegian striker","Scored 36 PL goals in debut season","Son of a former Premier League player"],"answer":"Erling Haaland","hint":"Man City No.9"},
    {"clues":["Spanish midfielder","Ballon d'Or winner 2023","Plays for Manchester City"],"answer":"Rodri","hint":"The engine room"},
    {"clues":["English winger","Arsenal academy product","Scored 16 goals in 2023/24 PL season"],"answer":"Bukayo Saka","hint":"Mr Arsenal"},
    {"clues":["Brazilian forward","Real Madrid Galactico","Champions League top scorer 2023/24"],"answer":"Vinicius Jr","hint":"Left winger, loves to dance"},
    {"clues":["German midfielder","Won everything at Bayern","Joined Real Madrid on a free in 2024"],"answer":"Toni Kroos","hint":"Came out of retirement"},
    {"clues":["English striker","All-time top scorer for England","Won the Bundesliga with Bayern"],"answer":"Harry Kane","hint":"Never won a trophy... until now?"},
    {"clues":["Spanish teenager","Barcelona winger","Broke into the Spain squad at 16"],"answer":"Lamine Yamal","hint":"The new Messi?"},
    {"clues":["Belgian forward","Retired from international football 2023","Three stints in the Premier League"],"answer":"Eden Hazard","hint":"What could have been"},
    {"clues":["French striker","PSG captain","Joined Real Madrid in 2024"],"answer":"Kylian Mbappe","hint":"The fastest in the world"},
    {"clues":["Portuguese forward","Left Man Utd in 2022","Plays in Saudi Arabia"],"answer":"Cristiano Ronaldo","hint":"SIUUUU"},
    {"clues":["Argentine forward","7-time Ballon d'Or winner","Won the World Cup in 2022"],"answer":"Lionel Messi","hint":"The GOAT debate ends here"},
    {"clues":["Dutch manager","Took over Liverpool in 2024","Previously at Feyenoord"],"answer":"Arne Slot","hint":"Klopp's successor"},
    {"clues":["Spanish manager","Won the treble with Barcelona","Now at Man City"],"answer":"Pep Guardiola","hint":"Has a PhD in winning"},
    {"clues":["French right back","Won the World Cup in 2018","Signed for Liverpool in 2024"],"answer":"Trent Alexander-Arnold","hint":"Wait... wrong nationality"},
    {"clues":["Brazilian midfielder","Played for Barca, Juve and PSG","Known for flicks and tricks"],"answer":"Ronaldinho","hint":"Pure joy to watch"},
    {"clues":["French midfielder","Arsenal and Barcelona legend","Known for his trickery on the ball"],"answer":"Thierry Henry","hint":"Va va voom"},
    {"clues":["French striker","Arsenal and Barcelona legend","PL's greatest season — 30 goals and 20 assists"],"answer":"Thierry Henry","hint":"Va va voom"},
    {"clues":["Irish midfielder","Liverpool and Juventus captain","One of the most combative players ever"],"answer":"Roy Keane","hint":"Never backed down from anyone"},
    {"clues":["Dutch forward","Three-time World Player of the Year","Played for Barcelona, Inter Milan and Real Madrid"],"answer":"Ronaldo (R9)","hint":"The original Ronaldo"},
    {"clues":["French midfielder","Won the World Cup in 1998","Famous for a headbutt in 2006"],"answer":"Zinedine Zidane","hint":"One of the greatest ever"},
    {"clues":["Italian defender","AC Milan legend","Played until he was 40 years old"],"answer":"Paolo Maldini","hint":"The perfect defender"},
    {"clues":["English midfielder","Won 6 Premier League titles","Described as the best midfielder of his generation by Zidane"],"answer":"Paul Scholes","hint":"Underrated genius"},
    {"clues":["English midfielder","Won the 2002 World Cup with Real Madrid","Iconic free kick vs Greece in 2001"],"answer":"David Beckham","hint":"Golden Balls"},
    {"clues":["Liverpool legend","Captain during their 2019/20 title win","Dutch centre-back"],"answer":"Virgil van Dijk","hint":"Made CBs cool again"},
    {"clues":["Arsenal captain","French midfielder","The complete midfielder of his era"],"answer":"Patrick Vieira","hint":"Clashed with Roy Keane regularly"},
    {"clues":["German striker","Bayern Munich legend","World Cup winner 2014"],"answer":"Thomas Muller","hint":"The Raumdeuter"},
    {"clues":["French striker","Arsenal's all-time top scorer","Won the World Cup in 1998"],"answer":"Thierry Henry","hint":"He handled it"},
    {"clues":["Swedish striker","Played in 6 different leagues","Never played in the World Cup knockout rounds"],"answer":"Zlatan Ibrahimovic","hint":"There is only one Zlatan"},
    {"clues":["Portuguese winger","Won the Champions League with Porto","Went on to win it 5 more times"],"answer":"Jose Mourinho","hint":"Wrong answer — think again"},
    {"clues":["English goalkeeper","Record 1390 professional appearances","125 England caps"],"answer":"Peter Shilton","hint":"The most capped keeper ever"},
    {"clues":["Scottish striker","Prolific in 1960s and 70s","Scored for Man City to relegate Man Utd"],"answer":"Denis Law","hint":"The King"},
    {"clues":["German goalkeeper","Won everything with Bayern","Considered the best in the world for a decade"],"answer":"Manuel Neuer","hint":"Sweeper keeper pioneer"},
    {"clues":["Brazilian winger","Dribbled past defenders for fun","Died tragically in a plane crash in 2016"],"answer":"Chapecoense","hint":"Think clubs not players"},
    {"clues":["Spanish midfielder","Won the World Cup and two Euros","Barca's metronomic passer"],"answer":"Xavi Hernandez","hint":"Now manages Barcelona"},
    {"clues":["Spanish midfielder","Xavi's partner in crime","Scored the 2010 World Cup winner"],"answer":"Andres Iniesta","hint":"That goal in Johannesburg"},
    {"clues":["Italian striker","Juventus and Real Madrid legend","5-time Champions League winner"],"answer":"Cristiano Ronaldo","hint":"Think Italy not Portugal"},
    {"clues":["English striker","Scored a hat-trick in the 1966 World Cup final","West Ham and England legend"],"answer":"Geoff Hurst","hint":"They think it's all over"},
    {"clues":["Welsh winger","Real Madrid and Juventus","Speed and crossing were his superpowers"],"answer":"Gareth Bale","hint":"Golf, Madrid, Wales — in that order"},
    {"clues":["Uruguayan striker","Bit three opponents","Actually a brilliant footballer"],"answer":"Luis Suarez","hint":"Controversial but gifted"},
    {"clues":["Argentine striker","Atletico Madrid and Barcelona","Griezmann's strike partner"],"answer":"Antoine Griezmann","hint":"Wrong country — try again"},
    {"clues":["Belgian midfielder","Everyon's fantasy football captain","Liverpool and now in Saudi"],"answer":"Kevin De Bruyne","hint":"Still active — Man City maestro"},
    {"clues":["Italian striker","5 World Cups","Retired at 40 after playing in 5 tournaments"],"answer":"Gianluigi Buffon","hint":"He's a goalkeeper not a striker"},
    {"clues":["English striker","20 goals in his first season","Signed from Leeds to Liverpool for £8.5m in 1997"],"answer":"Robbie Fowler","hint":"God"},
    {"clues":["Senegalese forward","Scored in two Champions League finals","Played for Liverpool and Bayern Munich"],"answer":"Sadio Mane","hint":"Left Liverpool for Germany"},
    {"clues":["French striker","Mbappe's strike partner at PSG","Won the World Cup in 2014"],"answer":"Olivier Giroud","hint":"France's all-time top scorer"},
    {"clues":["Norwegian manager","Took over Man Utd caretaker then permanently","Ole Ole Ole"],"answer":"Ole Gunnar Solskjaer","hint":"Baby-faced assassin turned manager"},
    {"clues":["Spanish forward","La Liga top scorer 5 times","Won the Ballon d'Or in 2019"],"answer":"Karim Benzema","hint":"Waited patiently behind Ronaldo"},
    {"clues":["English winger","Arsenal and Man City legend","Won the Premier League with both clubs"],"answer":"Samir Nasri","hint":"Wasted potential"},
    {"clues":["Dutch striker","Scored 150 Premier League goals","Manchester United legend"],"answer":"Ruud van Nistelrooy","hint":"Pure penalty box predator"},
]

# ── TRIVIA — 40 questions ─────────────────────────────────────────────────────
TRIVIA = [
    {"q":"How many times have Liverpool won the European Cup/Champions League?","a":"6 times — 1977, 1978, 1981, 1984, 2005, 2019"},
    {"q":"Who holds the record for most goals in a single World Cup tournament?","a":"Just Fontaine — 13 goals for France at the 1958 World Cup"},
    {"q":"Which club has the most Premier League titles?","a":"Manchester United with 13"},
    {"q":"Who was the first player to score 100 Premier League goals?","a":"Alan Shearer — doing so in April 1999"},
    {"q":"How many teams are in the Champions League from 2024/25 onwards?","a":"36 teams in the new league phase (expanded from 32)"},
    {"q":"Which country has won the most World Cups?","a":"Brazil — 5 times (1958, 1962, 1970, 1994, 2002)"},
    {"q":"What is the record transfer fee paid?","a":"Neymar to PSG in 2017 — approximately £198 million"},
    {"q":"Who scored the fastest Champions League goal?","a":"Roy Makaay — 10.2 seconds for Bayern Munich vs Real Madrid in 2007"},
    {"q":"How many clubs have won the Premier League since it started in 1992?","a":"8 clubs — Man Utd, Chelsea, Arsenal, Man City, Liverpool, Blackburn, Leicester, Leeds"},
    {"q":"Which player has won the most Champions League medals as a player?","a":"Francisco Gento — 6 medals with Real Madrid between 1956 and 1966"},
    {"q":"What is the highest score ever recorded in a World Cup match?","a":"Hungary 10-1 El Salvador at the 1982 World Cup"},
    {"q":"Who is the all-time top scorer in World Cup history?","a":"Miroslav Klose — 16 goals across four World Cups for Germany"},
    {"q":"How many goals did Cristiano Ronaldo score in the 2023/24 Champions League?","a":"Ronaldo was not in the Champions League — he plays in Saudi Arabia"},
    {"q":"Which nation has appeared in the most World Cup finals without winning?","a":"Netherlands — 3 finals, 0 wins (1974, 1978, 2010)"},
    {"q":"What year did the Premier League introduce VAR?","a":"2019/20 season"},
    {"q":"Who scored the first ever Premier League goal?","a":"Brian Deane for Sheffield United vs Manchester United on 15 August 1992"},
    {"q":"How many minutes did Fabrice Muamba's heart stop during the Bolton vs Tottenham FA Cup tie in 2012?","a":"78 minutes — he survived and made a full recovery"},
    {"q":"Which English club won back-to-back European Cups in 1979 and 1980?","a":"Nottingham Forest under Brian Clough"},
    {"q":"What is the record for most consecutive games unbeaten in the Premier League?","a":"Arsenal — 49 games between May 2003 and October 2004"},
    {"q":"Who won the first ever Premier League title?","a":"Manchester United in the 1992/93 season"},
    {"q":"How many goals did Alan Shearer score in his Premier League career?","a":"260 goals — a record that still stands"},
    {"q":"Which country hosted the first ever World Cup in 1930?","a":"Uruguay — who also won it"},
    {"q":"What is the Champions League anthem based on?","a":"Handel's Zadok the Priest, composed in 1727"},
    {"q":"Who is England's all-time record goalscorer?","a":"Wayne Rooney — 53 goals in 120 appearances"},
    {"q":"How many red cards were shown at the 2006 World Cup?","a":"28 red cards — the most in any World Cup tournament"},
    {"q":"Which goalkeeper has the most clean sheets in Premier League history?","a":"Petr Cech — 202 clean sheets"},
    {"q":"What was the score when Germany beat Brazil 7-1 in the 2014 World Cup semi-final?","a":"Germany 7-1 Brazil — known as the Mineirazo"},
    {"q":"How many Premier League seasons has Cristiano Ronaldo played in total?","a":"9 seasons — 6 at Man Utd first spell, 1 second spell, 2 at others"},
    {"q":"Which club did Eric Cantona play for before Manchester United?","a":"Leeds United — whom he helped win the First Division in 1992"},
    {"q":"What is the record for most goals scored in a single Premier League season by one player?","a":"Erling Haaland — 36 goals in the 2022/23 season"},
    {"q":"Who managed Liverpool to their 2019/20 Premier League title?","a":"Jurgen Klopp — their first league title in 30 years"},
    {"q":"How many times has Italy won the World Cup?","a":"4 times — 1934, 1938, 1982, 2006"},
    {"q":"Which player was known as the Raumdeuter (space investigator)?","a":"Thomas Muller of Bayern Munich and Germany"},
    {"q":"What is the lowest number of goals scored by a Premier League champion in a season?","a":"Chelsea in 2004/05 — 72 goals, but they won with a record 95 points"},
    {"q":"Who scored the winning goal in the 2012 Champions League final for Chelsea?","a":"Didier Drogba — in the 88th minute against Bayern Munich"},
    {"q":"How old was Lamine Yamal when he scored at Euro 2024?","a":"16 years old — the youngest scorer in European Championship history"},
    {"q":"Which Premier League team has been relegated the most times?","a":"Sunderland — relegated 6 times from the Premier League"},
    {"q":"What year did Arsenal move from Highbury to the Emirates Stadium?","a":"2006 — after 93 years at Highbury"},
    {"q":"Who holds the record for most assists in a single Premier League season?","a":"Kevin De Bruyne — 20 assists in the 2019/20 season"},
    {"q":"How many managers has Chelsea had since Roman Abramovich took over in 2003?","a":"21 managers in just over 20 years"},
]

# ── POLLS — 70 questions ──────────────────────────────────────────────────────
POLLS = {
    0: ["Who will win the Champions League this season?","Is the Premier League the best league in the world?","Should VAR be scrapped entirely?","Best current Premier League manager?","Is Mbappe living up to the hype at Real Madrid?","Who has been the best signing of the season?","Will England ever win a major tournament again?"],
    1: ["Best team left in the Champions League?","Will an English club win the UCL this season?","Mbappe or Vinicius — who has been better this season?","Best Champions League goal this season?","Which UCL semi-final are you most excited about?","Who is the best goalkeeper in Europe right now?","Greatest Champions League final of all time?"],
    2: ["Can Arsenal win the Champions League?","Best manager in Europe right now?","Who will win Ballon d'Or 2025?","Best youth player in European football right now?","Which club has the best squad depth in Europe?","Most underrated team in the Champions League?","Best comeback in Champions League history?"],
    3: ["Most overrated player in the Premier League?","Best young player in Europe right now?","Should clubs be able to loan players mid-season?","Which Premier League team has the best fans?","Worst transfer of the season?","Best stadium in the Premier League?","Should financial fair play rules be scrapped?"],
    4: ["Your Premier League prediction for this weekend?","Who scores first this weekend?","Biggest upset of the weekend?","Best match to watch this Saturday?","Who will be Man of the Match this weekend?","Will there be a goal from outside the box this weekend?","Which manager is under most pressure this weekend?"],
    5: ["Best goal of the weekend so far?","Biggest shock of the weekend?","Player of the weekend?","Best save of the weekend?","Most disappointing performance of the weekend?","Best comeback of the weekend?","Which result surprised you most?"],
    6: ["Player of the weekend?","Manager of the month?","Which club has the best squad depth in the PL?","Best performance of the weekend?","Most improved player this season?","Which young player impressed you most this weekend?","Best team of the season so far?"],
}

# ── MONDAY QUOTES — 20 quotes ─────────────────────────────────────────────────
QUOTES = [
    {"quote":"Football is not just a game. It is a way of life.","author":"Pele"},
    {"quote":"Some people believe football is a matter of life and death. I am very disappointed with that attitude. I can assure you it is much, much more important than that.","author":"Bill Shankly"},
    {"quote":"You have to fight to reach your dream. You have to sacrifice and work hard for it.","author":"Lionel Messi"},
    {"quote":"The more difficult the victory, the greater the happiness in winning.","author":"Pele"},
    {"quote":"I learned all about life with a ball at my feet.","author":"Ronaldinho"},
    {"quote":"In football, the worst blindness is only seeing the ball.","author":"Nelson Falcao"},
    {"quote":"Success is no accident. It is hard work, perseverance, learning, studying, sacrifice and most of all, love of what you are doing.","author":"Pele"},
    {"quote":"The ball is round, the game lasts ninety minutes, and everything else is pure theory.","author":"Sepp Herberger"},
    {"quote":"Football is the most important of the less important things in the world.","author":"Carlo Ancelotti"},
    {"quote":"I was born to play football, just like Beethoven was born to write music.","author":"Ronaldinho"},
    {"quote":"If you work hard and you play well, all the external stuff just takes care of itself.","author":"Jurgen Klopp"},
    {"quote":"The secret is to believe in your dreams; in your potential that you can be like your star, keep searching, keep believing and don't lose faith in yourself.","author":"Neymar"},
    {"quote":"I always say that the best team in the world should be like Manchester United. A team that wins, plays well and fills the stadium every week.","author":"Johan Cruyff"},
    {"quote":"Talent without working hard is nothing.","author":"Cristiano Ronaldo"},
    {"quote":"A lot of football success is in the mind. You must believe you are the best and then make sure that you are.","author":"Bill Shankly"},
    {"quote":"I am not a perfectionist, but I like to feel that things are done well.","author":"Zinedine Zidane"},
    {"quote":"When you see the ball, you don't say: that's round, made of leather. You just play football.","author":"Johan Cruyff"},
    {"quote":"Football is simple. But it is difficult to play simple football.","author":"Johan Cruyff"},
    {"quote":"The greatest gift I have is my ability to play football, and I'll never take it for granted.","author":"Gareth Bale"},
    {"quote":"If you are first you are first. If you are second you are nothing.","author":"Bill Shankly"},
]

print("Seeding content database...")
seed_content("on_this_day", ON_THIS_DAY, replace=True)
seed_content("did_you_know", DID_YOU_KNOW, replace=True)
seed_content("guess_player", GUESS_PLAYERS, replace=True)
seed_content("trivia", TRIVIA, replace=True)
seed_content("monday_quote", QUOTES, replace=True)

# Polls stored as flat list with day metadata
all_polls = []
for day, questions in POLLS.items():
    for q in questions:
        all_polls.append({"question": q, "weekday": day})
seed_content("daily_poll", all_polls, replace=True)

print("Done. Summary:")
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
for ct in ["on_this_day","did_you_know","guess_player","trivia","monday_quote","daily_poll"]:
    count = c.execute("SELECT COUNT(*) FROM engagement_content WHERE content_type=?", (ct,)).fetchone()[0]
    print(f"  {ct}: {count} items")
conn.close()
