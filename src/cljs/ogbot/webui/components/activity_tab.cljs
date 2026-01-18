(ns ogbot.webui.components.activity-tab
  (:require [reagent.core :as r]
            [ogbot.webui.state :as state]))

(defn- get-defense-status [report]
  (cond
    (nil? (:defense report)) "?"
    (empty? (:defense report)) "No"
    (every? #(#{"antiBallisticMissile" "interplanetaryMissile"} (first %))
            (:defense report)) "Missiles"
    :else "Yes"))

(defn- format-resources [resources]
  (if resources
    (str (or (:metal resources) 0) "M "
         (or (:crystal resources) 0) "C "
         (or (:deuterium resources) 0) "D")
    "Not spied"))

(defn- get-mines-str [report]
  (if-let [buildings (:buildings report)]
    (str "M:" (get buildings "metalMine" "?")
         " C:" (get buildings "crystalMine" "?")
         " D:" (get buildings "deuteriumSynthesizer" "?"))
    "?"))

(defn- status-class [status]
  (case status
    "Yes" "status-yes"
    "No" "status-no"
    "status-unknown"))

(defn activity-log-panel []
  (let [logs @state/activity-log
        auto-scroll? @state/auto-scroll?]
    [:div
     [:h3 "Activity Log"]
     [:label
      [:input {:type "checkbox"
               :checked auto-scroll?
               :on-change #(reset! state/auto-scroll? (.. % -target -checked))}]
      " Auto-scroll"]
     (into [:div.log {:id "activity-log"}]
           (for [{:keys [time msg]} logs]
             ^{:key (str time msg)}
             [:div.log-entry
              [:span.log-time time]
              [:span msg]]))]))

(defn stats-panel []
  (let [stats @state/stats
        status @state/bot-status]
    [:div
     [:h3 "Statistics"]
     [:p "Status: " [:strong.stats-status status]]
     [:p "Inactive Planets: " [:strong (:planets stats)]]
     [:p "Targets: " [:strong (:targets stats)]]
     [:p "Log Entries: " [:strong (:logs stats)]]
     [:p "DB Planets: " [:strong (:db-planets stats)]]]))

(defn- rent-row [rent]
  (let [target (:target-planet rent)
        source (:source-planet rent)
        history (:espionage-history target)
        report (when (seq history) (last history))
        target-coords (:coords target)
        source-coords (:coords source)
        rentability (or (:rentability rent) 0.0)]
    ^{:key target-coords}
    [:tr
     [:td [:span.rentability {:class (if (pos? rentability) "positive" "negative")}
           (.toFixed rentability 2)]]
     [:td target-coords]
     [:td (or (:name target) "-")]
     [:td (get-in target [:owner :name] "-")]
     [:td (or (get-in target [:owner :alliance]) "-")]
     [:td (format-resources (when report (:resources report)))]
     [:td {:class (status-class (get-defense-status report))}
      (get-defense-status report)]
     [:td (get-mines-str report)]
     [:td source-coords]
     [:td (if report
            (or (:date report) "-")
            "Not spied")]
     [:td.action-cell
      [:button.btn-action.btn-small
       {:on-click #(state/spy-planet! target-coords)} "Spy"]
      [:button.btn-start.btn-small
       {:on-click #(state/attack-planet! target-coords "smallCargo")} "SC"]
      [:button.btn-start.btn-small
       {:on-click #(state/attack-planet! target-coords "largeCargo")} "LC"]]]))

(defn rentabilities-table []
  (let [rents @state/rentabilities]
    [:div
     [:h3 (str "Targets (" (count rents) ")")]
     [:div.table-wrapper.table-wrapper-large
      [:table
       [:thead
        [:tr
         [:th "Rent."]
         [:th "Target"]
         [:th "Name"]
         [:th "Owner"]
         [:th "Alliance"]
         [:th "Resources"]
         [:th "Defended"]
         [:th "Mines"]
         [:th "Source"]
         [:th "Last Spied"]
         [:th "Actions"]]]
       (into [:tbody]
             (map rent-row (take 50 rents)))]]]))

(defn activity-tab []
  [:div#activity-tab.tab-content.active
   [:div.grid
    [activity-log-panel]
    [stats-panel]]
   [rentabilities-table]])
