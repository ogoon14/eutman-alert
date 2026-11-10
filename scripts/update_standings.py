#!/usr/bin/env python3
"""Refresh men's league rankings from OK Savings Bank volleyball official page.
Run through GitHub Actions. Never replace the snapshot on a parse/network failure.
"""
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

SOURCE = 'https://www.okfinancialsports.com/volleyball/game/team_ranking.asp'
OUT = Path(__file__).resolve().parents[1] / 'standings.json'
TEAMS = {'우리카드', '현대캐피탈', '대한항공', '삼성화재', 'OK저축은행', '한국전력', 'KB손해보험'}


def parse(html):
    soup = BeautifulSoup(html, 'html.parser')
    teams = []
    for tr in soup.select('tr'):
        cells = [re.sub(r'\s+', '', td.get_text(' ', strip=True)) for td in tr.find_all(['td', 'th'], recursive=False)]
        if len(cells) < 6:
            continue
        # Official table columns: rank, team, games, wins, losses, points, ...
        # Some layouts wrap the team name with extra text/logo labels.
        team = next((name for name in TEAMS if cells[1] == name or cells[1].endswith(name)), None)
        if not team:
            continue
        try:
            rank, played, win, loss, points = [int(re.sub(r'[^0-9]', '', cells[i])) for i in (0, 2, 3, 4, 5)]
        except (ValueError, IndexError):
            continue
        if not (1 <= rank <= 7 and 0 <= played <= 50 and 0 <= win <= played and 0 <= loss <= played and 0 <= points <= 150 and win + loss == played):
            continue
        teams.append({'rank': rank, 'team': team, 'played': played, 'win': win, 'loss': loss, 'points': points})
    # Reject incomplete or malformed results rather than publishing incorrect data.
    unique = {t['team']: t for t in teams}
    if set(unique) != TEAMS or len(set(t['rank'] for t in unique.values())) != 7:
        raise ValueError(f'Expected 7 unique teams and ranks; found {len(unique)} teams: {sorted(unique)}')
    return sorted(unique.values(), key=lambda x: x['rank'])


def main():
    response = requests.get(SOURCE, timeout=25, headers={'User-Agent': 'Mozilla/5.0 (compatible; PersonalVolleyballDashboard/1.0)'})
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    teams = parse(response.text)
    previous = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {}
    # Only commit when rank/record data changes; avoid unnecessary Pages deployments.
    if previous.get('teams') == teams and previous.get('source') == SOURCE:
        print('No rankings changes; keeping existing file.')
        return
    now = datetime.now(ZoneInfo('Asia/Seoul'))
    payload = {
        'asOf': now.strftime('%Y-%m-%d'),
        'fetchedAt': now.isoformat(timespec='minutes'),
        'season': '2026-2027',
        'source': SOURCE,
        'teams': teams,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Updated {OUT} with {len(teams)} teams.')


if __name__ == '__main__':
    main()
