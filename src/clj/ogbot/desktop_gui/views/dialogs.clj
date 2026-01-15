(ns ogbot.desktop-gui.views.dialogs
  "Dialog windows for the desktop GUI."
  (:require [cljfx.api :as fx]
            [ogbot.desktop-gui.state :as state]
            [ogbot.desktop-gui.events :as events]))

;; ============================================================================
;; About Dialog
;; ============================================================================

(defn about-dialog [{:keys [fx/context]}]
  (let [showing? (fx/sub-ctx context state/sub-about-dialog-open)]
    {:fx/type :stage
     :showing showing?
     :title "About"
     :width 300
     :height 200
     :resizable false
     :on-close-request {:event/type ::events/close-about}
     :scene {:fx/type :scene
             :root {:fx/type :v-box
                    :spacing 15
                    :padding 30
                    :alignment :center
                    :children
                    [{:fx/type :label
                      :text "Kovan's OGBot"
                      :style "-fx-font-size: 18px; -fx-font-weight: bold;"}
                     {:fx/type :label
                      :text "Clojure Edition"}
                     {:fx/type :label
                      :text "Version: 3.1.0-SNAPSHOT"
                      :style "-fx-font-style: italic;"}
                     {:fx/type :label
                      :text "Translated from Python"}
                     {:fx/type :region
                      :min-height 20}
                     {:fx/type :button
                      :text "OK"
                      :min-width 80
                      :on-action {:event/type ::events/close-about}}]}}}))

;; ============================================================================
;; Options Dialog
;; ============================================================================

(defn options-basic-pane [{:keys [fx/context]}]
  {:fx/type :grid-pane
   :hgap 10
   :vgap 10
   :padding 15
   :children
   [;; Server
    {:fx/type :label
     :text "Server:"
     :grid-pane/row 0
     :grid-pane/column 0}
    {:fx/type :text-field
     :grid-pane/row 0
     :grid-pane/column 1
     :grid-pane/hgrow :always}

    ;; Username
    {:fx/type :label
     :text "Username:"
     :grid-pane/row 1
     :grid-pane/column 0}
    {:fx/type :text-field
     :grid-pane/row 1
     :grid-pane/column 1}

    ;; Password
    {:fx/type :label
     :text "Password:"
     :grid-pane/row 2
     :grid-pane/column 0}
    {:fx/type :password-field
     :grid-pane/row 2
     :grid-pane/column 1}

    ;; Attack radius
    {:fx/type :label
     :text "Attack radius:"
     :grid-pane/row 3
     :grid-pane/column 0}
    {:fx/type :spinner
     :grid-pane/row 3
     :grid-pane/column 1
     :editable true
     :value-factory {:fx/type :integer-spinner-value-factory
                     :min 1
                     :max 100
                     :value 10}}

    ;; Probes to send
    {:fx/type :label
     :text "Probes to send:"
     :grid-pane/row 4
     :grid-pane/column 0}
    {:fx/type :spinner
     :grid-pane/row 4
     :grid-pane/column 1
     :editable true
     :value-factory {:fx/type :integer-spinner-value-factory
                     :min 1
                     :max 50
                     :value 3}}

    ;; Slots to reserve
    {:fx/type :label
     :text "Slots to reserve:"
     :grid-pane/row 5
     :grid-pane/column 0}
    {:fx/type :spinner
     :grid-pane/row 5
     :grid-pane/column 1
     :editable true
     :value-factory {:fx/type :integer-spinner-value-factory
                     :min 0
                     :max 20
                     :value 1}}

    ;; Attacking ship
    {:fx/type :label
     :text "Attacking ship:"
     :grid-pane/row 6
     :grid-pane/column 0}
    {:fx/type :h-box
     :spacing 10
     :grid-pane/row 6
     :grid-pane/column 1
     :children
     [{:fx/type :radio-button
       :text "Small Cargo"
       :selected true
       :toggle-group {:fx/type :toggle-group}}
      {:fx/type :radio-button
       :text "Large Cargo"}]}]})

(defn options-advanced-pane [{:keys [fx/context]}]
  {:fx/type :v-box
   :spacing 10
   :padding 15
   :children
   [{:fx/type :label
     :text "Rentability formula:"}
    {:fx/type :text-field
     :prompt-text "(metal + crystal + deuterium) / flightTime"}
    {:fx/type :v-box
     :spacing 5
     :children
     [{:fx/type :radio-button
       :text "Default formula"
       :selected true
       :toggle-group {:fx/type :toggle-group}}
      {:fx/type :radio-button
       :text "Best relation: (metal + crystal + deuterium) / flightTime"}
      {:fx/type :radio-button
       :text "Most total: metal + crystal + deuterium"}
      {:fx/type :radio-button
       :text "Most metal"}
      {:fx/type :radio-button
       :text "Most crystal"}
      {:fx/type :radio-button
       :text "Most deuterium"}
      {:fx/type :radio-button
       :text "Custom formula"}]}
    {:fx/type :separator}
    {:fx/type :label
     :text "Players to avoid (one per line):"}
    {:fx/type :text-area
     :pref-row-count 3}
    {:fx/type :label
     :text "Alliances to avoid (one per line):"}
    {:fx/type :text-area
     :pref-row-count 3}]})

(defn options-dialog [{:keys [fx/context]}]
  (let [showing? (fx/sub-ctx context state/sub-options-dialog-open)]
    {:fx/type :stage
     :showing showing?
     :title "Options"
     :width 550
     :height 500
     :on-close-request {:event/type ::events/close-options}
     :scene {:fx/type :scene
             :root {:fx/type :border-pane
                    :center {:fx/type :tab-pane
                             :tabs [{:fx/type :tab
                                     :text "Basic"
                                     :closable false
                                     :content {:fx/type options-basic-pane}}
                                    {:fx/type :tab
                                     :text "Advanced"
                                     :closable false
                                     :content {:fx/type options-advanced-pane}}]}
                    :bottom {:fx/type :h-box
                             :spacing 10
                             :padding 10
                             :alignment :center-right
                             :children
                             [{:fx/type :button
                               :text "OK"
                               :min-width 80
                               :on-action {:event/type ::events/save-options}}
                              {:fx/type :button
                               :text "Cancel"
                               :min-width 80
                               :on-action {:event/type ::events/close-options}}]}}}}))
