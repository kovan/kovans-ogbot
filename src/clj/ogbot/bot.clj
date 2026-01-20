(ns ogbot.bot
  "Core OGBot logic"
  (:require [clojure.java.io :as io]
            [clojure.core.async :as async]
            [clj-time.core :as t]
            [clj-time.coerce :as tc]
            [ogbot.entities :as entities]
            [ogbot.constants :as constants]
            [ogbot.config :as config]
            [ogbot.db :as db]
            [ogbot.web-selenium :as web]
            [ogbot.utils :as utils])
  (:import [java.time Duration]))

;; ============================================================================
;; Event Management
;; ============================================================================

(defprotocol EventManager
  (log-activity [this msg])
  (log-status [this msg])
  (fatal-exception [this exception])
  (connected [this])
  (simulations-update [this rentabilities]))

(defrecord ConsoleEventManager []
  EventManager
  (log-activity [_ msg]
    (println (str (t/now) " " msg)))
  (log-status [_ msg]
    (println (str "[STATUS] " msg)))
  (fatal-exception [_ exception]
    (println (str "[FATAL] " (.getMessage exception))))
  (connected [_]
    (println "Connected to OGame server"))
  (simulations-update [_ rentabilities]
    (println (str "Simulations updated: " (count rentabilities) " targets"))))

;; ============================================================================
;; Plugin System
;; ============================================================================

(defprotocol Plugin
  (step [this]))

(defrecord PluginSystem [plugins]
  Plugin
  (step [this]
    (doseq [plugin (:plugins this)]
      (step plugin))))

(defn create-plugin-system [config web-adapter]
  (->PluginSystem []))

;; ============================================================================
;; Bot State
;; ============================================================================

(defrecord BotState [config own-player web-adapter planet-db translations
                     inactive-planets source-planets reachable-solar-systems
                     last-inactive-scan-time not-arrived-espionages
                     attacking-ship secondary-attacking-ship event-mgr
                     running? paused? msg-queue])

(defn create-bot-state [config-file event-mgr]
  (let [config (config/load-bot-configuration config-file)
        translations (config/load-translations)
        planet-db-spec (db/create-db-spec (get constants/file-paths :planetdb))
        attacking-ship (if (= "smallCargo" (:attacking-ship config))
                        (constants/get-by-name "smallCargo")
                        (constants/get-by-name "largeCargo"))
        secondary-ship (if (= "smallCargo" (:attacking-ship config))
                         (constants/get-by-name "largeCargo")
                         (constants/get-by-name "smallCargo"))]
    (db/init-planet-db! planet-db-spec)
    (->BotState config
                (entities/own-player)
                nil ;; web-adapter initialized later
                planet-db-spec
                translations
                []
                []
                []
                nil
                (atom {})
                attacking-ship
                secondary-ship
                event-mgr
                (atom true)
                (atom false)
                (async/chan 100))))

;; ============================================================================
;; File Persistence
;; ============================================================================

(defn save-bot-state! [state]
  (let [file-path (get constants/file-paths :botstate)]
    (spit file-path (pr-str {:inactive-planets (:inactive-planets state)
                             :last-scan-time (:last-inactive-scan-time state)}))))

(defn load-bot-state! [state]
  (let [file-path (get constants/file-paths :botstate)]
    (when (.exists (io/file file-path))
      (try
        (let [data (read-string (slurp file-path))]
          (assoc state
                 :inactive-planets (:inactive-planets data)
                 :last-inactive-scan-time (:last-scan-time data)))
        (catch Exception e
          state)))))

;; ============================================================================
;; Connection and Initialization
;; ============================================================================

(defn connect! [state]
  (log-activity (:event-mgr state) "Contacting server...")
  (let [check-msgs-fn (fn [] nil) ;; Simplified
        web-adapter (web/create-web-adapter (:config state)
                                            (:translations state)
                                            check-msgs-fn
                                            (:event-mgr state))
        updated-player (web/get-my-planets web-adapter (:own-player state) nil)]
    (let [version (:version (:server-data web-adapter))]
      (when (> version constants/supported-ogame-version)
        (log-activity (:event-mgr state)
                     (format "WARNING: Bot designed for v%.1f, found v%.1f"
                            constants/supported-ogame-version version))))

    ;; Update ship speeds based on research
    (let [research (:research-levels updated-player)
          large-cargo (constants/get-by-name "largeCargo")
          small-cargo (constants/get-by-name "smallCargo")
          combustion (:combustionDrive research 0)
          impulse (:impulseDrive research 0)]
      ;; Update speeds (simplified - would need to modify ship records)
      )

    (connected (:event-mgr state))
    ;; Set source-planets from player's colonies if not configured
    (let [source-planets (if (empty? (:source-planets state))
                          (:colonies updated-player)
                          (:source-planets state))]
      (assoc state
             :web-adapter web-adapter
             :own-player updated-player
             :source-planets source-planets))))

;; ============================================================================
;; Galaxy Scanning
;; ============================================================================

(defn calculate-reachable-systems [state]
  (let [attack-radius (:attack-radius (:config state))
        systems-per-galaxy (:systems-per-galaxy (:config state))
        source-planets (:source-planets state)]
    (vec
     (distinct
      (for [source-planet source-planets
            :let [galaxy (:galaxy (:coords source-planet))
                  center-system (:solar-system (:coords source-planet))
                  first-system (max 1 (- center-system attack-radius))
                  last-system (min systems-per-galaxy (+ center-system attack-radius))]
            system (range first-system (inc last-system))]
        [galaxy system])))))

(defn scan-galaxies [state]
  (log-activity (:event-mgr state) "Searching inactive planets...")
  (let [systems (calculate-reachable-systems state)
        _ (log-activity (:event-mgr state) (format "Calculated %d reachable systems" (count systems)))]
    (if (empty? systems)
      (do
        (log-activity (:event-mgr state) "No reachable systems found - check source planets config")
        state)
      (let [deut-planet (:deuterium-source-planet (:config state))
            web-adapter (:web-adapter state)
            planet-db (:planet-db state)
            all-planets (atom [])
            system-count (count systems)]
        ;; Scan and save incrementally
        (doseq [[idx [galaxy system]] (map-indexed vector systems)]
          (log-activity (:event-mgr state) (format "Scanning %d:%d (%d/%d)" galaxy system (inc idx) system-count))
          (let [planets (web/scan-solar-system web-adapter galaxy system)]
            (when (seq planets)
              (swap! all-planets into planets))
            ;; Save incrementally every 10 systems
            (when (and (pos? (count @all-planets))
                       (zero? (mod (inc idx) 10)))
              (db/write-many-planets! planet-db @all-planets)
              (log-activity (:event-mgr state) (format "Saved %d planets so far..." (count @all-planets))))))

        ;; Final save
        (db/write-many-planets! planet-db @all-planets)
        (log-activity (:event-mgr state) (format "Scanned %d planets total" (count @all-planets)))

        (let [inactive-planets (filter #(:is-inactive (:owner %)) @all-planets)
              filtered-inactives (remove
                                 (fn [p]
                                   (or (some #{(:name (:owner p))}
                                            (:players-to-avoid (:config state)))
                                       (some #{(:alliance (:owner p))}
                                            (:alliances-to-avoid (:config state)))))
                                 inactive-planets)]

          (log-activity (:event-mgr state)
                       (format "Found %d inactive planets in %d systems"
                              (count filtered-inactives)
                              system-count))

          (assoc state
                 :inactive-planets filtered-inactives
                 :last-inactive-scan-time (t/now)
                 :reachable-solar-systems systems))))))

;; ============================================================================
;; Espionage
;; ============================================================================

(defn spy-planet [state source-planet target-planet probes-to-send]
  (let [mission (entities/mission :spy
                                 source-planet
                                 target-planet
                                 {"espionageProbe" probes-to-send}
                                 (entities/resources 0 0 0)
                                 100)]
    (try
      (web/launch-mission (:web-adapter state) mission true 0)
      (log-activity (:event-mgr state)
                   (format "Spying %s from %s"
                          (:coords target-planet)
                          (:coords source-planet)))
      mission
      (catch Exception e
        (log-activity (:event-mgr state)
                     (format "Error spying: %s" (.getMessage e)))
        nil))))

(defn spy-planets [state planets detail-level]
  (doseq [planet planets
          :let [source-planet (first (:source-planets state))]]
    (spy-planet state source-planet planet (:probes-to-send (:config state)))))

(defn check-espionage-reports-arrived
  "Check if pending espionage missions have returned with reports.
  Returns [updated-state arrived-reports]."
  [state]
  (let [not-arrived (:not-arrived-espionages state)
        web-adapter (:web-adapter state)
        planet-db (:planet-db state)]
    (if (empty? not-arrived)
      [state []]
      (let [displayed-reports (web/get-game-messages web-adapter :espionage-report)
            server-time (web/current-server-time (:server-data web-adapter))
            results (reduce
                     (fn [[arrived remaining] [planet espionage]]
                       (let [target-coords (:coords (:target-planet espionage))
                             launch-time (:launch-time espionage)
                             arrival-time (:arrival-time espionage)
                             ;; Find matching reports
                             matching-reports (filter
                                              (fn [report]
                                                (and (= (:coords report) target-coords)
                                                     (>= (:date report) launch-time)))
                                              displayed-reports)
                             ;; Sort by date (newest first)
                             sorted-reports (reverse (sort-by :date matching-reports))]
                         (cond
                           ;; Report arrived
                           (seq sorted-reports)
                           (let [report (first sorted-reports)
                                 ;; Update report with probes sent
                                 report (assoc report :probes-sent
                                             (get (:fleet espionage) "espionageProbe" 0))
                                 ;; Update planet with simulation and history
                                 planet (-> planet
                                          (assoc :simulation
                                                 {:resources (:resources report)
                                                  :mines (:buildings report)})
                                          (update :espionage-history conj report))]
                             ;; Save to database
                             (db/write-planet! planet-db planet)
                             [(conj arrived report) remaining])

                           ;; Report never arrived (timeout after 2 minutes)
                           (> server-time (+ arrival-time (* 2 60 1000)))
                           (do
                             (web/activity-msg (:event-mgr state)
                                              (format "Espionage report from %s never arrived. Deleting planet."
                                                     (str target-coords)))
                             ;; Remove from inactive planets
                             (swap! (:inactive-planets state)
                                   (fn [planets] (remove #(= % planet) planets)))
                             [arrived remaining])

                           ;; Still waiting
                           :else
                           [arrived (assoc remaining planet espionage)])))
                     [[] {}]
                     not-arrived)
            [arrived-reports remaining-espionages] results]

        ;; Delete arrived reports from game
        (when (seq arrived-reports)
          (web/delete-messages web-adapter arrived-reports)
          (save-bot-state! state))

        ;; Return updated state and arrived reports
        [(assoc state :not-arrived-espionages remaining-espionages) arrived-reports]))))

;; ============================================================================
;; Attack Mode
;; ============================================================================

(defrecord Rentability [source-planet target-planet rentability])

(defn generate-rentability-table [state planets]
  (let [source-planets (:source-planets state)
        formula (:rentability-formula (:config state))
        attacking-ship (:attacking-ship state)]
    (->> (for [target planets
               source source-planets]
           (let [rent (entities/planet-rentability
                      target
                      (:coords source)
                      (:speed attacking-ship)
                      formula
                      true)]
             (->Rentability source target rent)))
         (sort-by :rentability >)
         vec)))

(defn attack-planet [state source-planet target-planet ship abort-if-not-enough?]
  (let [best-report (entities/get-best-espionage-report
                    (:espionage-history target-planet))
        resources (if best-report
                   (entities/half-resources (:resources best-report))
                   (entities/resources 0 0 0))
        needed-capacity (:metal resources)
        ships-needed (int (Math/ceil (/ needed-capacity (:capacity ship))))
        mission (entities/mission :attack
                                 source-planet
                                 target-planet
                                 {(:name ship) ships-needed}
                                 resources
                                 100)]
    (try
      (let [sent-mission (web/launch-mission (:web-adapter state)
                                            mission
                                            abort-if-not-enough?
                                            (:slots-to-reserve (:config state)))]
        (log-activity (:event-mgr state)
                     (format "Attacking %s from %s with %d %s"
                            (:coords target-planet)
                            (:coords source-planet)
                            ships-needed
                            (:name ship)))
        sent-mission)
      (catch Exception e
        (throw e)))))

(defn attack-mode [state]
  (log-activity (:event-mgr state) "Entering attack mode")
  (let [planets-without-ships (atom {})
        not-arrived-attacks (atom [])]
    (loop []
      (when @(:running? state)
        (let [rentabilities (generate-rentability-table state
                                                       (:inactive-planets state))]
          (simulations-update (:event-mgr state) rentabilities)

          (when (seq rentabilities)
            (let [best (first rentabilities)
                  target (:target-planet best)
                  source (:source-planet best)]
              (try
                (attack-planet state source target (:attacking-ship state) true)
                (Thread/sleep 5000)
                (catch Exception e
                  (log-activity (:event-mgr state)
                               (format "Error: %s" (.getMessage e))))))))

        (Thread/sleep 15000)
        (recur)))))

;; ============================================================================
;; Main Bot Loop
;; ============================================================================

(defn start! [state]
  "Start bot in auto mode - scans and attacks automatically"
  (log-activity (:event-mgr state) "Bot started (auto mode)")
  (let [state (load-bot-state! state)
        state (connect! state)
        state (scan-galaxies state)]
    (spy-planets state (:inactive-planets state) :buildings)
    (attack-mode state)))

(defn start-interactive! [state]
  "Start bot in interactive mode - connects but waits for manual commands"
  (log-activity (:event-mgr state) "Bot started (interactive mode)")
  (let [state (load-bot-state! state)
        state (connect! state)]
    (log-activity (:event-mgr state) "Connected and ready. Use web UI to control.")
    ;; Keep the state updated and return it
    state))

(defn stop! [state]
  (reset! (:running? state) false)
  (save-bot-state! state)
  (when-let [adapter (:web-adapter state)]
    (try
      (web/shutdown-adapter adapter)
      (catch Exception _ nil)))
  (log-activity (:event-mgr state) "Bot stopped"))

(defn run-bot [config-file]
  (let [event-mgr (->ConsoleEventManager)
        state (create-bot-state config-file event-mgr)]
    (try
      (start! state)
      (catch Exception e
        (fatal-exception event-mgr e)
        (stop! state)))))
