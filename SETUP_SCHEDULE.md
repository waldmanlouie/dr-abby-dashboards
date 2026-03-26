# Daily Dashboard Auto-Refresh — Setup Guide

## What it does
Runs `build_all_dashboards.py` every day at 6:30 AM, which rebuilds all 3 dashboards from their Excel source files:

| Dashboard | Source Excel |
|-----------|-------------|
| Trending Analysis (`1 Dr Abby Trending.html`) | `Competitor Analysis.xlsx` |
| Growth (`2 Dr Abby Growth Dashboard.html`) | `Profiles.xlsx` + `Competitor Analysis.xlsx` |
| Projects (`3 Dr Abby Projects.html`) | `Gersh Deals.xlsx` |

## Prerequisites
- Python 3 installed
- pandas + openpyxl installed (`pip install pandas openpyxl`)

## Windows (Task Scheduler)

1. Open **Task Scheduler** (search "Task Scheduler" in Start menu)
2. Click **Create Basic Task**
3. Name: `Dr Abby Dashboard Refresh`
4. Trigger: **Daily**, Start time: **6:30 AM**
5. Action: **Start a program**
   - Program/script: `python`
   - Arguments: `"C:\Users\YOUR_USERNAME\Dropbox\Dr Abby Dashboards\build_all_dashboards.py"`
   - Start in: `"C:\Users\YOUR_USERNAME\Dropbox\Dr Abby Dashboards"`
6. Check **Open the Properties dialog** → Finish
7. In Properties: check **Run whether user is logged on or not**

> Replace `YOUR_USERNAME` and adjust paths to match your Dropbox folder location.

## Mac (launchd)

Create file `~/Library/LaunchAgents/com.drabby.dashboards.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.drabby.dashboards</string>
    <key>ProgramArguments</key>
    <array>
        <string>python3</string>
        <string>/Users/louiswaldman/Dropbox/Dr Abby Dashboards/build_all_dashboards.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>6</integer>
        <key>Minute</key>
        <integer>30</integer>
    </dict>
</dict>
</plist>
```
Then run: `launchctl load ~/Library/LaunchAgents/com.drabby.dashboards.plist`

## Manual run (anytime)
```
cd ~/Dropbox/Dr\ Abby\ Dashboards
python build_all_dashboards.py
```
