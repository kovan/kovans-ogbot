(ns ogbot.desktop-gui.events
  "Event handlers for the desktop GUI."
  (:require [ogbot.desktop-gui.state :as state]
            [ogbot.desktop-gui.event-manager :as em]
            [ogbot.bot :as bot]
            [ogbot.config :as config]
            [ogbot.db :as db]
            [ogbot.constants :as constants]
            [cljfx.api :as fx]
            [clojure.java.browse :as browse]))

;; ============================================================================
;; Bot Control Events
;; ============================================================================

(defn handle-start-pause-resume [{:keys [fx/context]}]
  (let [status (fx/sub-ctx context state/sub-bot-status)]
    (case status
      :stopped
      ;; Start the bot
      (let [event-mgr (em/create-event-manager)
            bot-state (bot/create-bot-state "files/config/config.ini" event-mgr)
            bot-thread (Thread. #(bot/start! bot-state))]
        (.start bot-thread)
        {:context (fx/swap-context context
                                   (fn [ctx]
                                     (-> ctx
                                         (assoc-in [:bot :state] bot-state)
                                         (assoc-in [:bot :thread] bot-thread)
                                         (assoc-in [:bot :status] :running))))})

      :running
      ;; Pause the bot
      (let [bot-state (fx/sub-ctx context state/sub-bot-state)]
        (when bot-state
          (reset! (:paused? bot-state) true))
        {:context (fx/swap-context context assoc-in [:bot :status] :paused)})

      :paused
      ;; Resume the bot
      (let [bot-state (fx/sub-ctx context state/sub-bot-state)]
        (when bot-state
          (reset! (:paused? bot-state) false))
        {:context (fx/swap-context context assoc-in [:bot :status] :running)})

      {:context context})))

(defn handle-stop-bot [{:keys [fx/context]}]
  (let [bot-state (fx/sub-ctx context state/sub-bot-state)]
    (when bot-state
      (bot/stop! bot-state))
    {:context (fx/swap-context context
                               (fn [ctx]
                                 (-> ctx
                                     (assoc-in [:bot :state] nil)
                                     (assoc-in [:bot :thread] nil)
                                     (assoc-in [:bot :status] :stopped)
                                     (assoc-in [:bot :connection-status] nil))))}))

;; ============================================================================
;; UI Events
;; ============================================================================

(defn handle-open-options [{:keys [fx/context]}]
  {:context (fx/swap-context context assoc-in [:ui :options-dialog-open?] true)})

(defn handle-close-options [{:keys [fx/context]}]
  {:context (fx/swap-context context assoc-in [:ui :options-dialog-open?] false)})

(defn handle-open-about [{:keys [fx/context]}]
  {:context (fx/swap-context context assoc-in [:ui :about-dialog-open?] true)})

(defn handle-close-about [{:keys [fx/context]}]
  {:context (fx/swap-context context assoc-in [:ui :about-dialog-open?] false)})

(defn handle-launch-browser [{:keys [fx/context]}]
  (try
    (let [session-data (slurp "files/session.edn")
          {:keys [server session]} (read-string session-data)]
      (browse/browse-url (str "http://" server "/game/index.php?session=" session)))
    (catch Exception _
      nil))
  {:context context})

(defn handle-tab-change [{:keys [fx/context fx/event]}]
  {:context (fx/swap-context context assoc-in [:ui :current-tab] (.getSelectedIndex event))})

;; ============================================================================
;; Planet Database Events
;; ============================================================================

(defn handle-set-filter-column [{:keys [fx/context fx/event]}]
  {:context (fx/swap-context context assoc-in [:planet-db :filter-column] (keyword event))})

(defn handle-set-filter-text [{:keys [fx/context fx/event]}]
  {:context (fx/swap-context context assoc-in [:planet-db :filter-text] event)})

(defn handle-reload-db [{:keys [fx/context]}]
  (try
    (let [db-spec (db/create-db-spec (get constants/file-paths :planetdb))
          planets (db/read-all-planets db-spec)]
      {:context (fx/swap-context context assoc-in [:planet-db :planets] (vec planets))})
    (catch Exception _
      {:context context})))

(defn handle-search-planets [{:keys [fx/context]}]
  ;; The filtering is done reactively via sub-filtered-planets
  {:context context})

(defn handle-planet-selected [{:keys [fx/context fx/event]}]
  (if event
    (let [planet (:value event)
          reports (or (:espionage-history planet) [])]
      {:context (fx/swap-context context
                                 (fn [ctx]
                                   (-> ctx
                                       (assoc-in [:planet-db :selected-planet] (str (:coords planet)))
                                       (assoc-in [:planet-db :reports] (vec reports)))))})
    {:context context}))

(defn handle-report-selected [{:keys [fx/context fx/event]}]
  (if event
    {:context (fx/swap-context context assoc-in [:planet-db :selected-report] (:value event))}
    {:context context}))

(defn handle-show-all-reports [{:keys [fx/context]}]
  (let [planets (fx/sub-ctx context state/sub-planets)
        all-reports (->> planets
                         (filter #(seq (:espionage-history %)))
                         (map #(last (:espionage-history %)))
                         vec)]
    {:context (fx/swap-context context assoc-in [:planet-db :reports] all-reports)}))

;; ============================================================================
;; Fleetsave Events
;; ============================================================================

(defn handle-set-fleetsave-mode [{:keys [fx/context mode]}]
  {:context (fx/swap-context context assoc-in [:fleetsave :mode] mode)})

(defn handle-toggle-fleetsave [{:keys [fx/context]}]
  {:context (fx/swap-context context update-in [:fleetsave :enabled?] not)})

;; ============================================================================
;; Context Menu Events
;; ============================================================================

(defn handle-copy-report [{:keys [fx/context]}]
  ;; TODO: Implement copy to clipboard
  {:context context})

(defn handle-attack-small-cargo [{:keys [fx/context]}]
  ;; TODO: Implement attack with small cargo
  {:context context})

(defn handle-attack-large-cargo [{:keys [fx/context]}]
  ;; TODO: Implement attack with large cargo
  {:context context})

(defn handle-spy-now [{:keys [fx/context]}]
  ;; TODO: Implement spy now
  {:context context})

;; ============================================================================
;; Options Events
;; ============================================================================

(defn handle-save-options [{:keys [fx/context]}]
  ;; TODO: Implement save options
  {:context (fx/swap-context context assoc-in [:ui :options-dialog-open?] false)})

;; ============================================================================
;; Event Map
;; ============================================================================

(def event-handler
  (-> (fn [event]
        (case (:event/type event)
          ;; Bot control
          ::start-pause-resume (handle-start-pause-resume event)
          ::stop-bot (handle-stop-bot event)

          ;; UI
          ::open-options (handle-open-options event)
          ::close-options (handle-close-options event)
          ::open-about (handle-open-about event)
          ::close-about (handle-close-about event)
          ::launch-browser (handle-launch-browser event)
          ::tab-change (handle-tab-change event)

          ;; Planet database
          ::set-filter-column (handle-set-filter-column event)
          ::set-filter-text (handle-set-filter-text event)
          ::reload-db (handle-reload-db event)
          ::search-planets (handle-search-planets event)
          ::planet-selected (handle-planet-selected event)
          ::report-selected (handle-report-selected event)
          ::show-all-reports (handle-show-all-reports event)

          ;; Fleetsave
          ::set-fleetsave-mode (handle-set-fleetsave-mode event)
          ::toggle-fleetsave (handle-toggle-fleetsave event)

          ;; Context menu
          ::copy-report (handle-copy-report event)
          ::attack-small-cargo (handle-attack-small-cargo event)
          ::attack-large-cargo (handle-attack-large-cargo event)
          ::spy-now (handle-spy-now event)

          ;; Options
          ::save-options (handle-save-options event)

          ;; Default
          {:context (:fx/context event)}))
      (fx/wrap-co-effects {:fx/context (fx/make-deref-co-effect state/*state)})
      (fx/wrap-effects {:context (fx/make-reset-effect state/*state)})))
