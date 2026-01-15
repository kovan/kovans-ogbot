(ns ogbot.webui
  "Web-based GUI for OGBot using Ring + Hiccup"
  (:require [ring.adapter.jetty :as jetty]
            [ring.middleware.params :refer [wrap-params]]
            [ring.middleware.keyword-params :refer [wrap-keyword-params]]
            [ring.util.response :as response]
            [compojure.core :refer [defroutes GET POST]]
            [compojure.route :as route]
            [hiccup.page :as page]
            [hiccup.form :as form]
            [cheshire.core :as json]
            [clojure.core.async :as async]
            [clj-time.core :as t]
            [clj-time.format :as f]
            [ogbot.bot :as bot]
            [ogbot.config :as config]))

;; ============================================================================
;; Application State
;; ============================================================================

(defonce app-state
  (atom {:bot-state nil
         :bot-thread nil
         :status "stopped"
         :activity-log []
         :rentabilities []
         :planets []
         :event-channels []}))

(defn add-log [msg]
  (swap! app-state update :activity-log
         #(take-last 100 (conj % {:time (t/now) :msg msg}))))

(defn add-event-channel [ch]
  (swap! app-state update :event-channels conj ch))

(defn remove-event-channel [ch]
  (swap! app-state update :event-channels
         #(remove #{ch} %)))

(defn broadcast-event [event]
  (doseq [ch (:event-channels @app-state)]
    (async/put! ch event)))

;; ============================================================================
;; Bot Event Manager (implements bot/EventManager)
;; ============================================================================

(defrecord WebEventManager []
  bot/EventManager
  (log-activity [_ msg]
    (add-log msg)
    (broadcast-event {:type :log :msg msg}))
  (log-status [_ msg]
    (swap! app-state assoc :status msg)
    (broadcast-event {:type :status :status msg}))
  (fatal-exception [_ exception]
    (add-log (str "FATAL: " (.getMessage exception)))
    (broadcast-event {:type :error :msg (.getMessage exception)}))
  (connected [_]
    (add-log "Connected to OGame server")
    (broadcast-event {:type :connected}))
  (simulations-update [_ rentabilities]
    (swap! app-state assoc :rentabilities rentabilities)
    (broadcast-event {:type :rentabilities :count (count rentabilities)})))

;; ============================================================================
;; Bot Control
;; ============================================================================

(defn start-bot! []
  (when-not (:bot-thread @app-state)
    (let [event-mgr (->WebEventManager)
          bot-state (bot/create-bot-state "files/config/config.ini" event-mgr)
          bot-thread (Thread. #(bot/start! bot-state))]
      (.start bot-thread)
      (swap! app-state assoc
             :bot-state bot-state
             :bot-thread bot-thread
             :status "running")
      (add-log "Bot started"))))

(defn stop-bot! []
  (when-let [bot-state (:bot-state @app-state)]
    (bot/stop! bot-state)
    (swap! app-state assoc
           :bot-thread nil
           :bot-state nil
           :status "stopped")
    (add-log "Bot stopped")))

(defn pause-bot! []
  (when-let [bot-state (:bot-state @app-state)]
    (reset! (:paused? bot-state) true)
    (swap! app-state assoc :status "paused")
    (add-log "Bot paused")))

(defn resume-bot! []
  (when-let [bot-state (:bot-state @app-state)]
    (reset! (:paused? bot-state) false)
    (swap! app-state assoc :status "running")
    (add-log "Bot resumed")))

;; ============================================================================
;; HTML Views
;; ============================================================================

(defn head []
  [:head
   [:meta {:charset "UTF-8"}]
   [:meta {:name "viewport" :content "width=device-width, initial-scale=1.0"}]
   [:title "OGBot - Web Interface"]
   [:style "
body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #1a1a2e; color: #eee; }
.container { max-width: 1400px; margin: 0 auto; }
h1 { color: #0f3460; background: #16213e; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
.controls { background: #16213e; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
.controls button {
  padding: 10px 20px; margin-right: 10px; font-size: 16px; cursor: pointer;
  border: none; border-radius: 5px; color: white; font-weight: bold;
}
.btn-start { background: #28a745; }
.btn-start:hover { background: #218838; }
.btn-stop { background: #dc3545; }
.btn-stop:hover { background: #c82333; }
.btn-pause { background: #ffc107; color: #000; }
.btn-pause:hover { background: #e0a800; }
.status {
  display: inline-block; padding: 10px 20px; border-radius: 5px;
  font-weight: bold; margin-left: 20px;
}
.status.running { background: #28a745; }
.status.stopped { background: #dc3545; }
.status.paused { background: #ffc107; color: #000; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.panel { background: #16213e; padding: 20px; border-radius: 8px; }
.panel h2 { margin-top: 0; color: #0f3460; border-bottom: 2px solid #0f3460; padding-bottom: 10px; }
.log {
  height: 400px; overflow-y: auto; font-family: monospace; font-size: 12px;
  background: #0f0f0f; padding: 10px; border-radius: 5px;
}
.log-entry { padding: 5px 0; border-bottom: 1px solid #333; }
.log-time { color: #888; margin-right: 10px; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 10px; text-align: left; border-bottom: 1px solid #333; }
th { background: #0f3460; font-weight: bold; }
tr:hover { background: #1a1a2e; }
.rentability { font-weight: bold; }
.rentability.positive { color: #28a745; }
.rentability.negative { color: #dc3545; }
#auto-scroll { margin: 10px 0; }
"]])

(defn controls-panel [status]
  [:div.controls
   [:button.btn-start {:onclick "startBot()"} "▶ Start"]
   [:button.btn-stop {:onclick "stopBot()"} "⏹ Stop"]
   [:button.btn-pause {:onclick "pauseBot()"} "⏸ Pause"]
   [:button.btn-pause {:onclick "resumeBot()"} "▶▶ Resume"]
   [:span.status {:class status} (clojure.string/upper-case status)]])

(defn activity-log-panel [logs]
  [:div.panel
   [:h2 "📋 Activity Log"]
   [:label [:input#auto-scroll {:type "checkbox" :checked true}] " Auto-scroll"]
   [:div {:class "log" :id "activity-log"}
    (doall
     (for [{:keys [time msg]} (take-last 50 logs)]
       [:div.log-entry
        [:span.log-time (f/unparse (f/formatter "HH:mm:ss") time)]
        [:span msg]]))]])

(defn rentabilities-panel [rentabilities]
  [:div.panel
   [:h2 "🎯 Targets (" (count rentabilities) ")"]
   [:table
    [:thead
     [:tr
      [:th "Source"]
      [:th "Target"]
      [:th "Player"]
      [:th "Rentability"]]]
    [:tbody
     (doall
      (for [rent (take 20 rentabilities)]
        [:tr
         [:td (str (get-in rent [:source-planet :coords]))]
         [:td (str (get-in rent [:target-planet :coords]))]
         [:td (get-in rent [:target-planet :owner :name])]
         [:td [:span.rentability
               {:class (if (pos? (:rentability rent)) "positive" "negative")}
               (format "%.2f" (:rentability rent))]]]))]]])

(defn stats-panel [state]
  [:div.panel
   [:h2 "📊 Statistics"]
   [:p "Status: " [:strong.stats-status (:status state)]]
   [:p "Inactive Planets: " [:strong.stats-planets (count (:planets state))]]
   [:p "Targets: " [:strong.stats-targets (count (:rentabilities state))]]
   [:p "Log Entries: " [:strong.stats-logs (count (:activity-log state))]]])

(defn javascript []
  [:script "
let lastLogCount = 0;
let currentStatus = '';

function startBot() {
  fetch('/api/start', {method: 'POST'})
    .then(r => r.json())
    .then(data => {
      console.log('Bot started', data);
      updateStatusDisplay('running');
    });
}
function stopBot() {
  fetch('/api/stop', {method: 'POST'})
    .then(r => r.json())
    .then(data => {
      console.log('Bot stopped', data);
      updateStatusDisplay('stopped');
    });
}
function pauseBot() {
  fetch('/api/pause', {method: 'POST'})
    .then(r => r.json())
    .then(data => {
      console.log('Bot paused', data);
      updateStatusDisplay('paused');
    });
}
function resumeBot() {
  fetch('/api/resume', {method: 'POST'})
    .then(r => r.json())
    .then(data => {
      console.log('Bot resumed', data);
      updateStatusDisplay('running');
    });
}

function updateStatusDisplay(status) {
  const statusEl = document.querySelector('.status');
  statusEl.className = 'status ' + status;
  statusEl.textContent = status.toUpperCase();
  currentStatus = status;
}

function addLogEntry(time, msg) {
  const log = document.getElementById('activity-log');
  const entry = document.createElement('div');
  entry.className = 'log-entry';
  entry.innerHTML = '<span class=\"log-time\">' + time + '</span><span>' + msg + '</span>';
  log.appendChild(entry);

  if (document.getElementById('auto-scroll').checked) {
    log.scrollTop = log.scrollHeight;
  }
}

function pollUpdates() {
  fetch('/api/updates')
    .then(r => r.json())
    .then(data => {
      // Update status if changed
      if (data.status !== currentStatus) {
        updateStatusDisplay(data.status);
      }

      // Add new log entries
      const log = document.getElementById('activity-log');
      if (data.logs && data.logs.length > 0) {
        // Clear and rebuild log to avoid duplicates
        const existingCount = log.children.length;
        if (data.logs.length !== existingCount) {
          log.innerHTML = '';
          data.logs.forEach(entry => {
            addLogEntry(entry.time, entry.msg);
          });
        }
      }

      // Update stats
      document.querySelector('.stats-targets').textContent = data.rentabilities_count || 0;
      document.querySelector('.stats-planets').textContent = data.planets_count || 0;
    })
    .catch(err => console.error('Poll error:', err));
}

// Poll every 2 seconds
setInterval(pollUpdates, 2000);

// Initial poll
pollUpdates();
"])

(defn main-page []
  (let [state @app-state]
    (page/html5
     (head)
     [:body
      [:div.container
       [:h1 "🚀 Kovan's OGBot - Web Interface"]
       (controls-panel (:status state))
       [:div.grid
        (activity-log-panel (:activity-log state))
        (stats-panel state)]
       (rentabilities-panel (:rentabilities state))]
      (javascript)])))

;; ============================================================================
;; API Routes
;; ============================================================================

(defn api-start [req]
  (start-bot!)
  {:status 200
   :headers {"Content-Type" "application/json"}
   :body (json/generate-string {:success true :status "started"})})

(defn api-stop [req]
  (stop-bot!)
  {:status 200
   :headers {"Content-Type" "application/json"}
   :body (json/generate-string {:success true :status "stopped"})})

(defn api-pause [req]
  (pause-bot!)
  {:status 200
   :headers {"Content-Type" "application/json"}
   :body (json/generate-string {:success true :status "paused"})})

(defn api-resume [req]
  (resume-bot!)
  {:status 200
   :headers {"Content-Type" "application/json"}
   :body (json/generate-string {:success true :status "resumed"})})

(defn api-status [req]
  {:status 200
   :headers {"Content-Type" "application/json"}
   :body (json/generate-string @app-state)})

(defn api-rentabilities [req]
  {:status 200
   :headers {"Content-Type" "application/json"}
   :body (json/generate-string {:rentabilities (:rentabilities @app-state)})})

;; Polling endpoint for logs and status updates
(defn api-updates [req]
  (let [state @app-state
        logs (take-last 20 (:activity-log state))]
    {:status 200
     :headers {"Content-Type" "application/json"}
     :body (json/generate-string
            {:status (:status state)
             :logs (mapv (fn [{:keys [time msg]}]
                          {:time (f/unparse (f/formatter "HH:mm:ss") time)
                           :msg msg})
                        logs)
             :rentabilities-count (count (:rentabilities state))
             :planets-count (count (:planets state))})}))

;; ============================================================================
;; Routes
;; ============================================================================

(defroutes app-routes
  (GET "/" [] (main-page))
  (POST "/api/start" [] api-start)
  (POST "/api/stop" [] api-stop)
  (POST "/api/pause" [] api-pause)
  (POST "/api/resume" [] api-resume)
  (GET "/api/status" [] api-status)
  (GET "/api/rentabilities" [] api-rentabilities)
  (GET "/api/updates" [] api-updates)
  (route/not-found "Not Found"))

(def app
  (-> app-routes
      wrap-keyword-params
      wrap-params))

;; ============================================================================
;; Server Management
;; ============================================================================

(defonce server (atom nil))

(defn start-server! [port]
  (when-not @server
    (println (str "Starting web UI on http://localhost:" port))
    (reset! server (jetty/run-jetty app {:port port :join? false}))
    (add-log "Web UI started")))

(defn stop-server! []
  (when @server
    (.stop @server)
    (reset! server nil)
    (println "Web UI stopped")))

(defn -main [& args]
  (let [port (Integer/parseInt (or (first args) "3000"))]
    (start-server! port)
    (println)
    (println "╔════════════════════════════════════════════════╗")
    (println "║   OGBot Web Interface                          ║")
    (println "║                                                ║")
    (println (format "║   Open http://localhost:%-5d in your browser║" port))
    (println "║                                                ║")
    (println "║   Press Ctrl+C to stop                         ║")
    (println "╚════════════════════════════════════════════════╝")))
