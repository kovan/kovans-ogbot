(ns ogbot.entities
  "Game entities and data structures for OGame"
  (:require [clojure.string :as str]
            [clj-time.core :as t]
            [clj-time.coerce :as tc])
  (:import [java.time Duration LocalDateTime]
           [java.util.regex Pattern]))

;; ============================================================================
;; Resources
;; ============================================================================

(defrecord Resources [metal crystal deuterium energy]
  Object
  (toString [this]
    (format "M: %,d C: %,d D: %,d (total: %,d)"
            metal crystal deuterium
            (+ metal crystal deuterium))))

(defn resources
  ([metal crystal deuterium]
   (->Resources (int metal) (int crystal) (int deuterium) 0))
  ([metal crystal deuterium energy]
   (->Resources (int metal) (int crystal) (int deuterium) (int energy))))

(defn total-resources [^Resources r]
  (+ (:metal r) (:crystal r) (:deuterium r)))

(defn half-resources [^Resources r]
  (resources (/ (:metal r) 2)
             (/ (:crystal r) 2)
             (/ (:deuterium r) 2)))

(defn add-resources [^Resources r1 ^Resources r2]
  (resources (+ (:metal r1) (:metal r2))
             (+ (:crystal r1) (:crystal r2))
             (+ (:deuterium r1) (:deuterium r2))))

(defn sub-resources [^Resources r1 ^Resources r2]
  (resources (- (:metal r1) (:metal r2))
             (- (:crystal r1) (:crystal r2))
             (- (:deuterium r1) (:deuterium r2))))

(defn mul-resources [^Resources r multiplier]
  (resources (* (:metal r) multiplier)
             (* (:crystal r) multiplier)
             (* (:deuterium r) multiplier)))

(defn calculate-rentability
  "Calculate rentability based on resources and flight time using custom formula"
  [^Resources res flight-time-seconds rentability-formula]
  (let [metal (:metal res)
        crystal (:crystal res)
        deuterium (:deuterium res)
        flightTime (double flight-time-seconds)]
    (eval (read-string
            (str "(let [metal " metal " crystal " crystal " deuterium " deuterium " flightTime " flightTime "] "
                 rentability-formula
                 ")")))))

;; ============================================================================
;; Coordinates
;; ============================================================================

(def coord-types
  {:unknown 0
   :planet 1
   :debris 2
   :moon 3})

(def planets-per-system 15)

(def coords-regex #"([0-9]{1,3}):([0-9]{1,3}):([0-9]{1,2})")

(defrecord Coords [galaxy solar-system planet coords-type]
  Comparable
  (compareTo [this other]
    (let [g-cmp (compare galaxy (:galaxy other))]
      (if (not= g-cmp 0)
        g-cmp
        (let [s-cmp (compare solar-system (:solar-system other))]
          (if (not= s-cmp 0)
            s-cmp
            (compare planet (:planet other)))))))

  Object
  (toString [this]
    (let [s (format "[%d:%d:%d]" galaxy solar-system planet)]
      (if (not= coords-type :planet)
        (str s " " (name coords-type))
        s))))

(defn parse-coords
  "Parse coordinate string like '[1:259:12]' or '1:259:12 moon'"
  [coord-str]
  (if-let [match (re-find coords-regex coord-str)]
    (let [[_ g s p] match
          coords-type (if (str/includes? coord-str "moon") :moon :planet)]
      (->Coords (Integer/parseInt g)
                (Integer/parseInt s)
                (Integer/parseInt p)
                coords-type))
    (throw (ex-info "Error parsing coords" {:coords coord-str}))))

(defn coords
  "Create coordinates from galaxy, solar system, planet, and optional type"
  ([galaxy solar-system planet]
   (coords galaxy solar-system planet :planet))
  ([galaxy-or-str solar-system planet coords-type]
   (if (string? galaxy-or-str)
     (parse-coords galaxy-or-str)
     (->Coords (int galaxy-or-str) (int solar-system) (int planet) coords-type))))

(defn moon? [^Coords c]
  (= (:coords-type c) :moon))

(defn distance-between
  "Calculate distance between two coordinates"
  [^Coords from ^Coords to]
  (let [g-diff (- (:galaxy to) (:galaxy from))
        s-diff (- (:solar-system to) (:solar-system from))
        p-diff (- (:planet to) (:planet from))]
    (cond
      (not= g-diff 0) (* (Math/abs g-diff) 20000)
      (not= s-diff 0) (+ (* (Math/abs s-diff) 5 19) 2700)
      (not= p-diff 0) (+ (* (Math/abs p-diff) 5) 1000)
      :else 5)))

(defn flight-time-to
  "Calculate flight time between coordinates given speed and speed percentage"
  [^Coords from ^Coords to speed speed-percentage]
  (let [distance (distance-between from to)
        seconds (+ (* (/ 350000.0 speed-percentage)
                      (Math/sqrt (/ (* distance 10.0) (double speed))))
                   10.0)]
    (Duration/ofSeconds (long seconds))))

;; ============================================================================
;; In-game Types (Ships, Buildings, Defense, Research)
;; ============================================================================

(defprotocol IngameType
  (get-name [this])
  (get-code [this])
  (get-cost [this])
  (get-local-name [this])
  (set-local-name [this name]))

(defrecord Ship [name code cost capacity consumption local-name]
  IngameType
  (get-name [_] name)
  (get-code [_] code)
  (get-cost [_] cost)
  (get-local-name [_] local-name)
  (set-local-name [this n] (assoc this :local-name n))

  Object
  (toString [_] name))

(defrecord Building [name code cost local-name]
  IngameType
  (get-name [_] name)
  (get-code [_] code)
  (get-cost [_] cost)
  (get-local-name [_] local-name)
  (set-local-name [this n] (assoc this :local-name n))

  Object
  (toString [_] name))

(defrecord Defense [name code cost local-name]
  IngameType
  (get-name [_] name)
  (get-code [_] code)
  (get-cost [_] cost)
  (get-local-name [_] local-name)
  (set-local-name [this n] (assoc this :local-name n))

  Object
  (toString [_] name))

(defrecord Research [name code cost local-name]
  IngameType
  (get-name [_] name)
  (get-code [_] code)
  (get-cost [_] cost)
  (get-local-name [_] local-name)
  (set-local-name [this n] (assoc this :local-name n))

  Object
  (toString [_] name))

;; ============================================================================
;; Players and Planets
;; ============================================================================

(defrecord Player [name alliance colonies rank points research-levels])

(defn player
  ([name] (->Player name "" [] 0 0 nil))
  ([name alliance] (->Player name alliance [] 0 0 nil)))

(defrecord OwnPlayer [name alliance colonies rank points research-levels
                      upgrade-to-raid upgrading-colonies attack research])

(defn own-player []
  (->OwnPlayer "" "" [] 0 0 nil [] [] [] {}))

(defrecord EnemyPlayer [name alliance colonies rank points research-levels
                        is-inactive])

(defn enemy-player [name]
  (->EnemyPlayer name "" [] 0 0 nil false))

(defrecord Planet [coords owner name])

(defn planet [coords owner name]
  (->Planet coords owner name))

(defrecord OwnPlanet [coords owner name code point buildings all-buildings
                      defense fleet resources energy resource-production
                      free-building-slots total-building-slots
                      end-wait-time end-build-time end-fleet-wait-time
                      end-defense-wait-time])

(defn own-planet [coords owner name]
  (->OwnPlanet coords owner name 0 0 {} {} {} {} (resources 0 0 0) 0
               (resources 0 0 0) 0 0 nil nil nil nil))

(defrecord EnemyPlanet [coords owner name has-moon has-debris
                        espionage-history attack-history simulation])

(defn enemy-planet [coords owner]
  (->EnemyPlanet coords owner "" false false [] [] nil))

;; ============================================================================
;; Game Messages and Reports
;; ============================================================================

(defrecord GameMessage [code date raw-html subject sender])

(defn game-message [code date raw-html subject sender]
  (->GameMessage code date raw-html subject sender))

(defrecord CombatReport [code date raw-html subject sender coords])

(defn combat-report [code date coords raw-html]
  (->CombatReport code date raw-html "" "" coords))

(def detail-levels
  {:resources 0
   :fleet 1
   :defense 2
   :buildings 3
   :research 4})

(defrecord EspionageReport [code date raw-html subject sender coords
                            resources fleet defense buildings research probes-sent])

(defn espionage-report [code date coords raw-html]
  (->EspionageReport code date raw-html "" "" coords
                     (resources 0 0 0) nil nil nil nil 0))

(defn has-fleet? [^EspionageReport report]
  (or (nil? (:fleet report))
      (pos? (count (:fleet report)))))

(defn has-defense? [^EspionageReport report]
  (or (nil? (:defense report))
      (pos? (count (:defense report)))))

(defn has-non-missile-defense? [^EspionageReport report]
  (if (nil? (:defense report))
    true
    (some (fn [[defense-name _]]
            (and (not (str/includes? defense-name "antiBallisticMissile"))
                 (not (str/includes? defense-name "interplanetaryMissile"))))
          (:defense report))))

(defn get-detail-level [^EspionageReport report]
  (cond
    (some? (:research report)) (:research detail-levels)
    (some? (:buildings report)) (:buildings detail-levels)
    (some? (:defense report)) (:defense detail-levels)
    (some? (:fleet report)) (:fleet detail-levels)
    :else (:resources detail-levels)))

(defn report-age [^EspionageReport report server-time]
  (t/interval (:date report) server-time))

(defn report-expired? [^EspionageReport report server-time]
  (let [age (t/in-days (report-age report server-time))]
    (cond
      (has-non-missile-defense? report) (>= age 7)
      (has-fleet? report) (>= age 4)
      :else false)))

(defn defended? [^EspionageReport report]
  (or (has-fleet? report)
      (has-non-missile-defense? report)))

(defn get-best-espionage-report [espionage-history]
  (when (seq espionage-history)
    (reduce (fn [best report]
              (if (or (> (get-detail-level report) (get-detail-level best))
                      (and (= (get-detail-level report) (get-detail-level best))
                           (t/after? (:date report) (:date best))))
                report
                best))
            (first espionage-history)
            (rest espionage-history))))

(defn planet-rentability
  "Calculate planet rentability based on espionage data and flight time"
  [^EnemyPlanet planet from-coords speed rentability-formula negative-if-defended?]
  (if-not (:simulation planet)
    0
    (let [flight-time-seconds (-> (flight-time-to (:coords planet) from-coords speed 100)
                                  (.getSeconds))
          best-report (get-best-espionage-report (:espionage-history planet))
          rent (calculate-rentability (:resources best-report)
                                      flight-time-seconds
                                      rentability-formula)]
      (if (and negative-if-defended? best-report (defended? best-report))
        (- rent)
        rent))))

;; ============================================================================
;; Missions
;; ============================================================================

(def mission-types
  {:unknown 0
   :attack 1
   :transport 3
   :deploy 4
   :spy 6
   :recycle 8})

(defrecord Mission [mission-type source-planet target-planet fleet resources
                    speed-percentage distance launch-time flight-time
                    arrival-time return-time])

(defn mission
  [mission-type source-planet target-planet fleet res speed-percentage]
  (->Mission mission-type source-planet target-planet fleet res
             (int speed-percentage) 0 nil nil nil nil))

(defn mark-launched [^Mission m launch-time flight-time]
  (let [arrival-time (t/plus launch-time flight-time)
        return-time (t/plus arrival-time flight-time)
        distance (distance-between (-> m :source-planet :coords)
                                   (-> m :target-planet :coords))]
    (assoc m
           :launch-time launch-time
           :flight-time flight-time
           :arrival-time arrival-time
           :return-time return-time
           :distance distance)))
