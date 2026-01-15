(ns ogbot.desktop-gui.event-manager
  "JavaFXEventManager implementation of the bot/EventManager protocol.
   Dispatches events to the cljfx state atom with thread-safe updates."
  (:require [ogbot.bot :as bot]
            [ogbot.desktop-gui.state :as state]
            [cljfx.api :as fx]
            [clj-time.core :as t]
            [clj-time.format :as tf]))

;; ============================================================================
;; Helper Functions
;; ============================================================================

(def time-formatter (tf/formatter "HH:mm:ss"))

(defn- format-time [time]
  (tf/unparse time-formatter time))

(defn- add-log-entry [ctx msg]
  (update-in ctx [:activity :log]
             #(vec (take-last 100 (conj % {:time (format-time (t/now))
                                            :msg msg})))))

;; ============================================================================
;; JavaFXEventManager Record
;; ============================================================================

(defrecord JavaFXEventManager []
  bot/EventManager

  (log-activity [_ msg]
    ;; Use fx/on-fx-thread to ensure thread safety when updating from bot thread
    (fx/on-fx-thread
      (swap! state/*state fx/swap-context add-log-entry msg)))

  (log-status [_ msg]
    (fx/on-fx-thread
      (swap! state/*state fx/swap-context
             (fn [ctx]
               (-> ctx
                   (assoc-in [:bot :status-message] msg)
                   (add-log-entry msg))))))

  (fatal-exception [_ exception]
    (fx/on-fx-thread
      (swap! state/*state fx/swap-context
             (fn [ctx]
               (-> ctx
                   (assoc-in [:bot :status] :stopped)
                   (assoc-in [:bot :connection-status] :error)
                   (add-log-entry (str "FATAL: " (.getMessage exception))))))
      ;; Show error dialog
      (let [alert (javafx.scene.control.Alert.
                    javafx.scene.control.Alert$AlertType/ERROR)]
        (.setTitle alert "Fatal Error")
        (.setHeaderText alert "Critical error occurred")
        (.setContentText alert (str (.getMessage exception)))
        (.showAndWait alert))))

  (connected [_]
    (fx/on-fx-thread
      (swap! state/*state fx/swap-context
             (fn [ctx]
               (-> ctx
                   (assoc-in [:bot :connection-status] :ok)
                   (add-log-entry "Connected to OGame server"))))))

  (simulations-update [_ rentabilities]
    (fx/on-fx-thread
      (swap! state/*state fx/swap-context
             (fn [ctx]
               (-> ctx
                   (assoc-in [:bot :connection-status] :ok)
                   (assoc-in [:activity :rentabilities] (vec rentabilities))))))))

;; ============================================================================
;; Constructor
;; ============================================================================

(defn create-event-manager
  "Create a new JavaFXEventManager instance."
  []
  (->JavaFXEventManager))
