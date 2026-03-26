"""Build Dr Abby Trending.html from Competitor Analysis.xlsx"""
import json
import math
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

SCRIPT_DIR = Path(__file__).resolve().parent
COMPETITOR_XLSX = SCRIPT_DIR / "Competitor Analysis.xlsx"
PROFILES_XLSX = SCRIPT_DIR / "Profiles.xlsx"
TEMPLATE = SCRIPT_DIR / "trending_dashboard_template.html"
OUTPUT = SCRIPT_DIR / "1 Dr Abby Trending.html"

# Dr. Abby author names in the Videos sheet
ABBY_AUTHORS = {'drabby6', 'abby.waldmanmd', 'Dr. Abby'}
PLAT_MAP = {'TikTok': 'TT', 'Instagram': 'IG', 'YouTube': 'YT'}


def norm_dur(v):
    """Normalize duration to integer seconds."""
    if pd.isna(v) or v == '':
        return 0
    s = str(v)
    if ':' in s:
        parts = s.split(':')
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    try:
        return round(float(s))
    except (ValueError, TypeError):
        return 0


def compute_views_hr(df):
    """Add viewsHr column to a dataframe that already has PostDate, Extract Date, Views."""
    df = df.copy()
    df['hrs_diff'] = (df['Extract Date'] - df['PostDate']).dt.total_seconds() / 3600
    df['viewsHr'] = 0.0
    mask = df['hrs_diff'] > 0
    df.loc[mask, 'viewsHr'] = (df.loc[mask, 'Views'] / df.loc[mask, 'hrs_diff']).round(1)
    return df


def compute_engagement(row):
    """Compute engagement % for a single row."""
    views = int(row['Views']) if pd.notna(row['Views']) else 0
    likes = int(row['Likes']) if pd.notna(row['Likes']) else 0
    comments = int(row['Comments']) if pd.notna(row['Comments']) else 0
    shares_null = pd.isna(row.get('Shares'))
    shares_num = 0 if shares_null else int(row['Shares'])
    if views == 0:
        return 0
    if shares_null:
        return round((comments + likes) / views * 100, 2)
    return round((comments + likes + shares_num) / views * 100, 2)


def snapshot_stats(vhr_list, views_list):
    """Compute tier breakdown + reach + top video from lists of views/hr and views."""
    n = len(vhr_list)
    if n == 0:
        return None
    sv = sum(1 for v in vhr_list if v >= 10000)
    viral = sum(1 for v in vhr_list if 1000 <= v < 10000)
    poor = sum(1 for v in vhr_list if v < 100)
    normal = n - sv - viral - poor
    total_views = sum(views_list)
    top_vhr = max(vhr_list)
    return {
        'total': n, 'sv': sv, 'viral': viral, 'normal': normal, 'poor': poor,
        'svPct': round(sv / n * 100, 1),
        'viralPct': round(viral / n * 100, 1),
        'normalPct': round(normal / n * 100, 1),
        'poorPct': round(poor / n * 100, 1),
        'totalViews': total_views,
        'topVhr': round(top_vhr, 1),
    }


def build_abby_historical(all_vids):
    """Compute Dr. Abby's per-snapshot baselines over the last 6 months, per platform + ALL."""
    abby = all_vids[all_vids['Author'].isin(ABBY_AUTHORS)].copy()
    if abby.empty:
        return None

    # Only use snapshots from the last 6 months (180 days)
    cutoff = abby['Extract Date'].max() - timedelta(days=180)
    abby = abby[abby['Extract Date'] >= cutoff]
    if abby.empty:
        return None

    abby = abby.sort_values('Views', ascending=True)
    abby = abby.drop_duplicates(subset=['VidID', 'extract_date_str'], keep='last')
    abby['PostDate'] = abby['CreateTime'] - timedelta(hours=4)
    abby = compute_views_hr(abby)
    abby['plat_short'] = abby['Platform'].map(PLAT_MAP)

    # Compute baselines for ALL and each platform
    baselines = {}
    for plat_key in ['ALL', 'TT', 'IG', 'YT']:
        if plat_key == 'ALL':
            subset = abby
        else:
            subset = abby[abby['plat_short'] == plat_key]
        if subset.empty:
            continue

        snapshots = []
        for date_str, grp in subset.groupby('extract_date_str'):
            n = len(grp)
            vhr_list = grp['viewsHr'].fillna(0).tolist()
            views_list = grp['Views'].fillna(0).tolist()
            sv = sum(1 for v in vhr_list if v >= 10000)
            viral = sum(1 for v in vhr_list if 1000 <= v < 10000)
            poor = sum(1 for v in vhr_list if v < 100)
            normal = n - sv - viral - poor
            snapshots.append({
                'sv': sv, 'viral': viral, 'normal': normal, 'poor': poor, 'n': n,
                'svPct': round(sv / max(n, 1) * 100, 1),
                'viralPct': round(viral / max(n, 1) * 100, 1),
                'normalPct': round(normal / max(n, 1) * 100, 1),
                'poorPct': round(poor / max(n, 1) * 100, 1),
                'totalViews': int(sum(views_list)),
                'topVhr': round(max(vhr_list), 1),
            })

        if not snapshots:
            continue

        ns = len(snapshots)
        baselines[plat_key] = {
            'avgSvPct': round(sum(s['svPct'] for s in snapshots) / ns, 1),
            'avgViralPct': round(sum(s['viralPct'] for s in snapshots) / ns, 1),
            'avgNormalPct': round(sum(s['normalPct'] for s in snapshots) / ns, 1),
            'avgPoorPct': round(sum(s['poorPct'] for s in snapshots) / ns, 1),
            'avgTotalViews': round(sum(s['totalViews'] for s in snapshots) / ns),
            'avgTopVhr': round(sum(s['topVhr'] for s in snapshots) / ns, 1),
            'snapshotCount': ns,
        }

    return baselines if baselines else None


# Profile author names (different from Videos sheet — YouTube uses 'doctor-abby')
ABBY_PROFILE_AUTHORS = {'drabby6', 'abby.waldmanmd', 'doctor-abby'}

def build_follower_growth():
    """Compute follower growth: 2-week weekly avg vs 6-month weekly avg, per platform + total."""
    try:
        profiles = pd.read_excel(PROFILES_XLSX)
    except Exception:
        return None
    profiles['Extract Date'] = pd.to_datetime(profiles['Extract Date'], utc=True)
    abby = profiles[profiles['Author'].isin(ABBY_PROFILE_AUTHORS)].copy()
    if abby.empty:
        return None
    abby['date'] = abby['Extract Date'].dt.date
    abby['plat'] = abby['Platform'].map(PLAT_MAP)
    max_date = abby['Extract Date'].max()
    two_wk_cutoff = (max_date - timedelta(days=14)).date()
    six_mo_cutoff = (max_date - timedelta(days=180)).date()

    growth = {}
    total_followers = 0
    total_2wk_weekly = 0
    total_6mo_weekly = 0

    for plat in ['TT', 'IG', 'YT']:
        p = abby[abby['plat'] == plat].sort_values('Extract Date')
        p = p.drop_duplicates(subset=['date'], keep='last')
        if p.empty:
            continue
        latest = p.iloc[-1]
        followers_raw = int(latest['Followers'])
        total_followers += followers_raw
        followers = round(followers_raw / 1000) * 1000  # round to nearest 1000
        entry = {'followers': followers}

        # Rounding: TT/IG round to nearest 100, YT uses exact
        def rnd(v):
            if plat == 'YT':
                return round(v)
            return round(v / 100) * 100

        # 2-week weekly average
        ref_2w = p[p['date'] <= two_wk_cutoff]
        if not ref_2w.empty:
            ref = ref_2w.iloc[-1]
            days = (latest['date'] - ref['date']).days
            if days > 0:
                raw = diff_raw = followers_raw - int(ref['Followers'])
                weekly_raw = diff_raw / days * 7
                weekly = rnd(weekly_raw)
                entry['weekly2wk'] = weekly
                entry['weekly2wkRaw'] = round(weekly_raw, 1)
                total_2wk_weekly += weekly

        # 6-month weekly average
        ref_6m = p[p['date'] <= six_mo_cutoff]
        if not ref_6m.empty:
            ref = ref_6m.iloc[-1]
            days = (latest['date'] - ref['date']).days
            if days > 0:
                diff_raw = followers_raw - int(ref['Followers'])
                weekly_raw = diff_raw / days * 7
                weekly = rnd(weekly_raw)
                entry['weekly6mo'] = weekly
                entry['weekly6moRaw'] = round(weekly_raw, 1)
                total_6mo_weekly += weekly

        growth[plat] = entry

    # Sum raw values for accurate ALL percentage
    raw_2wk = sum(growth.get(p, {}).get('weekly2wkRaw', 0) for p in ['TT', 'IG', 'YT'])
    raw_6mo = sum(growth.get(p, {}).get('weekly6moRaw', 0) for p in ['TT', 'IG', 'YT'])
    growth['ALL'] = {
        'followers': round(total_followers / 1000) * 1000,
        'weekly2wk': total_2wk_weekly,
        'weekly6mo': total_6mo_weekly,
        'weekly2wkRaw': round(raw_2wk, 1),
        'weekly6moRaw': round(raw_6mo, 1),
    }
    return growth


def build_data():
    all_vids = pd.read_excel(COMPETITOR_XLSX, sheet_name="Videos")
    all_vids['Extract Date'] = pd.to_datetime(all_vids['Extract Date'], utc=True)
    all_vids['CreateTime'] = pd.to_datetime(all_vids['CreateTime'], errors='coerce', utc=True)
    all_vids = all_vids.dropna(subset=['VidID'])
    all_vids['extract_date_str'] = all_vids['Extract Date'].dt.strftime('%Y-%m-%d')

    # ── Historical baselines (all extract dates, per platform) ──
    baselines = build_abby_historical(all_vids)

    # ── Current snapshot (latest extract date only) ──
    max_date = all_vids['extract_date_str'].max()
    vids = all_vids[all_vids['extract_date_str'] == max_date].copy()

    # Dedup by VidID: keep row with highest Views
    vids = vids.sort_values('Views', ascending=True)
    vids = vids.drop_duplicates(subset=['VidID'], keep='last')

    # Compute PostDate and views/hr
    vids['PostDate'] = vids['CreateTime'] - timedelta(hours=4)
    vids = compute_views_hr(vids)

    # Build records
    records = []
    for _, r in vids.iterrows():
        views = int(r['Views']) if pd.notna(r['Views']) else 0
        likes = int(r['Likes']) if pd.notna(r['Likes']) else 0
        comments = int(r['Comments']) if pd.notna(r['Comments']) else 0
        shares_null = pd.isna(r.get('Shares'))
        shares_num = 0 if shares_null else int(r['Shares'])
        eng = compute_engagement(r)

        text = str(r.get('Text', '') or '')
        title = r.get('Title')
        if pd.notna(title) and str(title).strip():
            text = (str(title) + '; ' + text) if text else str(title)
        if len(text) > 300:
            text = text[:300]

        post_date = r['PostDate']
        post_date_str = ''
        if pd.notna(post_date):
            post_date_str = post_date.strftime('%-m/%-d/%y, %-I:%M%p').lower().replace('am', 'am').replace('pm', 'pm')

        platform = r['Platform'] if pd.notna(r['Platform']) else ''
        plat_short = PLAT_MAP.get(platform, platform)
        author = str(r['Author']) if pd.notna(r['Author']) else ''

        records.append({
            'postDate': post_date_str,
            'postDateRaw': post_date.strftime('%Y-%m-%d %H:%M') if pd.notna(post_date) else '',
            'author': author,
            'isAbby': author in ABBY_AUTHORS,
            'len': norm_dur(r.get('Duration (s)')),
            'music': str(r.get('Music', '') or ''),
            'viewsHr': float(r['viewsHr']) if pd.notna(r['viewsHr']) else 0,
            'views': views,
            'likes': likes,
            'shares': -1 if shares_null else shares_num,
            'comments': comments,
            'engagement': eng,
            'text': text,
            'platform': plat_short,
            'url': str(r['URL']) if pd.notna(r.get('URL')) else '',
            'sharesNull': shares_null
        })

    records.sort(key=lambda x: x['viewsHr'], reverse=True)

    # ── Dr. Abby snapshot stats per platform ──
    abby_snapshot = {}
    for plat_key in ['ALL', 'TT', 'IG', 'YT']:
        if plat_key == 'ALL':
            abby_recs = [r for r in records if r['isAbby']]
            all_recs = records
        else:
            abby_recs = [r for r in records if r['isAbby'] and r['platform'] == plat_key]
            all_recs = [r for r in records if r['platform'] == plat_key]

        if not abby_recs:
            continue

        vhr_list = [r['viewsHr'] for r in abby_recs]
        views_list = [r['views'] for r in abby_recs]
        stats = snapshot_stats(vhr_list, views_list)

        # All Abby ranks in the platform-filtered full list (sorted by viewsHr desc)
        abby_ranks = []
        for i, r in enumerate(all_recs):
            if r['isAbby']:
                abby_ranks.append({'rank': i + 1, 'plat': r['platform']})
        stats['ranks'] = abby_ranks
        stats['totalInRanking'] = len(all_recs)

        abby_snapshot[plat_key] = stats

    # Add per-platform tier counts to ALL snapshot for breakdown display
    if 'ALL' in abby_snapshot:
        for tier in ['sv', 'viral', 'normal', 'poor']:
            abby_snapshot['ALL'][tier + 'Plat'] = [
                abby_snapshot.get(p, {}).get(tier, 0) for p in ['TT', 'IG', 'YT']
            ]

    follower_growth = build_follower_growth()

    return {
        'extractDate': max_date,
        'videos': records,
        'abbySnapshot': abby_snapshot,
        'abbyBaselines': baselines,
        'followerGrowth': follower_growth,
    }


def main():
    data = build_data()
    data_json = json.dumps(data, default=str)

    html = TEMPLATE.read_text()
    html = html.replace('__DATA_PLACEHOLDER__', data_json)
    html = html.replace('__BUILD_TIMESTAMP__', datetime.now(tz=ZoneInfo('America/New_York')).strftime('%b %d, %Y %I:%M %p'))
    OUTPUT.write_text(html)

    print(f"Trending Dashboard built: {len(data['videos'])} videos, extract date {data['extractDate']}")


if __name__ == '__main__':
    main()
