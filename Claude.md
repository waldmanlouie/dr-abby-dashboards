# Dr Abby Dashboard Suite

## What This Is

Three HTML dashboards that track Dr. Abby's social media performance across TikTok, Instagram, and YouTube. Python scripts read Excel data files, crunch the numbers, and produce self-contained HTML files you open in Chrome. No server needed — everything is baked into the HTML.

A daily scheduled job (macOS launchd) rebuilds all three dashboards at 6:30 AM automatically.


## Folder Location

`~/Dropbox/Dr Abby Dashboards/`

Everything lives in this one flat folder — scripts, templates, Excel sources, and output HTML files.


## The Three Dashboards

### 1. Trending Analysis ("Trending")
- **What it shows:** Snapshot of all tracked creators' latest videos ranked by views/hr, with engagement metrics and viral/superviral tagging.
- **Output:** `1 Dr Abby Trending.html`
- **Data source:** `Competitor Analysis.xlsx` (Videos sheet, latest extract date only)
- **Build script:** `build_trending_dashboard.py`
- **Template:** `trending_dashboard_template.html`
- **Also has:** A "Load from Excel" button in the browser so you can refresh data client-side without rebuilding.

### 2. Growth
- **What it shows:** Dr. Abby's follower growth over time, monthly video performance trends, competitive rankings, viral/superviral rates, and a full video table with all tracked creators.
- **Output:** `2 Dr Abby Growth Dashboard.html`
- **Data sources:** `Profiles.xlsx` (follower history) + `Competitor Analysis.xlsx` (video data)
- **Build script:** `build_growth_dashboard.py`
- **Template:** `growth_dashboard_template.html`

### 3. Projects
- **What it shows:** Brand partnership deals on a Gantt timeline, revenue tracking, deliverables, and exclusivity terms.
- **Output:** `3 Dr Abby Projects.html`
- **Data source:** `Gersh Deals.xlsx` (first sheet)
- **Build script:** `build_projects_dashboard.py`
- **Template:** `projects_dashboard_template.html`

All three dashboards share a top nav bar that links between them. They must stay in the same folder for navigation to work.


## How the Build Works

Each dashboard follows a **template + build script** pattern:

1. Python script reads Excel file(s) with pandas
2. Processes data (dedup, compute views/hr, engagement, rankings, etc.)
3. Serializes result as JSON
4. Injects JSON into the HTML template (replacing `__DATA_PLACEHOLDER__` or `__SNAPSHOT_PLACEHOLDER__`)
5. Writes the output HTML file

The master script `build_all_dashboards.py` runs all three in sequence and logs results to `build.log`.


## Daily Auto-Refresh

- **Schedule:** Every day at 6:30 AM local time
- **Mechanism:** macOS launchd
- **Config:** `~/Library/LaunchAgents/com.drabby.dashboards.plist`
- **Python:** `/Library/Frameworks/Python.framework/Versions/3.14/bin/python3`
- **Log:** `build.log` in this folder (appends each run)
- **Behavior:** If Mac is asleep at 6:30 AM, launchd runs it when the Mac wakes up

### Useful Terminal Commands

```bash
# Run manually
cd ~/Dropbox/Dr\ Abby\ Dashboards && python3 build_all_dashboards.py

# Check if schedule is loaded
launchctl list | grep drabby

# Stop/start schedule
launchctl unload ~/Library/LaunchAgents/com.drabby.dashboards.plist
launchctl load ~/Library/LaunchAgents/com.drabby.dashboards.plist

# Check latest build log
tail -15 ~/Dropbox/Dr\ Abby\ Dashboards/build.log
```


## Complete File Reference

### Output HTML (what you open in Chrome)
| File | Dashboard |
|------|-----------|
| `1 Dr Abby Trending.html` | Trending Analysis |
| `2 Dr Abby Growth Dashboard.html` | Growth |
| `3 Dr Abby Projects.html` | Projects |

### Build Scripts
| File | What It Does |
|------|-------------|
| `build_all_dashboards.py` | Master script — runs all three builds in sequence, logs to `build.log`. This is what the daily schedule runs. |
| `build_trending_dashboard.py` | Builds Trending dashboard from `Competitor Analysis.xlsx` |
| `build_growth_dashboard.py` | Builds Growth dashboard from `Profiles.xlsx` + `Competitor Analysis.xlsx` |
| `build_projects_dashboard.py` | Builds Projects dashboard from `Gersh Deals.xlsx` |

### Templates
| File | For Dashboard |
|------|--------------|
| `trending_dashboard_template.html` | Trending Analysis — has `__DATA_PLACEHOLDER__` |
| `growth_dashboard_template.html` | Growth — has `__DATA_PLACEHOLDER__` |
| `projects_dashboard_template.html` | Projects — has `__SNAPSHOT_PLACEHOLDER__` |

To change how a dashboard looks, edit the **template** (not the output HTML). Then rebuild.

### Excel Data Sources (all in this folder)
| File | Used By |
|------|---------|
| `Competitor Analysis.xlsx` | Trending + Growth (Videos sheet for video data) |
| `Profiles.xlsx` | Growth (follower counts over time) |
| `Gersh Deals.xlsx` | Projects (brand deals) |

### Config & Logs
| File | Purpose |
|------|---------|
| `build.log` | Append-only log from each daily build run |
| `SETUP_SCHEDULE.md` | Instructions for setting up the launchd schedule |
| `Claude.md` | This file |
| `Dr Abby Dashboard Manual.docx` | Detailed technical manual |


## Key Technical Details

- **Dr. Abby identifiers:** TikTok/IG = `drabby6`, `abby.waldmanmd`; YouTube = `doctor-abby` (profiles), `Dr. Abby` (videos)
- **Views/hr calculation:** Views / hours since post (PostDate = CreateTime minus 4 hours for timezone offset)
- **Viral thresholds:** Superviral = 10,000+ views/hr; Viral = 1,000-9,999 views/hr
- **Engagement:** (Likes + Comments + Shares) / Views * 100. Shares excluded from formula when null.
- **Extract date filtering:** Trending dashboard only shows the most recent extract date. Growth uses all historical data.
- **Build timestamps:** Shown in Eastern time on each dashboard.
- **Dependencies:** Python 3, pandas, openpyxl (`pip3 install pandas openpyxl`)


## Making Changes

- **Dashboard layout/design:** Edit the template HTML file, then rebuild
- **Data processing logic:** Edit the corresponding build script
- **Add a new dashboard:** Create a build script + template, add the script name to the `SCRIPTS` list in `build_all_dashboards.py`
- **Never edit output HTML directly** — changes get overwritten on next build
