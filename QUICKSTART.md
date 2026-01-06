# OGBot Clojure - Quick Start Guide

## 5-Minute Setup

### Step 1: Install Java & Leiningen (2 minutes)

```bash
# Check Java (need 11+)
java -version

# If not installed:
# Ubuntu/Debian: sudo apt install openjdk-11-jdk
# Mac: brew install openjdk@11
# Windows: Download from https://adoptium.net/

# Install Leiningen
# Linux/Mac:
curl https://raw.githubusercontent.com/technomancy/leiningen/stable/bin/lein > ~/bin/lein
chmod +x ~/bin/lein
lein version  # Downloads dependencies on first run

# Windows:
# Download lein.bat from https://leiningen.org/ and add to PATH
```

### Step 2: Configure Bot (1 minute)

```bash
# Copy sample config
cp files/config/config.ini.sample files/config/config.ini

# Edit with your credentials
nano files/config/config.ini  # or use any text editor
```

**Minimal config:**
```ini
[options]
username = YOUR_USERNAME
password = YOUR_PASSWORD
webpage = uni1.ogame.org
attackRadius = 10
attackingShip = smallCargo
probesToSend = 1
```

### Step 3: Run Bot (1 minute)

**Option A: Web UI (Recommended)**
```bash
# Starts web interface on http://localhost:3000
./run-bot.sh              # Linux/Mac
run-bot.bat               # Windows

# OR directly:
lein run

# Then open http://localhost:3000 in your browser
```

**Option B: Console Mode**
```bash
# Console mode (no GUI)
./run-bot.sh --no-gui     # Linux/Mac
run-bot.bat --no-gui      # Windows

# OR directly:
lein run --no-gui
```

### Step 4: Monitor (1 minute)

Watch the console output:
```
Bot started.
Contacting server...
Logged in with user YOUR_USERNAME
Connected to OGame server
Searching inactive planets...
Found 45 inactive planets in 21 systems
Entering attack mode
Attacking [1:234:5] from [1:240:3] with 50 smallCargo
...
```

Check logs:
```bash
tail -f files/log/ogbot.log
```

## Done! 🎉

Your bot is now running. It will:
1. Scan for inactive planets
2. Send espionage probes
3. Attack profitable targets
4. Repeat continuously

## Common Issues

### "Leiningen not found"
```bash
# Make sure lein is in PATH
export PATH="$HOME/bin:$PATH"  # Add to ~/.bashrc
```

### "Invalid username/password"
- Double-check config.ini
- Try logging in manually to verify credentials

### "Module javafx.controls not found"
- This is expected - GUI mode is not yet implemented
- Use `--no-gui` flag

### "Connection refused"
- Check your internet connection
- Verify OGame server is accessible
- Check if proxy is needed (add to config.ini)

## Next Steps

1. **Monitor First Run**: Watch for 10-15 minutes
2. **Check Results**: Log into OGame and verify attacks
3. **Adjust Settings**: Tune attackRadius, rentabilityFormula
4. **Set Up Automation**: Use cron/systemd to run continuously

## Advanced Usage

### REPL Development
```bash
lein repl
```

```clojure
(require '[ogbot.bot :as bot])
(require '[ogbot.config :as config])

;; Load config
(def cfg (config/load-bot-configuration "files/config/config.ini"))

;; Create bot state
(def state (bot/create-bot-state "files/config/config.ini"
                                 (bot/->ConsoleEventManager)))

;; Manually scan galaxies
(def updated-state (bot/scan-galaxies state))

;; Check inactive planets
(count (:inactive-planets updated-state))
```

### Build Standalone
```bash
lein uberjar
java -jar target/uberjar/ogbot-3.1.0-SNAPSHOT-standalone.jar --no-gui
```

### Run as Service (Linux)
```bash
# Create systemd service
sudo nano /etc/systemd/system/ogbot.service
```

```ini
[Unit]
Description=OGBot Clojure
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/kovans-ogbot
ExecStart=/usr/bin/java -jar target/uberjar/ogbot-3.1.0-SNAPSHOT-standalone.jar --no-gui
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable ogbot
sudo systemctl start ogbot
sudo journalctl -u ogbot -f  # View logs
```

## Configuration Tips

### Increase Attack Range
```ini
attackRadius = 20  # Default: 10
```

### Use Multiple Source Planets
```ini
sourcePlanets = [1:240:3], [1:250:7]
```

### Adjust Rentability Formula
```ini
# More weight on deuterium
rentabilityFormula = (metal + 2 * crystal + 4 * deuterium) / flightTime

# Only metal and crystal
rentabilityFormula = (metal + 1.5 * crystal) / flightTime
```

### Avoid Players/Alliances
```ini
playersToAvoid = BadPlayer1, BadPlayer2
alliancesToAvoid = StrongAlliance
```

## Safety Tips

1. **Start Small**: Use attackRadius=5 for first run
2. **Monitor Closely**: Watch first hour of operation
3. **Use Dedicated Account**: Don't risk your main account
4. **Check OGame Rules**: Bot usage may violate ToS
5. **Backup Config**: Keep config.ini backed up

## Performance Tuning

### Reduce Memory Usage
```bash
# In run-bot.sh or run-bot.bat, change:
lein run --no-gui  # Uses default 512MB

# To:
export JVM_OPTS="-Xmx256m"
lein run --no-gui
```

### Faster Startup
```bash
# Use uberjar for faster startup
lein uberjar
java -jar target/uberjar/ogbot-*-standalone.jar --no-gui
```

## Getting Help

- **Logs**: `files/log/ogbot.log`
- **Debug HTML**: Check `debug/` folder for captured pages
- **Config**: Review `files/config/config.ini`
- **Database**: `files/botdata/planets.db` (SQLite)

## Success Indicators

✅ Bot logs show "Bot started"
✅ Bot logs show "Connected to OGame server"
✅ Bot logs show "Found X inactive planets"
✅ Bot logs show "Attacking [X:Y:Z]"
✅ OGame shows fleet missions in progress

## Stop the Bot

- Press `Ctrl+C` in console
- Or send SIGTERM to process
- Bot saves state automatically on shutdown

---

**Happy Botting!** 🚀

For more details, see:
- README-CLOJURE.md (comprehensive guide)
- TRANSLATION-SUMMARY.md (translation details)
- Original README (Python version reference)
