(ns ogbot.desktop-gui.views.database-tab
  "Planet Database tab view components."
  (:require [cljfx.api :as fx]
            [ogbot.desktop-gui.state :as state]
            [ogbot.desktop-gui.events :as events]
            [clj-time.format :as tf]))

;; ============================================================================
;; Formatters
;; ============================================================================

(def date-formatter (tf/formatter "HH:mm:ss MM-dd"))

(defn- format-date [date]
  (if date
    (try
      (tf/unparse date-formatter date)
      (catch Exception _ (str date)))
    ""))

(defn- has-info-str [data]
  (cond
    (nil? data) "Unknown"
    (empty? data) "No"
    :else "Yes"))

(defn- defense-status-str [report]
  (cond
    (nil? (:defense report)) "Unknown"
    (empty? (:defense report)) "No"
    ;; Check if only missiles
    (and (every? #(#{"antiBallisticMissile" "interplanetaryMissile"} (first %))
                 (:defense report))
         (seq (:defense report)))
    "Only missiles"
    :else "Yes"))

;; ============================================================================
;; Filter Bar
;; ============================================================================

(defn filter-bar [{:keys [fx/context]}]
  (let [filter-col (fx/sub-ctx context state/sub-filter-column)
        filter-text (fx/sub-ctx context state/sub-filter-text)]
    {:fx/type :h-box
     :spacing 6
     :alignment :center-left
     :children
     [{:fx/type :button
       :text "Reload database"
       :on-action {:event/type ::events/reload-db}}
      {:fx/type :label
       :text "Filter:"}
      {:fx/type :combo-box
       :value (name filter-col)
       :items ["coords" "name" "owner" "alliance" "owner-inactive"]
       :on-value-changed {:event/type ::events/set-filter-column}}
      {:fx/type :label
       :text "contains"}
      {:fx/type :text-field
       :text filter-text
       :min-width 200
       :on-text-changed {:event/type ::events/set-filter-text}}
      {:fx/type :button
       :text "Search"
       :on-action {:event/type ::events/search-planets}}]}))

;; ============================================================================
;; Planets Table
;; ============================================================================

(defn planets-table [{:keys [fx/context]}]
  (let [planets (fx/sub-ctx context state/sub-filtered-planets)]
    {:fx/type :table-view
     :items (vec planets)
     :placeholder {:fx/type :label
                   :text "No planets found. Click 'Reload database' to load."}
     :on-selected-item-changed {:event/type ::events/planet-selected}
     :columns
     [{:fx/type :table-column
       :text "Coords"
       :pref-width 100
       :cell-value-factory #(str (:coords %))}
      {:fx/type :table-column
       :text "Name"
       :pref-width 100
       :cell-value-factory :name}
      {:fx/type :table-column
       :text "Owner"
       :pref-width 100
       :cell-value-factory #(get-in % [:owner :name])}
      {:fx/type :table-column
       :text "Alliance"
       :pref-width 80
       :cell-value-factory #(get-in % [:owner :alliance])}
      {:fx/type :table-column
       :text "Owner inactive"
       :pref-width 90
       :cell-value-factory #(if (get-in % [:owner :is-inactive]) "yes" "no")}
      {:fx/type :table-column
       :text "Spy reports"
       :pref-width 80
       :cell-value-factory #(let [c (count (:espionage-history %))]
                              (if (zero? c) "-" (str c)))}]}))

;; ============================================================================
;; Reports Table
;; ============================================================================

(defn reports-table [{:keys [fx/context]}]
  (let [reports (fx/sub-ctx context state/sub-reports)]
    {:fx/type :table-view
     :items (vec reports)
     :placeholder {:fx/type :label
                   :text "Select a planet to view its spy reports"}
     :on-selected-item-changed {:event/type ::events/report-selected}
     :columns
     [{:fx/type :table-column
       :text "Code"
       :pref-width 60
       :cell-value-factory :code}
      {:fx/type :table-column
       :text "Date"
       :pref-width 110
       :cell-value-factory #(format-date (:date %))}
      {:fx/type :table-column
       :text "Coords"
       :pref-width 80
       :cell-value-factory #(str (:coords %))}
      {:fx/type :table-column
       :text "Metal"
       :pref-width 80
       :cell-value-factory #(get-in % [:resources :metal])}
      {:fx/type :table-column
       :text "Crystal"
       :pref-width 80
       :cell-value-factory #(get-in % [:resources :crystal])}
      {:fx/type :table-column
       :text "Deuterium"
       :pref-width 80
       :cell-value-factory #(get-in % [:resources :deuterium])}
      {:fx/type :table-column
       :text "Fleet"
       :pref-width 60
       :cell-value-factory #(has-info-str (:fleet %))}
      {:fx/type :table-column
       :text "Defenses"
       :pref-width 80
       :cell-value-factory #(defense-status-str %)}
      {:fx/type :table-column
       :text "Probes"
       :pref-width 50
       :cell-value-factory :probes-sent}]}))

;; ============================================================================
;; Detail Tables
;; ============================================================================

(defn detail-table [{:keys [fx/context title data-key]}]
  (let [report (fx/sub-ctx context state/sub-selected-report)
        data (when report (get report data-key))]
    {:fx/type :v-box
     :min-width 180
     :children
     [{:fx/type :label
       :text title
       :style "-fx-font-weight: bold;"}
      {:fx/type :table-view
       :min-height 150
       :items (if data
                (vec (map (fn [[k v]] {:type k :quantity v}) data))
                [{:type (str "Unknown " title) :quantity ""}])
       :columns
       [{:fx/type :table-column
         :text "Type"
         :pref-width 120
         :cell-value-factory :type}
        {:fx/type :table-column
         :text "Quantity"
         :pref-width 60
         :cell-value-factory :quantity}]}]}))

;; ============================================================================
;; Main Tab View
;; ============================================================================

(defn database-tab [{:keys [fx/context] :as props}]
  {:fx/type :v-box
   :spacing 6
   :padding 9
   :children
   [{:fx/type filter-bar}
    {:fx/type :split-pane
     :orientation :vertical
     :divider-positions [0.35 0.65]
     :min-height 400
     :items
     [;; Planets table
      {:fx/type planets-table}

      ;; Reports section
      {:fx/type :v-box
       :spacing 3
       :children
       [{:fx/type :h-box
         :spacing 6
         :alignment :center-left
         :children
         [{:fx/type :label
           :text "Spy reports"}
          {:fx/type :button
           :text "Show all planet's last spy report"
           :on-action {:event/type ::events/show-all-reports}}]}
        {:fx/type reports-table}]}

      ;; Detail tables
      {:fx/type :h-box
       :spacing 6
       :children
       [{:fx/type detail-table
         :title "Fleet"
         :data-key :fleet}
        {:fx/type detail-table
         :title "Defense"
         :data-key :defense}
        {:fx/type detail-table
         :title "Buildings"
         :data-key :buildings}
        {:fx/type detail-table
         :title "Research"
         :data-key :research}]}]}]})
