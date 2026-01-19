(ns ogbot.webui.state
  (:require [reagent.core :as r]))

;; ============================================================================
;; Application State
;; ============================================================================

(defonce active-tab (r/atom :activity))
(defonce bot-status (r/atom "stopped"))
(defonce activity-log (r/atom []))
(defonce rentabilities (r/atom []))
(defonce stats (r/atom {:planets 0 :targets 0 :logs 0 :db-planets 0}))

;; Planet Database State
(defonce db-planets (r/atom []))
(defonce selected-planet (r/atom nil))
(defonce planet-reports (r/atom []))
(defonce selected-report (r/atom nil))
(defonce filter-column (r/atom "coords"))
(defonce filter-text (r/atom ""))

;; Auto-scroll
(defonce auto-scroll? (r/atom true))

;; ============================================================================
;; API Calls (using native fetch)
;; ============================================================================

(defn- parse-json [response]
  (.json response))

(defn- handle-response [on-success]
  (fn [data]
    (when on-success
      (on-success (js->clj data :keywordize-keys true)))))

(defn- handle-error [on-error]
  (fn [error]
    (js/console.error "API Error:" error)
    (when on-error (on-error error))))

(defn api-get [url & {:keys [on-success on-error]}]
  (-> (js/fetch url)
      (.then parse-json)
      (.then (handle-response on-success))
      (.catch (handle-error on-error))))

(defn api-post [url & {:keys [params on-success on-error]}]
  (-> (js/fetch url #js {:method "POST"
                         :headers #js {"Content-Type" "application/json"}
                         :body (js/JSON.stringify (clj->js params))})
      (.then parse-json)
      (.then (handle-response on-success))
      (.catch (handle-error on-error))))

;; ============================================================================
;; Bot Control
;; ============================================================================

(defn start-bot! []
  (js/console.log "start-bot! called")
  (api-post "/api/start"
            :on-success (fn [_]
                          (js/console.log "start-bot! success")
                          (reset! bot-status "running"))
            :on-error (fn [e] (js/console.error "start-bot! error:" e))))

(defn stop-bot! []
  (js/console.log "stop-bot! called")
  (api-post "/api/stop"
            :on-success (fn [_]
                          (js/console.log "stop-bot! success")
                          (reset! bot-status "stopped"))
            :on-error (fn [e] (js/console.error "stop-bot! error:" e))))

(defn pause-bot! []
  (js/console.log "pause-bot! called")
  (api-post "/api/pause"
            :on-success (fn [_]
                          (js/console.log "pause-bot! success")
                          (reset! bot-status "paused"))
            :on-error (fn [e] (js/console.error "pause-bot! error:" e))))

(defn resume-bot! []
  (js/console.log "resume-bot! called")
  (api-post "/api/resume"
            :on-success (fn [_]
                          (js/console.log "resume-bot! success")
                          (reset! bot-status "running"))
            :on-error (fn [e] (js/console.error "resume-bot! error:" e))))

;; ============================================================================
;; Polling
;; ============================================================================

(defn poll-updates! []
  (api-get "/api/updates"
           :on-success (fn [data]
                         (reset! bot-status (:status data))
                         (reset! activity-log (or (:logs data) []))
                         (swap! stats assoc
                                :targets (or (:rentabilities-count data) 0)
                                :planets (or (:planets-count data) 0)
                                :db-planets (or (:db-planets-count data) 0)
                                :logs (count (or (:logs data) []))))))

(defn fetch-rentabilities! []
  (api-get "/api/rentabilities"
           :on-success (fn [data]
                         (reset! rentabilities (or (:rentabilities data) [])))))

(defonce poll-interval (atom nil))

(defn start-polling! []
  (when @poll-interval
    (js/clearInterval @poll-interval))
  (poll-updates!)
  (fetch-rentabilities!)
  (reset! poll-interval (js/setInterval
                         (fn []
                           (poll-updates!)
                           (fetch-rentabilities!))
                         2000)))

;; ============================================================================
;; Planet Database
;; ============================================================================

(defn load-planets! []
  (api-get "/api/planets"
           :on-success (fn [data]
                         (reset! db-planets (or (:planets data) [])))))

(defn search-planets! []
  (api-get (str "/api/planets/search?column=" (js/encodeURIComponent @filter-column)
                "&text=" (js/encodeURIComponent @filter-text))
           :on-success (fn [data]
                         (reset! db-planets (or (:planets data) [])))))

(defn select-planet! [coords]
  (reset! selected-planet coords)
  (reset! selected-report nil)
  (api-get (str "/api/planets/" (js/encodeURIComponent coords) "/reports")
           :on-success (fn [data]
                         (reset! planet-reports (or (:reports data) [])))))

(defn select-report! [code]
  (reset! selected-report nil)
  (when @selected-planet
    (api-get (str "/api/planets/" (js/encodeURIComponent @selected-planet)
                  "/reports/" (js/encodeURIComponent code))
             :on-success (fn [data]
                           (reset! selected-report (:report data))))))

(defn load-all-reports! []
  (api-get "/api/planets/all-reports"
           :on-success (fn [data]
                         (reset! planet-reports (or (:reports data) [])))))

;; ============================================================================
;; Actions
;; ============================================================================

(defn spy-planet! [coords]
  (api-post "/api/action/spy"
            :params {:coords coords}
            :on-success #(js/console.log "Spy sent to" coords)))

(defn attack-planet! [coords ship-type]
  (api-post "/api/action/attack"
            :params {:coords coords :ship ship-type}
            :on-success #(js/console.log "Attack sent to" coords "with" ship-type)))
