(ns ogbot.core
  "Main entry point for OGBot"
  (:require [ogbot.gui :as gui]
            [ogbot.bot :as bot]
            [ogbot.config :as config])
  (:gen-class))

(defn print-banner []
  (println "╔═══════════════════════════════════════════╗")
  (println "║   Kovan's OGBot - Clojure Edition v3.1   ║")
  (println "║                                           ║")
  (println "║   Automated OGame Bot                    ║")
  (println "║   Translated from Python to Clojure      ║")
  (println "╚═══════════════════════════════════════════╝")
  (println))

(defn print-usage []
  (println "Usage:")
  (println "  lein run              - Start with GUI")
  (println "  lein run --no-gui     - Run in console mode")
  (println "  lein run --help       - Show this help")
  (println))

(defn run-console-mode []
  (println "Starting bot in console mode...")
  (try
    (bot/run-bot "files/config/config.ini")
    (catch Exception e
      (println "Error:" (.getMessage e))
      (.printStackTrace e))))

(defn run-gui-mode []
  (println "Starting bot with Web UI...")
  (gui/start-gui)
  ;; Keep main thread alive
  (loop []
    (Thread/sleep 1000)
    (recur)))

(defn -main
  "Main entry point for OGBot"
  [& args]
  (print-banner)

  (cond
    (or (nil? args) (empty? args))
    (run-gui-mode)

    (some #{"--help" "-h"} args)
    (print-usage)

    (some #{"--no-gui" "--console"} args)
    (run-console-mode)

    :else
    (do
      (println "Unknown option:" (first args))
      (print-usage))))
