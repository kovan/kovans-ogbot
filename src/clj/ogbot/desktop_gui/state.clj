(ns ogbot.desktop-gui.state
  "Centralized state management for the desktop GUI using cljfx context."
  (:require [cljfx.api :as fx]))

;; ============================================================================
;; Initial State
;; ============================================================================

(def initial-state
  {:bot
   {:state nil                    ; Reference to BotState record
    :thread nil                   ; Bot thread reference
    :status :stopped              ; :stopped | :running | :paused
    :connection-status nil        ; nil | :ok | :error
    :status-message nil}          ; Current status message

   :activity
   {:log []                       ; Vector of {:time :msg} entries (max 100)
    :rentabilities []}            ; Vector of Rentability records

   :planet-db
   {:planets []                   ; Loaded planets from database
    :selected-planet nil          ; Currently selected planet coords string
    :filter-column :coords        ; :coords | :name | :owner | :alliance | :owner-inactive
    :filter-text ""
    :reports []                   ; Espionage reports for selected planet
    :selected-report nil}         ; Currently selected report

   :fleetsave
   {:mode :normal                 ; :normal | :hide-fleet
    :enabled? false}

   :ui
   {:current-tab 0                ; 0, 1, or 2
    :options-dialog-open? false
    :about-dialog-open? false}

   :config nil})                  ; Loaded configuration

;; ============================================================================
;; State Atom
;; ============================================================================

(defonce *state (atom (fx/create-context initial-state)))

;; ============================================================================
;; Subscription Functions (derived state)
;; ============================================================================

(defn sub-bot-status [context]
  (fx/sub-val context get-in [:bot :status]))

(defn sub-bot-state [context]
  (fx/sub-val context get-in [:bot :state]))

(defn sub-connection-status [context]
  (fx/sub-val context get-in [:bot :connection-status]))

(defn sub-status-message [context]
  (fx/sub-val context get-in [:bot :status-message]))

(defn sub-activity-log [context]
  (fx/sub-val context get-in [:activity :log]))

(defn sub-rentabilities [context]
  (fx/sub-val context get-in [:activity :rentabilities]))

(defn sub-max-rentability [context]
  (let [rents (fx/sub-val context get-in [:activity :rentabilities])]
    (if (empty? rents)
      1
      (apply max (map :rentability rents)))))

(defn sub-planets [context]
  (fx/sub-val context get-in [:planet-db :planets]))

(defn sub-filter-column [context]
  (fx/sub-val context get-in [:planet-db :filter-column]))

(defn sub-filter-text [context]
  (fx/sub-val context get-in [:planet-db :filter-text]))

(defn- get-planet-field [planet field]
  (case field
    :coords (str (:coords planet))
    :name (:name planet)
    :owner (get-in planet [:owner :name])
    :alliance (get-in planet [:owner :alliance])
    :owner-inactive (if (get-in planet [:owner :is-inactive]) "yes" "no")
    ""))

(defn sub-filtered-planets [context]
  (let [planets (fx/sub-val context get-in [:planet-db :planets])
        filter-col (fx/sub-val context get-in [:planet-db :filter-column])
        filter-text (fx/sub-val context get-in [:planet-db :filter-text])]
    (if (empty? filter-text)
      planets
      (filter #(clojure.string/includes?
                 (clojure.string/lower-case (str (get-planet-field % filter-col)))
                 (clojure.string/lower-case filter-text))
              planets))))

(defn sub-selected-planet [context]
  (fx/sub-val context get-in [:planet-db :selected-planet]))

(defn sub-reports [context]
  (fx/sub-val context get-in [:planet-db :reports]))

(defn sub-selected-report [context]
  (fx/sub-val context get-in [:planet-db :selected-report]))

(defn sub-fleetsave-mode [context]
  (fx/sub-val context get-in [:fleetsave :mode]))

(defn sub-fleetsave-enabled [context]
  (fx/sub-val context get-in [:fleetsave :enabled?]))

(defn sub-current-tab [context]
  (fx/sub-val context get-in [:ui :current-tab]))

(defn sub-options-dialog-open [context]
  (fx/sub-val context get-in [:ui :options-dialog-open?]))

(defn sub-about-dialog-open [context]
  (fx/sub-val context get-in [:ui :about-dialog-open?]))

(defn sub-config [context]
  (fx/sub-val context :config))
