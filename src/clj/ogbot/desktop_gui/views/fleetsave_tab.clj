(ns ogbot.desktop-gui.views.fleetsave-tab
  "Auto Fleetsave tab view components."
  (:require [cljfx.api :as fx]
            [ogbot.desktop-gui.state :as state]
            [ogbot.desktop-gui.events :as events]))

;; ============================================================================
;; Main Tab View
;; ============================================================================

(defn fleetsave-tab [{:keys [fx/context]}]
  (let [mode (fx/sub-ctx context state/sub-fleetsave-mode)
        enabled? (fx/sub-ctx context state/sub-fleetsave-enabled)]
    {:fx/type :v-box
     :spacing 10
     :padding 15
     :children
     [{:fx/type :h-box
       :spacing 15
       :alignment :center-left
       :children
       [{:fx/type :titled-pane
         :text "Fleetsave mode:"
         :collapsible false
         :content {:fx/type :v-box
                   :spacing 8
                   :padding 10
                   :children
                   [{:fx/type :radio-button
                     :text "Hide fleet: fleetsave also when enemy espionages detected"
                     :selected (= mode :hide-fleet)
                     :toggle-group {:fx/type :toggle-group}
                     :on-action {:event/type ::events/set-fleetsave-mode
                                 :mode :hide-fleet}}
                    {:fx/type :radio-button
                     :text "Normal: fleetsave only when attacks detected"
                     :selected (= mode :normal)
                     :on-action {:event/type ::events/set-fleetsave-mode
                                 :mode :normal}}]}}
        {:fx/type :button
         :text (if enabled? "Disable" "Enable")
         :style (if enabled?
                  "-fx-background-color: #dc3545; -fx-text-fill: white; -fx-font-weight: bold;"
                  "-fx-background-color: #28a745; -fx-text-fill: white; -fx-font-weight: bold;")
         :min-width 100
         :min-height 40
         :on-action {:event/type ::events/toggle-fleetsave}}]}

      {:fx/type :separator}

      {:fx/type :label
       :text "Fleetsave status:"
       :style "-fx-font-weight: bold;"}

      {:fx/type :table-view
       :min-height 200
       :placeholder {:fx/type :label
                     :text "No fleetsave activity"}
       :items []
       :columns
       [{:fx/type :table-column
         :text "Time"
         :pref-width 100}
        {:fx/type :table-column
         :text "Planet"
         :pref-width 100}
        {:fx/type :table-column
         :text "Destination"
         :pref-width 100}
        {:fx/type :table-column
         :text "Fleet"
         :pref-width 150}
        {:fx/type :table-column
         :text "Return time"
         :pref-width 150}
        {:fx/type :table-column
         :text "Status"
         :pref-width 100}]}]}))
