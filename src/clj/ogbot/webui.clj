(ns ogbot.webui
  "Web-based GUI for OGBot using Ring + Hiccup + ClojureScript"
  (:require [ring.adapter.jetty :as jetty]
            [ring.middleware.params :refer [wrap-params]]
            [ring.middleware.keyword-params :refer [wrap-keyword-params]]
            [ring.middleware.resource :refer [wrap-resource]]
            [ring.middleware.content-type :refer [wrap-content-type]]
            [ring.util.response :as response]
            [compojure.core :refer [defroutes GET POST]]
            [compojure.route :as route]
            [hiccup.page :as page]
            [cheshire.core :as json]
            [clojure.core.async :as async]
            [clojure.string :as str]
            [clj-time.core :as t]
            [clj-time.format :as f]
            [ogbot.bot :as bot]
            [ogbot.config :as config]
            [ogbot.db :as db]
            [ogbot.constants :as constants]
            [ogbot.web-selenium :as web])
  (:import [java.awt Desktop Desktop$Action]
           [java.net URI]))

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
         :event-channels []
         ;; Planet database state
         :db-planets []
         :selected-planet nil
         :selected-report nil
         :filter-column "coords"
         :filter-text ""}))

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
          bot-thread (Thread.
                      (fn []
                        (try
                          (bot/start! bot-state)
                          (catch Exception e
                            (add-log (str "Bot error: " (.getMessage e)))
                            (swap! app-state assoc :status "error")))))]
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
;; HTML Index Page (loads ClojureScript app)
;; ============================================================================

(defn index-page []
  (page/html5
   [:head
    [:meta {:charset "UTF-8"}]
    [:meta {:name "viewport" :content "width=device-width, initial-scale=1.0"}]
    [:title "OGBot - Web Interface"]
    [:link {:rel "stylesheet" :href "/css/style.css"}]]
   [:body
    [:div#app
     [:div.container
      [:h1 "Loading OGBot..."]
      [:p {:style "color: #888;"} "If this message persists, make sure ClojureScript is compiled."]
      [:p {:style "color: #666;"} "Run: npx shadow-cljs watch app"]]]
    [:script {:src "/js/main.js"}]]))

;; ============================================================================
;; Helper functions for API responses
;; ============================================================================

(defn- get-defense-status [report]
  (cond
    (nil? (:defense report)) "?"
    (empty? (:defense report)) "No"
    (every? #(#{"antiBallisticMissile" "interplanetaryMissile"} (first %))
            (:defense report)) "Missiles only"
    :else "Yes"))

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
             :planets-count (count (:planets state))
             :db-planets-count (count (:db-planets state))})}))

;; ============================================================================
;; Planet Database API
;; ============================================================================

(defn get-planet-db-spec []
  (db/create-db-spec (get constants/file-paths :planetdb)))

(defn api-get-planets [req]
  (try
    (let [db-spec (get-planet-db-spec)
          _ (db/init-planet-db! db-spec)
          planets (db/read-all-planets db-spec)
          planet-data (mapv (fn [p]
                             {:coords (str (:coords p))
                              :name (:name p)
                              :owner_name (get-in p [:owner :name])
                              :owner_alliance (get-in p [:owner :alliance])
                              :owner_is_inactive (get-in p [:owner :is-inactive])
                              :report_count (count (:espionage-history p))})
                           planets)]
      (swap! app-state assoc :db-planets planets)
      {:status 200
       :headers {"Content-Type" "application/json"}
       :body (json/generate-string {:planets planet-data})})
    (catch Exception e
      {:status 500
       :headers {"Content-Type" "application/json"}
       :body (json/generate-string {:error (.getMessage e)})})))

(defn api-search-planets [req]
  (try
    (let [params (:params req)
          column (get params "column" "coords")
          text (str/lower-case (get params "text" ""))
          db-spec (get-planet-db-spec)
          planets (db/read-all-planets db-spec)
          filtered (if (str/blank? text)
                     planets
                     (filter (fn [p]
                              (let [value (case column
                                           "coords" (str (:coords p))
                                           "name" (or (:name p) "")
                                           "owner" (get-in p [:owner :name] "")
                                           "alliance" (get-in p [:owner :alliance] "")
                                           "inactive" (if (get-in p [:owner :is-inactive]) "yes" "no")
                                           (str (:coords p)))]
                                (str/includes? (str/lower-case value) text)))
                            planets))
          planet-data (mapv (fn [p]
                             {:coords (str (:coords p))
                              :name (:name p)
                              :owner_name (get-in p [:owner :name])
                              :owner_alliance (get-in p [:owner :alliance])
                              :owner_is_inactive (get-in p [:owner :is-inactive])
                              :report_count (count (:espionage-history p))})
                           filtered)]
      {:status 200
       :headers {"Content-Type" "application/json"}
       :body (json/generate-string {:planets planet-data})})
    (catch Exception e
      {:status 500
       :headers {"Content-Type" "application/json"}
       :body (json/generate-string {:error (.getMessage e)})})))

(defn- format-report-for-json [report]
  {:code (or (:code report) "")
   :date (when-let [date (:date report)]
           (try (f/unparse (f/formatter "HH:mm:ss MM-dd") date)
                (catch Exception _ "")))
   :coords (str (:coords report))
   :metal (get-in report [:resources :metal] 0)
   :crystal (get-in report [:resources :crystal] 0)
   :deuterium (get-in report [:resources :deuterium] 0)
   :fleet_status (cond
                   (nil? (:fleet report)) "Unknown"
                   (empty? (:fleet report)) "No"
                   :else "Yes")
   :defense_status (get-defense-status report)
   :probes_sent (:probes-sent report)
   :fleet (or (:fleet report) {})
   :defense (or (:defense report) {})
   :buildings (or (:buildings report) {})
   :research (or (:research report) {})})

(defn api-get-planet-reports [req]
  (try
    (let [coords-str (get-in req [:params :coords])
          db-spec (get-planet-db-spec)
          planet (db/read-planet db-spec coords-str)
          reports (or (:espionage-history planet) [])
          report-data (mapv format-report-for-json reports)]
      (swap! app-state assoc :selected-planet planet)
      {:status 200
       :headers {"Content-Type" "application/json"}
       :body (json/generate-string {:reports report-data})})
    (catch Exception e
      {:status 500
       :headers {"Content-Type" "application/json"}
       :body (json/generate-string {:error (.getMessage e)})})))

(defn api-get-report-details [req]
  (try
    (let [coords-str (get-in req [:params :coords])
          code-str (get-in req [:params :code])
          db-spec (get-planet-db-spec)
          planet (db/read-planet db-spec coords-str)
          reports (or (:espionage-history planet) [])
          report (first (filter #(= (str (:code %)) code-str) reports))]
      (swap! app-state assoc :selected-report report)
      {:status 200
       :headers {"Content-Type" "application/json"}
       :body (json/generate-string {:report (when report (format-report-for-json report))})})
    (catch Exception e
      {:status 500
       :headers {"Content-Type" "application/json"}
       :body (json/generate-string {:error (.getMessage e)})})))

(defn api-get-all-reports [req]
  (try
    (let [db-spec (get-planet-db-spec)
          planets (db/read-all-planets db-spec)
          all-reports (->> planets
                          (mapcat :espionage-history)
                          (filter some?)
                          (sort-by :date)
                          reverse
                          (take 100)
                          (mapv format-report-for-json))]
      {:status 200
       :headers {"Content-Type" "application/json"}
       :body (json/generate-string {:reports all-reports})})
    (catch Exception e
      {:status 500
       :headers {"Content-Type" "application/json"}
       :body (json/generate-string {:error (.getMessage e)})})))

;; ============================================================================
;; Action API
;; ============================================================================

(defn api-spy [req]
  (try
    (let [body (json/parse-string (slurp (:body req)) true)
          coords-str (:coords body)]
      (add-log (str "Spy command sent for " coords-str))
      (when-let [bot-state (:bot-state @app-state)]
        ;; Queue spy command
        (async/put! (:msg-queue bot-state) {:type :spy :coords coords-str}))
      {:status 200
       :headers {"Content-Type" "application/json"}
       :body (json/generate-string {:success true :coords coords-str})})
    (catch Exception e
      {:status 500
       :headers {"Content-Type" "application/json"}
       :body (json/generate-string {:error (.getMessage e)})})))

(defn api-attack [req]
  (try
    (let [body (json/parse-string (slurp (:body req)) true)
          coords-str (:coords body)
          ship-type (:ship body)]
      (add-log (str "Attack command sent for " coords-str " with " ship-type))
      (when-let [bot-state (:bot-state @app-state)]
        ;; Queue attack command
        (async/put! (:msg-queue bot-state) {:type :attack :coords coords-str :ship ship-type}))
      {:status 200
       :headers {"Content-Type" "application/json"}
       :body (json/generate-string {:success true :coords coords-str :ship ship-type})})
    (catch Exception e
      {:status 500
       :headers {"Content-Type" "application/json"}
       :body (json/generate-string {:error (.getMessage e)})})))

;; ============================================================================
;; Manual Scan API
;; ============================================================================

(defn api-manual-scan [req]
  (try
    (let [body (json/parse-string (slurp (:body req)) true)
          galaxy (or (:galaxy body) 1)
          system (or (:system body) 1)]
      (add-log (str "Manual scan requested for " galaxy ":" system))
      (if-let [bot-state (:bot-state @app-state)]
        (if-let [web-adapter (:web-adapter bot-state)]
          (let [planets (web/scan-solar-system web-adapter galaxy system)
                db-spec (get-planet-db-spec)]
            (db/init-planet-db! db-spec)
            (db/write-many-planets! db-spec planets)
            (add-log (str "Scanned " (count planets) " planets in " galaxy ":" system))
            {:status 200
             :headers {"Content-Type" "application/json"}
             :body (json/generate-string {:success true :planets-found (count planets)})})
          {:status 400
           :headers {"Content-Type" "application/json"}
           :body (json/generate-string {:error "Bot not connected - start the bot first"})})
        {:status 400
         :headers {"Content-Type" "application/json"}
         :body (json/generate-string {:error "Bot not running - start the bot first"})}))
    (catch Exception e
      (add-log (str "Scan error: " (.getMessage e)))
      {:status 500
       :headers {"Content-Type" "application/json"}
       :body (json/generate-string {:error (.getMessage e)})})))

;; ============================================================================
;; Routes
;; ============================================================================

(defroutes app-routes
  (GET "/" [] (index-page))
  ;; Bot control
  (POST "/api/start" [] api-start)
  (POST "/api/stop" [] api-stop)
  (POST "/api/pause" [] api-pause)
  (POST "/api/resume" [] api-resume)
  (GET "/api/status" [] api-status)
  (GET "/api/rentabilities" [] api-rentabilities)
  (GET "/api/updates" [] api-updates)
  ;; Planet database
  (GET "/api/planets" [] api-get-planets)
  (GET "/api/planets/search" [] api-search-planets)
  (GET "/api/planets/all-reports" [] api-get-all-reports)
  (GET "/api/planets/:coords/reports" [coords] (fn [req] (api-get-planet-reports (assoc-in req [:params :coords] coords))))
  (GET "/api/planets/:coords/reports/:code" [coords code] (fn [req] (api-get-report-details (-> req (assoc-in [:params :coords] coords) (assoc-in [:params :code] code)))))
  ;; Actions
  (POST "/api/action/spy" [] api-spy)
  (POST "/api/action/attack" [] api-attack)
  (POST "/api/action/scan" [] api-manual-scan)
  (route/not-found "Not Found"))

(def app
  (-> app-routes
      wrap-keyword-params
      wrap-params
      (wrap-resource "public")
      wrap-content-type))

;; ============================================================================
;; Server Management
;; ============================================================================

(defonce server (atom nil))

(defn- open-browser! [url]
  (try
    (when (Desktop/isDesktopSupported)
      (let [desktop (Desktop/getDesktop)]
        (when (.isSupported desktop Desktop$Action/BROWSE)
          (.browse desktop (URI. url))
          true)))
    (catch Exception e
      (println "Could not open browser automatically:" (.getMessage e))
      false)))

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
  (let [port (Integer/parseInt (or (first args) "3000"))
        url (str "http://localhost:" port)]
    (start-server! port)
    (println)
    (println "╔════════════════════════════════════════════════╗")
    (println "║   OGBot Web Interface                          ║")
    (println "║                                                ║")
    (println (format "║   Open http://localhost:%-5d in your browser║" port))
    (println "║                                                ║")
    (println "║   Press Ctrl+C to stop                         ║")
    (println "╚════════════════════════════════════════════════╝")
    (when (open-browser! url)
      (println "\nBrowser opened automatically."))))
