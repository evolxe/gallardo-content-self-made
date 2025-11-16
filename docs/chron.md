The runPython.sh script is ready and working. To set it up as a cron job:

### Summary

Created runPython.sh that:

Sets up a Python virtual environment (if it doesn't exist)

Installs/updates dependencies from requirements.txt

Runs sheet.py

Logs all activity to runPython.log

Uses absolute paths (works in cron)

To set up a cron job:

Open your crontab:
```
crontab -e
```

Add a line like this (runs every hour at minute 0):
```
0 * * * * /Users/millionairemacmillionairemac/Developer/gallardo-automated-content-pipeline/runPython.sh >> /Users/millionairemacmillionairemac/Developer/gallardo-automated-content-pipeline/cron.log 2>&1
```
Or run it every 15 minutes:
```
*/15 * * * * /Users/millionairemacmillionairemac/Developer/gallardo-automated-content-pipeline/runPython.sh >> /Users/millionairemacmillionairemac/Developer/gallardo-automated-content-pipeline/cron.log 2>&1
```

Save and exit. The cron job will run automatically.

The script logs to runPython.log in the project directory, and cron output will also go to cron.log if you redirect it as shown above.

The script is executable and tested. It will work in cron because it uses absolute paths and doesn't rely on interactive shell features.
