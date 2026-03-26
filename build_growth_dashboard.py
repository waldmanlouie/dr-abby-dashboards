#!/usr/bin/env python3
"""Build Dr Abby Growth Dashboard.html from Profiles.xlsx + Competitor Analysis.xlsx"""

import pandas as pd
import json
import math
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROFILES_XLSX = SCRIPT_DIR / "Profiles.xlsx"
COMPETITOR_XLSX = SCRIPT_DIR / "Competitor Analysis.xlsx"
OUTPUT = SCRIPT_DIR / "2 Dr Abby Growth Dashboard.html"

# Dr Abby author names per source
ABBY_AUTHORS_PROFILES = {'drabby6', 'abby.waldmanmd', 'doctor-abby'}
ABBY_AUTHORS_VIDEOS = {'drabby6', 'abby.waldmanmd', 'Dr. Abby'}
ABBY_DISPLAY = 'Dr. Abby'

def norm_dur(v):
    if pd.isna(v) or v is None:
        return 0
    if hasattr(v, 'hour'):  # datetime.time
        return v.hour * 3600 + v.minute * 60 + v.second
    v = str(v)
    if ':' in v:
        parts = v.split(':')
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    try:
        return int(float(v))
    except Exception:
        return 0

def safe(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return v

def build_data():
    # ── PROFILES: growth over time ──
    prof = pd.read_excel(PROFILES_XLSX, sheet_name="Profiles")
    prof['Extract Date'] = pd.to_datetime(prof['Extract Date'], utc=True)
    prof['date'] = prof['Extract Date'].dt.strftime('%Y-%m-%d')
    prof = prof.dropna(subset=['Author'])
    if 'Extrapolated' not in prof.columns:
        prof['Extrapolated'] = False
    prof['Extrapolated'] = prof['Extrapolated'].fillna(False).astype(bool)

    # Tag Dr Abby
    prof['is_abby'] = prof['Author'].isin(ABBY_AUTHORS_PROFILES)

    # Get per-author per-platform per-date: take last reading of the day
    prof = prof.sort_values('Extract Date')
    daily = prof.groupby(['Author', 'Platform', 'date']).last().reset_index()

    # Build Dr Abby growth series (by platform)
    abby_growth = {}
    for plat in ['TikTok', 'Instagram', 'YouTube']:
        abby_names_for_plat = daily[(daily['is_abby']) & (daily['Platform'] == plat)]
        if abby_names_for_plat.empty:
            continue
        series = abby_names_for_plat.sort_values('date')
        abby_growth[plat] = [
            {'date': r['date'],
             'followers': safe(r.get('Followers')),
             'views': safe(r.get('Views')),
             'likes': safe(r.get('Likes')),
             'videos': safe(r.get('Videos')),
             'ext': bool(r.get('Extrapolated', False))}
            for _, r in series.iterrows()
        ]

    # Build competitor growth series (top 10 by latest followers per platform)
    comp_growth = {}
    for plat in ['TikTok', 'Instagram', 'YouTube']:
        plat_data = daily[(~daily['is_abby']) & (daily['Platform'] == plat)]
        if plat_data.empty:
            continue
        # Get latest followers per author
        latest = plat_data.sort_values('date').groupby('Author').last().reset_index()
        top10 = latest.nlargest(10, 'Followers')['Author'].tolist()
        comp_growth[plat] = {}
        for author in top10:
            author_data = plat_data[plat_data['Author'] == author].sort_values('date')
            comp_growth[plat][author] = [
                {'date': r['date'],
                 'followers': safe(r.get('Followers')),
                 'views': safe(r.get('Views')),
                 'likes': safe(r.get('Likes')),
                 'videos': safe(r.get('Videos')),
                 'ext': bool(r.get('Extrapolated', False))}
                for _, r in author_data.iterrows()
            ]

    # Dr Abby current stats (latest per platform) with last-complete-month delta
    abby_current = {}

    # Determine last complete month: if today is Feb 2026, last complete = Jan 2026
    from datetime import date
    today = date.today()
    if today.month == 1:
        lcm_year, lcm_month = today.year - 1, 12
    else:
        lcm_year, lcm_month = today.year, today.month - 1
    lcm_label = f"{date(lcm_year, lcm_month, 1):%b-%Y}"
    lcm_start = f"{lcm_year}-{lcm_month:02d}-01"
    lcm_end = f"{lcm_year}-{lcm_month:02d}-31"  # safe upper bound
    # Month before last complete month
    if lcm_month == 1:
        plcm_year, plcm_month = lcm_year - 1, 12
    else:
        plcm_year, plcm_month = lcm_year, lcm_month - 1
    plcm_end = f"{plcm_year}-{plcm_month:02d}-31"

    for plat in ['TikTok', 'Instagram', 'YouTube']:
        abby_plat = daily[(daily['is_abby']) & (daily['Platform'] == plat)]
        if abby_plat.empty:
            continue
        sorted_plat = abby_plat.sort_values('date')
        latest_row = sorted_plat.iloc[-1]
        first_row = sorted_plat.iloc[0]
        followers_now = safe(latest_row.get('Followers'))
        followers_start = safe(first_row.get('Followers'))

        # Last complete month delta
        end_of_lcm = sorted_plat[sorted_plat['date'] <= lcm_end]
        start_of_lcm = sorted_plat[sorted_plat['date'] <= plcm_end]
        lcm_followers_end = safe(end_of_lcm.iloc[-1]['Followers']) if len(end_of_lcm) > 0 else None
        lcm_followers_start = safe(start_of_lcm.iloc[-1]['Followers']) if len(start_of_lcm) > 0 else None
        lcm_delta = None
        lcm_delta_pct = None
        if lcm_followers_end and lcm_followers_start and lcm_followers_start > 0:
            lcm_delta = lcm_followers_end - lcm_followers_start
            lcm_delta_pct = round(lcm_delta / lcm_followers_start * 100, 1)

        abby_current[plat] = {
            'followers': followers_now,
            'views': safe(latest_row.get('Views')),
            'likes': safe(latest_row.get('Likes')),
            'videos': safe(latest_row.get('Videos')),
            'followersStart': followers_start,
            'dateStart': first_row['date'],
            'dateEnd': latest_row['date'],
            'lcmLabel': lcm_label,
            'lcmDelta': lcm_delta,
            'lcmDeltaPct': lcm_delta_pct,
        }

    # Competitive ranking — ALL authors per platform with full growth series
    rankings = {}
    for plat in ['TikTok', 'Instagram', 'YouTube']:
        plat_daily = daily[daily['Platform'] == plat]
        plat_latest = plat_daily.sort_values('date').groupby('Author').last().reset_index()
        plat_latest = plat_latest.sort_values('Followers', ascending=False).reset_index(drop=True)
        plat_latest['rank'] = range(1, len(plat_latest) + 1)
        abby_row = plat_latest[plat_latest['is_abby']]
        total = len(plat_latest)
        # Build per-author follower time-series for growth calcs
        author_series = {}
        for author, grp in plat_daily.groupby('Author'):
            author_series[author] = [
                {'date': r['date'], 'followers': safe(r['Followers']), 'ext': bool(r.get('Extrapolated', False))}
                for _, r in grp.sort_values('date').iterrows()
            ]
        if not abby_row.empty:
            rankings[plat] = {
                'rank': int(abby_row.iloc[0]['rank']),
                'total': total,
                'allAuthors': [
                    {'author': ABBY_DISPLAY if bool(r['is_abby']) else r['Author'],
                     'origAuthor': r['Author'],
                     'followers': safe(r['Followers']),
                     'isAbby': bool(r['is_abby'])}
                    for _, r in plat_latest.iterrows()
                ],
                'authorSeries': author_series
            }

    # ── VIDEOS: performance data ──
    vids_all = pd.read_excel(COMPETITOR_XLSX, sheet_name="Videos")
    vids_all['Extract Date'] = pd.to_datetime(vids_all['Extract Date'], utc=True)
    vids_all['CreateTime'] = pd.to_datetime(vids_all['CreateTime'], errors='coerce', utc=True)
    vids_all['extract_date_only'] = vids_all['Extract Date'].dt.date
    vids = vids_all.dropna(subset=['VidID']).copy()

    # For each VidID, keep only the most recent extract date
    vids = vids.sort_values('Extract Date')
    vids_latest = vids.groupby('VidID').last().reset_index()

    # Tag Dr Abby
    vids_latest['is_abby'] = vids_latest['Author'].isin(ABBY_AUTHORS_VIDEOS)

    # Compute views/hr and engagement
    vids_latest['PostDate'] = vids_latest['CreateTime'] - timedelta(hours=4)
    vids_latest['hours_diff'] = (vids_latest['Extract Date'] - vids_latest['PostDate']).dt.total_seconds() / 3600
    vids_latest['views_hr'] = (vids_latest['Views'] / vids_latest['hours_diff']).round(1)
    vids_latest.loc[vids_latest['hours_diff'] <= 0, 'views_hr'] = 0

    def calc_eng(row):
        v = row['Views']
        if pd.isna(v) or v == 0:
            return 0
        l = row['Likes'] if pd.notna(row['Likes']) else 0
        c = row['Comments'] if pd.notna(row['Comments']) else 0
        s = row['Shares'] if pd.notna(row['Shares']) else 0
        return round((l + c + s) / v * 100, 2)

    vids_latest['engagement'] = vids_latest.apply(calc_eng, axis=1)

    # Dr Abby video stats summary
    abby_vids = vids_latest[vids_latest['is_abby']]
    comp_vids = vids_latest[~vids_latest['is_abby']]

    # First extract date for videos
    first_extract = str(vids['Extract Date'].min().date())

    abby_video_summary = {
        'totalVideos': len(abby_vids),
        'avgViews': round(abby_vids['Views'].mean()) if len(abby_vids) > 0 else 0,
        'avgViewsHr': round(abby_vids['views_hr'].mean(), 1) if len(abby_vids) > 0 else 0,
        'avgEngagement': round(abby_vids['engagement'].mean(), 2) if len(abby_vids) > 0 else 0,
        'medianViews': round(abby_vids['Views'].median()) if len(abby_vids) > 0 else 0,
        'medianViewsHr': round(abby_vids['views_hr'].median(), 1) if len(abby_vids) > 0 else 0,
        'totalViews': int(abby_vids['Views'].sum()) if len(abby_vids) > 0 else 0,
        'firstExtractDate': first_extract,
    }
    comp_video_summary = {
        'totalVideos': len(comp_vids),
        'avgViews': round(comp_vids['Views'].mean()) if len(comp_vids) > 0 else 0,
        'avgViewsHr': round(comp_vids['views_hr'].mean(), 1) if len(comp_vids) > 0 else 0,
        'avgEngagement': round(comp_vids['engagement'].mean(), 2) if len(comp_vids) > 0 else 0,
        'medianViews': round(comp_vids['Views'].median()) if len(comp_vids) > 0 else 0,
        'medianViewsHr': round(comp_vids['views_hr'].median(), 1) if len(comp_vids) > 0 else 0,
    }

    # ── VIRAL / SUPERVIRAL video stats ──
    # Dr Abby only
    abby_superviral = abby_vids[abby_vids['views_hr'] >= 10000]
    abby_viral = abby_vids[(abby_vids['views_hr'] >= 1000) & (abby_vids['views_hr'] < 10000)]
    abby_viral_plus = abby_vids[abby_vids['views_hr'] >= 1000]  # viral + superviral

    # Monthly breakdown for Dr Abby (by PostDate month)
    abby_with_post = abby_vids[abby_vids['PostDate'].notna()].copy()
    abby_with_post['post_month'] = abby_with_post['PostDate'].dt.strftime('%Y-%m')

    # Last complete month label
    lcm_str = f"{lcm_year}-{lcm_month:02d}"

    # Superviral by month
    sv_monthly = abby_with_post[abby_with_post['views_hr'] >= 10000].groupby('post_month').size()
    v_monthly = abby_with_post[(abby_with_post['views_hr'] >= 1000) & (abby_with_post['views_hr'] < 10000)].groupby('post_month').size()

    # All months Dr Abby has videos
    all_abby_months = abby_with_post['post_month'].unique()
    n_months = max(len(all_abby_months), 1)

    viral_stats = {
        'superviralTotal': len(abby_superviral),
        'superviralPct': round(len(abby_superviral) / max(len(abby_vids), 1) * 100, 1),
        'superviralLastMonth': int(sv_monthly.get(lcm_str, 0)),
        'superviralAvgMonth': round(len(abby_superviral) / n_months, 1),
        'viralTotal': len(abby_viral),
        'viralPct': round(len(abby_viral) / max(len(abby_vids), 1) * 100, 1),
        'viralLastMonth': int(v_monthly.get(lcm_str, 0)),
        'viralAvgMonth': round(len(abby_viral) / n_months, 1),
        'lcmLabel': lcm_label,
    }

    # Dr Abby videos over time (by post month)
    abby_vids_ts = abby_vids[abby_vids['CreateTime'].notna()].copy()
    abby_vids_ts['month'] = abby_vids_ts['CreateTime'].dt.strftime('%Y-%m')
    abby_vids_ts['is_sv'] = abby_vids_ts['views_hr'] >= 10000
    abby_vids_ts['is_viral'] = (abby_vids_ts['views_hr'] >= 1000) & (abby_vids_ts['views_hr'] < 10000)
    monthly = abby_vids_ts.groupby('month').agg(
        count=('VidID', 'count'),
        avgViews=('Views', 'mean'),
        avgViewsHr=('views_hr', 'mean'),
        avgEng=('engagement', 'mean'),
        avgLikes=('Likes', 'mean'),
        totalViews=('Views', 'sum'),
        svCount=('is_sv', 'sum'),
        viralCount=('is_viral', 'sum'),
    ).fillna(0).reset_index()
    # Compute views_hr percentiles per month for distribution chart
    vhr_percentiles = abby_vids_ts.groupby('month')['views_hr'].quantile([0.25, 0.5, 0.75]).unstack()
    vhr_percentiles.columns = ['p25', 'p50', 'p75']
    vhr_percentiles = vhr_percentiles.reset_index()
    pct_map = {r['month']: (round(r['p25'], 1), round(r['p50'], 1), round(r['p75'], 1))
               for _, r in vhr_percentiles.iterrows()}

    abby_monthly = [
        {'month': r['month'], 'count': int(r['count']),
         'avgViews': round(r['avgViews']), 'avgViewsHr': round(r['avgViewsHr'], 1),
         'avgEng': round(r['avgEng'], 2), 'totalViews': int(r['totalViews']),
         'svCount': int(r['svCount']), 'viralCount': int(r['viralCount']),
         'avgLikes': round(r['avgLikes'], 1),
         'vhrP25': pct_map.get(r['month'], (0,0,0))[0],
         'vhrP50': pct_map.get(r['month'], (0,0,0))[1],
         'vhrP75': pct_map.get(r['month'], (0,0,0))[2]}
        for _, r in monthly.iterrows()
    ]

    # Build Dr Abby monthly FOLLOWER snapshots (sum across platforms, keyed by month)
    # Use the profile data: for each month take the last reading
    abby_prof = daily[daily['is_abby']].copy()
    abby_prof['month'] = pd.to_datetime(abby_prof['date']).dt.strftime('%Y-%m')
    # Per platform per month: take last reading
    abby_prof_monthly = abby_prof.sort_values('date').groupby(['Platform', 'month']).last().reset_index()
    # Sum followers across all platforms per month
    abby_follower_monthly_all = abby_prof_monthly.groupby('month').agg(
        followers=('Followers', 'sum')
    ).reset_index().sort_values('month')
    # Per-platform follower monthly
    abby_follower_monthly_plat = {}
    for plat in ['TikTok', 'Instagram', 'YouTube']:
        plat_data = abby_prof_monthly[abby_prof_monthly['Platform'] == plat].sort_values('month')
        if len(plat_data) > 0:
            abby_follower_monthly_plat[plat] = [
                {'month': r['month'], 'followers': int(r['Followers']) if pd.notna(r['Followers']) else 0}
                for _, r in plat_data.iterrows()
            ]
    # Combine into abbyMonthly (merge follower data)
    follower_map_all = {r['month']: int(r['followers']) for _, r in abby_follower_monthly_all.iterrows()}
    for rec in abby_monthly:
        rec['followers'] = follower_map_all.get(rec['month'], None)

    # Per-platform monthly for Dr Abby
    abby_monthly_by_plat = {}
    for plat_full in ['TikTok', 'Instagram', 'YouTube']:
        plat_vids = abby_vids_ts[abby_vids_ts['Platform'] == plat_full]
        if len(plat_vids) == 0:
            continue
        pm = plat_vids.groupby('month').agg(
            count=('VidID', 'count'),
            avgViewsHr=('views_hr', 'mean'),
            avgEng=('engagement', 'mean'),
            avgLikes=('Likes', 'mean'),
            totalViews=('Views', 'sum'),
            svCount=('is_sv', 'sum'),
            viralCount=('is_viral', 'sum'),
        ).fillna(0).reset_index()
        plat_follower_data = abby_follower_monthly_plat.get(plat_full, [])
        plat_follower_map = {r['month']: r['followers'] for r in plat_follower_data}
        # Percentiles per platform
        plat_pct = plat_vids.groupby('month')['views_hr'].quantile([0.25, 0.5, 0.75]).unstack()
        plat_pct.columns = ['p25', 'p50', 'p75']
        plat_pct = plat_pct.reset_index()
        plat_pct_map = {r['month']: (round(r['p25'], 1), round(r['p50'], 1), round(r['p75'], 1))
                        for _, r in plat_pct.iterrows()}
        abby_monthly_by_plat[plat_full] = [
            {'month': r['month'], 'count': int(r['count']),
             'avgViewsHr': round(r['avgViewsHr'], 1),
             'avgEng': round(r['avgEng'], 2), 'totalViews': int(r['totalViews']),
             'svCount': int(r['svCount']), 'viralCount': int(r['viralCount']),
             'avgLikes': round(r['avgLikes'], 1),
             'followers': plat_follower_map.get(r['month'], None),
             'vhrP25': plat_pct_map.get(r['month'], (0,0,0))[0],
             'vhrP50': plat_pct_map.get(r['month'], (0,0,0))[1],
             'vhrP75': plat_pct_map.get(r['month'], (0,0,0))[2]}
            for _, r in pm.iterrows()
        ]

    # Competitor avg by month for comparison
    comp_vids_ts = comp_vids[comp_vids['CreateTime'].notna()].copy()
    comp_vids_ts['month'] = comp_vids_ts['CreateTime'].dt.strftime('%Y-%m')
    comp_monthly = comp_vids_ts.groupby('month').agg(
        count=('VidID', 'count'),
        avgViews=('Views', 'mean'),
        avgViewsHr=('views_hr', 'mean'),
        avgEng=('engagement', 'mean')
    ).fillna(0).reset_index()
    comp_monthly_data = [
        {'month': r['month'], 'count': int(r['count']),
         'avgViews': round(r['avgViews']), 'avgViewsHr': round(r['avgViewsHr'], 1),
         'avgEng': round(r['avgEng'], 2)}
        for _, r in comp_monthly.iterrows()
    ]

    # Per-author video averages (for competitive comparison)
    author_stats = vids_latest.groupby('Author').agg(
        videoCount=('VidID', 'count'),
        avgViews=('Views', 'mean'),
        avgViewsHr=('views_hr', 'mean'),
        avgEng=('engagement', 'mean'),
        totalViews=('Views', 'sum'),
        avgLikes=('Likes', 'mean')
    ).fillna(0).reset_index()
    author_stats['is_abby'] = author_stats['Author'].isin(ABBY_AUTHORS_VIDEOS)
    # Merge all Abby accounts into one
    abby_stats_row = author_stats[author_stats['is_abby']].agg({
        'videoCount': 'sum',
        'avgViews': 'mean',
        'avgViewsHr': 'mean',
        'avgEng': 'mean',
        'totalViews': 'sum',
        'avgLikes': 'mean'
    })
    author_leaderboard = []
    # Add Abby combined
    author_leaderboard.append({
        'author': ABBY_DISPLAY,
        'isAbby': True,
        'videoCount': int(abby_stats_row['videoCount']),
        'avgViews': round(abby_stats_row['avgViews']),
        'avgViewsHr': round(abby_stats_row['avgViewsHr'], 1),
        'avgEng': round(abby_stats_row['avgEng'], 2),
        'totalViews': int(abby_stats_row['totalViews']),
        'avgLikes': round(abby_stats_row['avgLikes'])
    })
    # Add competitors
    for _, r in author_stats[~author_stats['is_abby']].iterrows():
        if r['videoCount'] >= 5:  # minimum threshold
            author_leaderboard.append({
                'author': r['Author'],
                'isAbby': False,
                'videoCount': int(r['videoCount']),
                'avgViews': round(r['avgViews']),
                'avgViewsHr': round(r['avgViewsHr'], 1),
                'avgEng': round(r['avgEng'], 2),
                'totalViews': int(r['totalViews']),
                'avgLikes': round(r['avgLikes'])
            })
    author_leaderboard.sort(key=lambda x: x['avgViewsHr'], reverse=True)

    # Top videos table (Dr Abby + top competitor videos)
    def build_video_record(r):
        post_date = r['PostDate']
        text = ''
        if pd.notna(r.get('Title')):
            text = str(r['Title'])
        if pd.notna(r.get('Text')):
            txt = str(r['Text'])
            text = text + '; ' + txt if text else txt
        if len(text) > 300:
            text = text[:300]
        plat_map = {'TikTok': 'TT', 'Instagram': 'IG', 'YouTube': 'YT'}
        return {
            'postDate': post_date.strftime('%-m/%-d/%y, %-I:%M%p').lower().replace('am', 'am').replace('pm', 'pm') if pd.notna(post_date) else '',
            'postDateRaw': post_date.strftime('%Y-%m-%d') if pd.notna(post_date) else '',
            'author': r['Author'] if pd.notna(r['Author']) else '',
            'isAbby': bool(r['is_abby']),
            'len': norm_dur(r.get('Duration (s)')),
            'viewsHr': float(r['views_hr']) if pd.notna(r['views_hr']) else 0,
            'views': int(r['Views']) if pd.notna(r['Views']) else 0,
            'likes': int(r['Likes']) if pd.notna(r['Likes']) else 0,
            'shares': int(r['Shares']) if pd.notna(r['Shares']) else -1,
            'comments': int(r['Comments']) if pd.notna(r['Comments']) else 0,
            'engagement': float(r['engagement']),
            'text': text,
            'platform': plat_map.get(r['Platform'], r['Platform']) if pd.notna(r['Platform']) else '',
            'url': r['URL'] if pd.notna(r.get('URL')) else '',
            'sharesNull': bool(pd.isna(r.get('Shares'))),
            'music': r['Music'] if pd.notna(r.get('Music')) else ''
        }

    # All Dr Abby videos + top 500 competitor videos by views/hr
    all_abby_records = [build_video_record(r) for _, r in abby_vids.iterrows()]
    top_comp = comp_vids.nlargest(500, 'views_hr')
    comp_records = [build_video_record(r) for _, r in top_comp.iterrows()]
    all_video_records = all_abby_records + comp_records
    all_video_records.sort(key=lambda x: x['viewsHr'], reverse=True)

    # Per-author MONTHLY video stats for competitive ranking (period-filterable)
    # Structure: { platform: { author: [ {month, views, sv, v, n} ] } }
    vids_with_post = vids_latest[vids_latest['PostDate'].notna()].copy()
    vids_with_post['post_month'] = vids_with_post['PostDate'].dt.strftime('%Y-%m')
    author_monthly_vid = {}
    for (author, plat_full, month), grp in vids_with_post.groupby(['Author', 'Platform', 'post_month']):
        author_monthly_vid.setdefault(plat_full, {}).setdefault(author, []).append({
            'mo': month,
            'vi': int(grp['Views'].sum()),
            'sv': int((grp['views_hr'] >= 10000).sum()),
            'vr': int(((grp['views_hr'] >= 1000) & (grp['views_hr'] < 10000)).sum()),
            'n': len(grp)
        })
    # Merge Dr Abby accounts per platform
    for plat_full in ['TikTok', 'Instagram', 'YouTube']:
        if plat_full not in author_monthly_vid:
            continue
        abby_keys = [k for k in author_monthly_vid[plat_full] if k in ABBY_AUTHORS_VIDEOS]
        if abby_keys:
            month_agg = {}
            for k in abby_keys:
                for rec in author_monthly_vid[plat_full].pop(k):
                    m = rec['mo']
                    if m not in month_agg:
                        month_agg[m] = {'mo': m, 'vi': 0, 'sv': 0, 'vr': 0, 'n': 0}
                    month_agg[m]['vi'] += rec['vi']
                    month_agg[m]['sv'] += rec['sv']
                    month_agg[m]['vr'] += rec['vr']
                    month_agg[m]['n'] += rec['n']
            author_monthly_vid[plat_full][ABBY_DISPLAY] = list(month_agg.values())

    # YouTube fix: remap video display names to profile handle names
    # Videos sheet uses display names (e.g. "Dr Adel Twins") while Profiles
    # uses channel handles (e.g. "DrAdelTwins"). Two-step mapping:
    #   1) Extract channel handle from YouTube URLs in raw video data
    #   2) Fallback: normalize both names (strip non-alphanumeric, lowercase)
    if 'YouTube' in author_monthly_vid:
        yt_prof_authors = set(daily[daily['Platform'] == 'YouTube']['Author'].dropna().unique())

        def _norm_name(name):
            """Strip non-alphanumeric, lowercase, remove trailing digits."""
            s = re.sub(r'[^a-zA-Z0-9]', '', name).lower()
            return re.sub(r'\d+$', '', s)

        # Step 1: extract channel handle from YouTube URLs in raw vids data
        # Use vids_all (before VidID filter) since channel URLs are on non-video rows
        yt_raw = vids_all[vids_all['Platform'] == 'YouTube']

        def extract_yt_handle(url):
            if pd.isna(url): return None
            m = re.search(r'youtube\.com/(?:@|c/)([^/?\s]+)', str(url))
            return m.group(1) if m else None

        vid_author_to_handle = {}
        for vid_author, grp in yt_raw.groupby('Author'):
            handles = grp['URL'].apply(extract_yt_handle).dropna().unique()
            if len(handles) > 0:
                vid_author_to_handle[str(vid_author)] = handles[0]

        # Step 2a: match URL handle to profile author (case-insensitive)
        prof_lower_map = {a.lower(): a for a in yt_prof_authors}
        vid_to_prof = {}  # video display name -> profile handle name
        for vid_author, handle in vid_author_to_handle.items():
            if vid_author == ABBY_DISPLAY:
                continue  # Dr. Abby already merged under ABBY_DISPLAY
            prof_match = prof_lower_map.get(handle.lower())
            if prof_match:
                vid_to_prof[vid_author] = prof_match

        # Step 2b: fallback — normalized name matching for unmatched authors
        prof_norm_map = {_norm_name(a): a for a in yt_prof_authors}
        for vid_author in list(author_monthly_vid['YouTube'].keys()):
            if vid_author not in vid_to_prof:
                norm = _norm_name(vid_author)
                prof_match = prof_norm_map.get(norm)
                if prof_match:
                    vid_to_prof[vid_author] = prof_match

        # Step 2c: manual overrides for names that can't be auto-matched
        yt_manual_map = {
            'Dr Dray': 'DrDrayzday',
        }
        for vid_author, prof_name in yt_manual_map.items():
            if vid_author in author_monthly_vid['YouTube'] and prof_name in yt_prof_authors:
                vid_to_prof[vid_author] = prof_name

        # Step 3: remap authorMonthlyVid keys for YouTube
        yt_data = author_monthly_vid['YouTube']
        remapped = {}
        for vid_author, records in yt_data.items():
            prof_name = vid_to_prof.get(vid_author, vid_author)
            if prof_name in remapped:
                # Merge if multiple video authors map to same profile
                existing = {r['mo']: r for r in remapped[prof_name]}
                for rec in records:
                    if rec['mo'] in existing:
                        existing[rec['mo']]['vi'] += rec['vi']
                        existing[rec['mo']]['sv'] += rec['sv']
                        existing[rec['mo']]['vr'] += rec['vr']
                        existing[rec['mo']]['n'] += rec['n']
                    else:
                        existing[rec['mo']] = dict(rec)
                remapped[prof_name] = list(existing.values())
            else:
                remapped[prof_name] = records
        author_monthly_vid['YouTube'] = remapped

    # Platform breakdown for Dr Abby videos
    abby_platform_breakdown = {}
    for plat in ['TT', 'IG', 'YT']:
        plat_full = {'TT': 'TikTok', 'IG': 'Instagram', 'YT': 'YouTube'}[plat]
        plat_vids = abby_vids[abby_vids['Platform'] == plat_full]
        if len(plat_vids) > 0:
            abby_platform_breakdown[plat] = {
                'count': len(plat_vids),
                'avgViews': round(plat_vids['Views'].mean()),
                'avgViewsHr': round(plat_vids['views_hr'].mean(), 1),
                'avgEng': round(plat_vids['engagement'].mean(), 2)
            }

    return {
        'abbyGrowth': abby_growth,
        'compGrowth': comp_growth,
        'abbyCurrent': abby_current,
        'rankings': rankings,
        'abbyVideoSummary': abby_video_summary,
        'abbyMonthly': abby_monthly,
        'abbyMonthlyByPlat': abby_monthly_by_plat,
        'compMonthly': comp_monthly_data,
        'authorLeaderboard': author_leaderboard,
        'videos': all_video_records,
        'abbyPlatformBreakdown': abby_platform_breakdown,
        'authorMonthlyVid': author_monthly_vid,
        'viralStats': viral_stats,
        'buildDate': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')
    }


def main():
    data = build_data()
    data_json = json.dumps(data, default=str)

    # Read template
    template_path = SCRIPT_DIR / "growth_dashboard_template.html"
    html = template_path.read_text()
    html = html.replace('__DATA_PLACEHOLDER__', data_json)
    html = html.replace('__BUILD_TIMESTAMP__', datetime.now(tz=ZoneInfo('America/New_York')).strftime('%b %d, %Y %I:%M %p'))
    OUTPUT.write_text(html)
    n_vids = len(data['videos'])
    n_authors = len(data['authorLeaderboard'])
    print(f"Growth Dashboard built: {n_vids} videos, {n_authors} authors tracked")


if __name__ == '__main__':
    main()
