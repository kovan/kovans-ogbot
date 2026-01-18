(ns ogbot.webui.components.database-tab
  (:require [reagent.core :as r]
            [ogbot.webui.state :as state]))

(defn- status-class [status]
  (case status
    "Yes" "status-yes"
    "No" "status-no"
    "status-unknown"))

(defn filter-bar []
  [:div.filter-bar
   [:button.btn-action {:on-click state/load-planets!} "Reload Database"]
   [:label "Filter:"]
   [:select {:value @state/filter-column
             :on-change #(reset! state/filter-column (.. % -target -value))}
    [:option {:value "coords"} "Coords"]
    [:option {:value "name"} "Name"]
    [:option {:value "owner"} "Owner"]
    [:option {:value "alliance"} "Alliance"]
    [:option {:value "inactive"} "Inactive"]]
   [:label "contains"]
   [:input {:type "text"
            :placeholder "Search..."
            :value @state/filter-text
            :on-change #(reset! state/filter-text (.. % -target -value))
            :on-key-down #(when (= (.-key %) "Enter") (state/search-planets!))}]
   [:button.btn-action {:on-click state/search-planets!} "Search"]
   [:button.btn-pause {:on-click state/load-all-reports!} "Show All Reports"]])

(defn planets-table []
  (let [planets @state/db-planets
        selected @state/selected-planet]
    [:div
     [:h3 (str "Planets (" (count planets) ")")]
     [:div.table-wrapper
      [:table
       [:thead
        [:tr
         [:th "Coords"]
         [:th "Name"]
         [:th "Owner"]
         [:th "Alliance"]
         [:th "Inactive"]
         [:th "Reports"]]]
       [:tbody
        (for [planet planets
              :let [coords (or (:coords planet) "")
                    report-count (or (:report_count planet) 0)]]
          ^{:key coords}
          [:tr {:class (when (= coords selected) "selected")
                :on-click #(state/select-planet! coords)}
           [:td coords]
           [:td (or (:name planet) "-")]
           [:td (or (:owner_name planet) "-")]
           [:td (or (:owner_alliance planet) "-")]
           [:td {:class (if (:owner_is_inactive planet) "inactive-yes" "inactive-no")}
            (if (:owner_is_inactive planet) "yes" "no")]
           [:td (if (pos? report-count) report-count "-")]])]]]]))

(defn reports-table []
  (let [reports @state/planet-reports
        selected-code (when-let [r @state/selected-report] (:code r))]
    [:div
     [:h3 "Spy Reports"]
     [:div.table-wrapper
      [:table
       [:thead
        [:tr
         [:th "Code"]
         [:th "Date"]
         [:th "Coords"]
         [:th "Metal"]
         [:th "Crystal"]
         [:th "Deuterium"]
         [:th "Fleet"]
         [:th "Defense"]
         [:th "Probes"]]]
       [:tbody
        (for [report reports
              :let [code (or (:code report) "")]]
          ^{:key code}
          [:tr {:class (when (= code selected-code) "selected")
                :on-click #(state/select-report! code)}
           [:td code]
           [:td (or (:date report) "-")]
           [:td (or (:coords report) "-")]
           [:td (or (:metal report) 0)]
           [:td (or (:crystal report) 0)]
           [:td (or (:deuterium report) 0)]
           [:td {:class (status-class (:fleet_status report))}
            (:fleet_status report)]
           [:td {:class (status-class (:defense_status report))}
            (:defense_status report)]
           [:td (or (:probes_sent report) "-")]])]]]]))

(defn detail-panel [title data-key]
  (let [report @state/selected-report
        data (when report (get report data-key))]
    [:div.detail-panel
     [:h4 title]
     [:table
      [:tbody
       (if (and data (seq data))
         (for [[type-name quantity] data]
           ^{:key type-name}
           [:tr
            [:td type-name]
            [:td quantity]])
         [:tr [:td {:col-span 2}
               (if (nil? data)
                 (str "Unknown " title)
                 (str "No " title))]])]]]))

(defn detail-panels []
  [:div.detail-grid
   [detail-panel "Fleet" :fleet]
   [detail-panel "Defense" :defense]
   [detail-panel "Buildings" :buildings]
   [detail-panel "Research" :research]])

(defn database-tab []
  [:div#database-tab.tab-content
   [filter-bar]
   [planets-table]
   [reports-table]
   [detail-panels]])
