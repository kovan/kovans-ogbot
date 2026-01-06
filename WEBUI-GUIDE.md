# OGBot Web UI Guide

## Overview

The Clojure version of OGBot includes a **modern web-based interface** instead of the original PyQt4 desktop GUI. This provides:

- ✅ **Cross-platform** - works on any OS with a browser
- ✅ **Modern UI** - responsive, dark theme, real-time updates
- ✅ **Easy deployment** - no GUI toolkit dependencies
- ✅ **Remote access** - control bot from any device on your network
- ✅ **Real-time updates** - see activity as it happens

## Starting the Web UI

### Default Port (3000)
```bash
# With GUI mode (opens web UI)
lein run

# Or directly
lein run -m ogbot.webui
```

### Custom Port
```bash
lein run -m ogbot.webui 8080
```

Then open **http://localhost:3000** (or your custom port) in your browser.

## Features

### 1. **Bot Controls**
- **Start** - Begin bot operation
- **Stop** - Gracefully stop the bot
- **Pause** - Temporarily pause operation
- **Resume** - Resume from pause

### 2. **Activity Log**
- Real-time logging of all bot activities
- Auto-scroll option
- Shows timestamps
- Last 100 entries displayed

### 3. **Target List**
- Shows all potential targets sorted by rentability
- Displays source planet, target coords, player name
- Color-coded rentability (green = profitable, red = not)
- Updates every 10 seconds when bot is running

### 4. **Statistics Panel**
- Current bot status
- Number of inactive planets found
- Number of active targets
- Log entry count

## Web UI Architecture

```
Browser (JavaScript)
       ↕ HTTP/SSE
Ring Web Server (Clojure)
       ↕
Bot Core Logic
       ↕
OGame Servers
```

### Technologies Used
- **Ring** - HTTP server
- **Compojure** - Routing
- **Hiccup** - HTML generation
- **Server-Sent Events** - Real-time push updates
- **Vanilla JavaScript** - No heavy frameworks

## API Endpoints

### Control Endpoints
- `POST /api/start` - Start the bot
- `POST /api/stop` - Stop the bot
- `POST /api/pause` - Pause operation
- `POST /api/resume` - Resume from pause

### Data Endpoints
- `GET /api/status` - Get current bot status
- `GET /api/rentabilities` - Get target list
- `GET /api/events` - Server-Sent Events stream (real-time updates)

## Real-Time Updates

The web UI uses **Server-Sent Events (SSE)** for real-time updates:

```javascript
// Browser automatically connects
const eventSource = new EventSource('/api/events');
eventSource.onmessage = function(e) {
  const data = JSON.parse(e.data);
  // Handle: log, status, rentabilities, error events
};
```

## Customization

### Styling
Edit the CSS in `webui.clj` under the `:style` tag. The UI uses a dark theme by default.

### Port Configuration
```clojure
;; In your REPL
(require '[ogbot.webui :as webui])
(webui/start-server! 8080)
```

### Adding Features
The web UI is modular. To add a new feature:

1. Add data to `app-state` atom
2. Create a Hiccup view function
3. Add API endpoint if needed
4. Update JavaScript for interactivity

Example:
```clojure
;; Add to webui.clj
(defn my-panel []
  [:div.panel
   [:h2 "My Custom Panel"]
   [:p "Content here..."]])

;; Add to main-page
(my-panel)
```

## Remote Access

To allow remote access:

```bash
# Make sure firewall allows the port
sudo ufw allow 3000

# Start the server
lein run
```

Then access from any device on your network:
```
http://YOUR_IP_ADDRESS:3000
```

⚠️ **Security Warning**: The web UI has no authentication. Only use on trusted networks or add authentication middleware.

## Production Deployment

### As a Service
```bash
# Build uberjar
lein uberjar

# Run as service (systemd example)
[Unit]
Description=OGBot Web UI
After=network.target

[Service]
Type=simple
User=ogbot
WorkingDirectory=/opt/ogbot
ExecStart=/usr/bin/java -jar ogbot-standalone.jar
Restart=always

[Install]
WantedBy=multi-user.target
```

### Behind Nginx
```nginx
server {
    listen 80;
    server_name ogbot.example.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

### With Authentication
Add Ring middleware:
```clojure
(require '[ring.middleware.basic-authentication :refer [wrap-basic-authentication]])

(defn authenticated? [username password]
  (and (= username "admin")
       (= password "secret")))

(def app
  (-> app-routes
      (wrap-basic-authentication authenticated?)
      wrap-keyword-params
      wrap-params))
```

## Troubleshooting

### Port Already in Use
```bash
# Find process using port 3000
lsof -i :3000

# Kill it or use different port
lein run -m ogbot.webui 3001
```

### Can't Connect from Remote Device
- Check firewall settings
- Verify server is listening on 0.0.0.0 (not just 127.0.0.1)
- Ensure you're using the correct IP address

### Events Not Updating
- Check browser console for errors
- Verify SSE connection is open (Network tab in dev tools)
- Refresh the page

### High Memory Usage
The web UI is lightweight, but if bot is scanning many planets:
```bash
# Reduce JVM heap
export JVM_OPTS="-Xmx256m"
lein run
```

## Advantages Over Desktop GUI

| Feature | Desktop (PyQt4) | Web UI |
|---------|----------------|--------|
| Install dependencies | Complex | None (just browser) |
| Cross-platform | Requires Qt libs | Works everywhere |
| Remote access | No | Yes |
| Mobile access | No | Yes |
| Real-time updates | Polling | SSE (push) |
| Customization | Requires Qt knowledge | HTML/CSS |
| Deployment | Needs X server | Headless OK |

## Future Enhancements

Possible additions:
- [ ] WebSocket support for bi-directional communication
- [ ] Configuration editor in UI
- [ ] Planet database browser
- [ ] Espionage report viewer
- [ ] Attack scheduler
- [ ] Statistics graphs (Chart.js)
- [ ] Authentication & user management
- [ ] Mobile-optimized layout
- [ ] Dark/Light theme toggle
- [ ] Export data to CSV/JSON

## Comparison to Original GUI

### Original (PyQt4)
- 3 tabs: Bot Activity, Planet Database, Options
- Tree views for planets and reports
- Modal dialogs for configuration
- Context menus for manual actions

### Web UI (Current)
- Single-page interface
- Real-time activity log
- Target list with rentability
- Statistics dashboard
- RESTful API for all actions

### Missing Features (TODO)
- Planet database browser with search
- Espionage report detail viewer
- Full configuration editor
- Manual spy/attack buttons for specific planets
- About/version info dialog

These can be added incrementally as panels to the web UI.

## Contributing

To improve the web UI:

1. Edit `src/clj/ogbot/webui.clj`
2. Restart server (`lein run`)
3. Refresh browser
4. Test functionality
5. Submit improvements

The UI is intentionally simple and uses minimal JavaScript to keep it maintainable.

---

**Enjoy your web-based OGame bot!** 🚀
