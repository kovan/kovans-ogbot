(ns ogbot.desktop-gui.views.activity-tab
  "Bot Activity tab view components."
  (:require [cljfx.api :as fx]
            [ogbot.desktop-gui.state :as state]
            [ogbot.desktop-gui.styles :as styles]
            [ogbot.desktop-gui.events :as events]))

;; ============================================================================
;; Activity Log
;; ============================================================================

(defn activity-log-view [{:keys [fx/context]}]
  (let [logs (fx/sub-ctx context state/sub-activity-log)]
    {:fx/type :list-view
     :items (vec logs)
     :cell-factory {:fx/cell-type :list-cell
                    :describe (fn [log-entry]
                                {:text (str (:time log-entry) " " (:msg log-entry))
                                 :style "-fx-font-family: monospace; -fx-font-size: 11px;"})}}))

;; ============================================================================
;; Control Panel
;; ============================================================================

(defn control-panel [{:keys [fx/context]}]
  (let [status (fx/sub-ctx context state/sub-bot-status)
        conn-status (fx/sub-ctx context state/sub-connection-status)]
    {:fx/type :v-box
     :spacing 6
     :min-width 160
     :children
     [;; Start/Stop buttons
      {:fx/type :h-box
       :spacing 6
       :children
       [{:fx/type :button
         :text (case status
                 :stopped "Start"
                 :running "Pause"
                 :paused "Resume")
         :style (case status
                  :stopped styles/start-button-style
                  :running styles/pause-button-style
                  :paused styles/start-button-style)
         :min-width 70
         :on-action {:event/type ::events/start-pause-resume}}
        {:fx/type :button
         :text "Stop"
         :style styles/stop-button-style
         :min-width 70
         :disable (= status :stopped)
         :on-action {:event/type ::events/stop-bot}}]}

      ;; Connection Status
      {:fx/type :titled-pane
       :text "Connection status"
       :collapsible false
       :content {:fx/type :label
                 :text (case conn-status
                         :ok "OK"
                         :error "Connection error"
                         "")
                 :min-height 20
                 :style (styles/connection-status-style conn-status)}}

      ;; Bot Status
      {:fx/type :titled-pane
       :text "Bot status"
       :collapsible false
       :content {:fx/type :label
                 :text (case status
                         :running "Running..."
                         :paused "Paused"
                         :stopped "Stopped"
                         "")
                 :min-height 20
                 :style (styles/bot-status-style status)}}

      ;; Spacer
      {:fx/type :region
       :min-height 20}

      ;; Additional buttons
      {:fx/type :button
       :text "Launch web browser"
       :max-width Double/MAX_VALUE
       :disable (not= conn-status :ok)
       :on-action {:event/type ::events/launch-browser}}

      {:fx/type :button
       :text "Options"
       :max-width Double/MAX_VALUE
       :on-action {:event/type ::events/open-options}}

      {:fx/type :button
       :text "About"
       :max-width Double/MAX_VALUE
       :on-action {:event/type ::events/open-about}}]}))

;; ============================================================================
;; Rentabilities Table
;; ============================================================================

(defn- format-resources [planet]
  (if-let [sim (:simulation planet)]
    (let [res (:resources sim)]
      (str (:metal res) " / " (:crystal res) " / " (:deuterium res)))
    "Not spied"))

(defn- defended-status [planet]
  (if-let [reports (:espionage-history planet)]
    (if (empty? reports)
      "Not spied"
      (let [report (last reports)]
        (cond
          (nil? (:defense report)) "?"
          (empty? (:defense report)) "No"
          :else "Yes")))
    "Not spied"))

(defn- mine-levels-str [planet]
  (if-let [reports (:espionage-history planet)]
    (if (empty? reports)
      "Not spied"
      (let [report (last reports)]
        (if-let [buildings (:buildings report)]
          (str "M: " (get buildings "metalMine" 0)
               ", C: " (get buildings "crystalMine" 0)
               ", D: " (get buildings "deuteriumSynthesizer" 0))
          "?")))
    "Not spied"))

(defn- last-spied-str [planet]
  (if-let [reports (:espionage-history planet)]
    (if (empty? reports)
      "Not spied"
      (str (:date (last reports))))
    "Not spied"))

(defn rentabilities-table [{:keys [fx/context]}]
  (let [rentabilities (fx/sub-ctx context state/sub-rentabilities)
        max-rent (fx/sub-ctx context state/sub-max-rentability)]
    {:fx/type :table-view
     :items (vec rentabilities)
     :placeholder {:fx/type :label
                   :text "No targets available"}
     :context-menu {:fx/type :context-menu
                    :items [{:fx/type :menu-item
                             :text "Copy last espionage report to clipboard"
                             :on-action {:event/type ::events/copy-report}}
                            {:fx/type :separator-menu-item}
                            {:fx/type :menu-item
                             :text "Attack now with small cargos"
                             :on-action {:event/type ::events/attack-small-cargo}}
                            {:fx/type :menu-item
                             :text "Attack now with large cargos"
                             :on-action {:event/type ::events/attack-large-cargo}}
                            {:fx/type :separator-menu-item}
                            {:fx/type :menu-item
                             :text "Spy now"
                             :on-action {:event/type ::events/spy-now}}]}
     :columns
     [{:fx/type :table-column
       :text "Rentability"
       :pref-width 80
       :cell-value-factory identity
       :cell-factory {:fx/cell-type :table-cell
                      :describe (fn [rent]
                                  (let [r (:rentability rent)]
                                    {:text (format "%.2f" (or r 0.0))
                                     :style (str (styles/rentability-cell-style r max-rent)
                                                 (if (and r (pos? r))
                                                   (styles/rentability-positive-style)
                                                   (styles/rentability-negative-style)))}))}}
      {:fx/type :table-column
       :text "Coords"
       :pref-width 80
       :cell-value-factory #(str (get-in % [:target-planet :coords]))}
      {:fx/type :table-column
       :text "Planet name"
       :pref-width 100
       :cell-value-factory #(get-in % [:target-planet :name])}
      {:fx/type :table-column
       :text "Owner"
       :pref-width 90
       :cell-value-factory #(get-in % [:target-planet :owner :name])}
      {:fx/type :table-column
       :text "Alliance"
       :pref-width 70
       :cell-value-factory #(get-in % [:target-planet :owner :alliance])}
      {:fx/type :table-column
       :text "Resources"
       :pref-width 150
       :cell-value-factory #(format-resources (:target-planet %))}
      {:fx/type :table-column
       :text "Defended"
       :pref-width 70
       :cell-value-factory #(defended-status (:target-planet %))}
      {:fx/type :table-column
       :text "Mine levels"
       :pref-width 120
       :cell-value-factory #(mine-levels-str (:target-planet %))}
      {:fx/type :table-column
       :text "Source planet"
       :pref-width 100
       :cell-value-factory #(str (get-in % [:source-planet :coords]))}
      {:fx/type :table-column
       :text "Last spied"
       :pref-width 150
       :cell-value-factory #(last-spied-str (:target-planet %))}]}))

;; ============================================================================
;; Main Tab View
;; ============================================================================

(defn activity-tab [{:keys [fx/context] :as props}]
  {:fx/type :split-pane
   :orientation :vertical
   :divider-positions [0.35]
   :items
   [;; Top section: activity log + control panel
    {:fx/type :h-box
     :spacing 6
     :padding 9
     :children
     [{:fx/type :scroll-pane
       :min-width 400
       :content {:fx/type activity-log-view}}
      {:fx/type control-panel}]}

    ;; Bottom section: rentabilities table
    {:fx/type :v-box
     :spacing 6
     :padding 9
     :children
     [{:fx/type :label
       :text "Most rentable attacks (resource values are simulated). Double click to see details:"}
      {:fx/type rentabilities-table}]}]})
