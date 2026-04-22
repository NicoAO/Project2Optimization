import csv
from collections import defaultdict
import gurobipy as gp
from gurobipy import GRB
from datetime import datetime

teams = set()
dates = set()
homeGameDates = defaultdict(list)
awayGameDates = defaultdict(list)
matchups = defaultdict(lambda: defaultdict(lambda: {"Home": 0, "Away": 0}))

with open('games.csv', mode='r', newline='') as file:
    reader = csv.reader(file)
    next(reader)

    for row in reader:
        date, visitor, pts, home, pts1, attend, log, arena, notes = row

        teams.add(home)
        teams.add(visitor)
        dates.add(date)

        homeGameDates[home].append(date)
        awayGameDates[visitor].append(date)

        matchups[home][visitor]["Home"] += 1
        matchups[visitor][home]["Away"] += 1

teams = sorted(teams)
dateFormat = "%a, %b %d, %Y"
dates = sorted(
    dates,
    key=lambda d: datetime.strptime(d, dateFormat)
)

for team in teams:
    homeGameDates[team] = sorted(set(homeGameDates[team]))
    awayGameDates[team] = sorted(set(awayGameDates[team]))

env = gp.Env()
m = gp.Model("NBA_Schedule_Part2_Smaller", env=env)

# only create feasible variables
possibleMatchups = []
for homeTeam in teams:
    for awayTeam in teams:
        if homeTeam != awayTeam:
            for date in dates:
                if date in homeGameDates[homeTeam] and date in awayGameDates[awayTeam]:
                    possibleMatchups.append((homeTeam, awayTeam, date))

x = m.addVars(possibleMatchups, vtype=GRB.BINARY, name="x")

# each team plays at home on its original home dates
for team in teams:
    for date in homeGameDates[team]:
        m.addConstr(
            gp.quicksum(
                x[team, opponent, date]
                for opponent in teams
                if opponent != team and (team, opponent, date) in x
            ) == 1,
            name=f"homeDate_{team}_{date}"
        )

# each team plays away on its original away dates
for team in teams:
    for date in awayGameDates[team]:
        m.addConstr(
            gp.quicksum(
                x[opponent, team, date]
                for opponent in teams
                if opponent != team and (opponent, team, date) in x
            ) == 1,
            name=f"awayDate_{team}_{date}"
        )

# away counts
for team in teams:
    for opponent in teams:
        if opponent != team:
            m.addConstr(
                gp.quicksum(
                    x[opponent, team, date]
                    for date in dates
                    if (opponent, team, date) in x
                ) == matchups[team][opponent]["Away"],
                name=f"awayCount_{team}_{opponent}"
            )

# home counts
for team in teams:
    for opponent in teams:
        if opponent != team:
            m.addConstr(
                gp.quicksum(
                    x[team, opponent, date]
                    for date in dates
                    if (team, opponent, date) in x
                ) == matchups[team][opponent]["Home"],
                name=f"homeCount_{team}_{opponent}"
            )

# Part 3: Time Zone Constraint
# map team to timezone where
# timezone mapping
teamTimeZone = {
    "Atlanta Hawks": 0,
    "Boston Celtics": 0,
    "Brooklyn Nets": 0,
    "Chicago Bulls": 1,
    "Cleveland Cavaliers": 0,
    "Dallas Mavericks": 1,
    "Denver Nuggets": 2,
    "Golden State Warriors": 3,
    "Houston Rockets": 1,
    "Los Angeles Lakers": 3,
    "Miami Heat": 0,
    "Milwaukee Bucks": 1,
    "New York Knicks": 0,
    "Philadelphia 76ers": 0,
    "Phoenix Suns": 3,
    "Toronto Raptors": 0
}

zones = sorted(set(teamTimeZone.values()))

dateFormat = "%a, %b %d, %Y"

# sort each team's game dates
teamGameDates = {}
for team in teams:
    gameDates = homeGameDates[team] + awayGameDates[team]
    teamGameDates[team] = sorted(
        set(gameDates),
        key=lambda d: datetime.strptime(d, dateFormat)
    )

# timezone variables
# y[team, date, zone] = 1 if team plays in zone on date
possibleTZ = []
for team in teams:
    for date in teamGameDates[team]:
        for zone in zones:
            possibleTZ.append((team, date, zone))

y = m.addVars(
    possibleTZ,
    vtype=GRB.BINARY,
    name="y"
)

# each team must be in exactly one timezone per game date
for team in teams:
    for date in teamGameDates[team]:
        m.addConstr(
            gp.quicksum(
                y[team, date, zone]
                for zone in zones
            ) == 1
        )

# link timezone variables to game decision variables
for team in teams:
    for date in teamGameDates[team]:
        for zone in zones:
            expr = gp.LinExpr()
            # home game timezone
            if date in homeGameDates[team]:
                if teamTimeZone[team] == zone:
                    expr += gp.quicksum(
                        x[team, opponent, date]
                        for opponent in teams
                        if opponent != team
                        and (team, opponent, date) in x
                    )

            # away game timezone
            if date in awayGameDates[team]:
                expr += gp.quicksum(
                    x[host, team, date]
                    for host in teams
                    if host != team
                    and (host, team, date) in x
                    and teamTimeZone[host] == zone
                )
            m.addConstr(
                y[team, date, zone] == expr
            )

# travel constraint
for team in teams:
    gameDates = teamGameDates[team]
    for i in range(len(gameDates) - 2):
        d1 = gameDates[i]
        d2 = gameDates[i+1]
        d3 = gameDates[i+2]
        for z1 in zones:
            for z2 in zones:
                for z3 in zones:
                    if abs(z2-z1) + abs(z3-z2) >= 4:
                        m.addConstr(
                            y[team,d1,z1]
                            + y[team,d2,z2]
                            + y[team,d3,z3]
                            <= 2
                        )

m.setObjective(0, GRB.MINIMIZE)
m.optimize()