(ns ogbot.entities-test
  (:require [clojure.test :refer :all]
            [ogbot.entities :as e]
            [clj-time.core :as t])
  (:import [java.time Duration]))

;; ============================================================================
;; Resources Tests
;; ============================================================================

(deftest test-resources-creation
  (testing "Creating resources"
    (let [res (e/resources 1000 500 250)]
      (is (= 1000 (:metal res)))
      (is (= 500 (:crystal res)))
      (is (= 250 (:deuterium res)))
      (is (= 0 (:energy res))))))

(deftest test-total-resources
  (testing "Calculating total resources"
    (let [res (e/resources 1000 500 250)]
      (is (= 1750 (e/total-resources res))))))

(deftest test-add-resources
  (testing "Adding resources"
    (let [r1 (e/resources 1000 500 250)
          r2 (e/resources 500 250 125)
          result (e/add-resources r1 r2)]
      (is (= 1500 (:metal result)))
      (is (= 750 (:crystal result)))
      (is (= 375 (:deuterium result))))))

(deftest test-sub-resources
  (testing "Subtracting resources"
    (let [r1 (e/resources 1000 500 250)
          r2 (e/resources 200 100 50)
          result (e/sub-resources r1 r2)]
      (is (= 800 (:metal result)))
      (is (= 400 (:crystal result)))
      (is (= 200 (:deuterium result))))))

(deftest test-mul-resources
  (testing "Multiplying resources"
    (let [res (e/resources 1000 500 250)
          result (e/mul-resources res 2)]
      (is (= 2000 (:metal result)))
      (is (= 1000 (:crystal result)))
      (is (= 500 (:deuterium result))))))

(deftest test-half-resources
  (testing "Halving resources"
    (let [res (e/resources 1000 500 250)
          result (e/half-resources res)]
      (is (= 500 (:metal result)))
      (is (= 250 (:crystal result)))
      (is (= 125 (:deuterium result))))))

;; ============================================================================
;; Coordinates Tests
;; ============================================================================

(deftest test-coords-creation
  (testing "Creating coordinates"
    (let [c (e/coords 1 240 3)]
      (is (= 1 (:galaxy c)))
      (is (= 240 (:solar-system c)))
      (is (= 3 (:planet c)))
      (is (= :planet (:coords-type c))))))

(deftest test-parse-coords
  (testing "Parsing coordinate strings"
    (let [c (e/parse-coords "[1:240:3]")]
      (is (= 1 (:galaxy c)))
      (is (= 240 (:solar-system c)))
      (is (= 3 (:planet c))))

    (let [c (e/parse-coords "2:150:7")]
      (is (= 2 (:galaxy c)))
      (is (= 150 (:solar-system c)))
      (is (= 7 (:planet c))))

    (let [c (e/parse-coords "[1:240:3] moon")]
      (is (= :moon (:coords-type c))))))

(deftest test-coords-comparison
  (testing "Comparing coordinates"
    (let [c1 (e/coords 1 240 3)
          c2 (e/coords 1 240 3)
          c3 (e/coords 1 240 4)]
      (is (= 0 (.compareTo c1 c2)))
      (is (< (.compareTo c1 c3) 0))
      (is (> (.compareTo c3 c1) 0)))))

(deftest test-distance-calculation
  (testing "Distance between coordinates"
    ;; Same position
    (let [c1 (e/coords 1 240 3)
          c2 (e/coords 1 240 3)]
      (is (= 5 (e/distance-between c1 c2))))

    ;; Same system, different planet
    (let [c1 (e/coords 1 240 3)
          c2 (e/coords 1 240 5)]
      (is (= 1010 (e/distance-between c1 c2))))

    ;; Different system, same galaxy
    (let [c1 (e/coords 1 240 3)
          c2 (e/coords 1 245 3)]
      (is (= 3175 (e/distance-between c1 c2))))

    ;; Different galaxy
    (let [c1 (e/coords 1 240 3)
          c2 (e/coords 2 240 3)]
      (is (= 20000 (e/distance-between c1 c2))))))

(deftest test-flight-time
  (testing "Flight time calculation"
    (let [c1 (e/coords 1 240 3)
          c2 (e/coords 1 245 3)
          duration (e/flight-time-to c1 c2 5000 100)]
      (is (instance? Duration duration))
      (is (pos? (.getSeconds duration))))))

(deftest test-moon-detection
  (testing "Moon coordinate detection"
    (let [planet (e/coords 1 240 3 :planet)
          moon (e/coords 1 240 3 :moon)]
      (is (false? (e/moon? planet)))
      (is (true? (e/moon? moon))))))

;; ============================================================================
;; Ship/Building/Defense/Research Tests
;; ============================================================================

(deftest test-ship-creation
  (testing "Creating a ship"
    (let [ship (e/->Ship "smallCargo" 202 (e/resources 2000 2000 0) 5000 20 "Small Cargo")]
      (is (= "smallCargo" (e/get-name ship)))
      (is (= 202 (e/get-code ship)))
      (is (= 5000 (:capacity ship)))
      (is (= 20 (:consumption ship))))))

(deftest test-building-creation
  (testing "Creating a building"
    (let [building (e/->Building "metalMine" 1 (e/resources 60 15 0) "Metal Mine")]
      (is (= "metalMine" (e/get-name building)))
      (is (= 1 (e/get-code building))))))

;; ============================================================================
;; Player and Planet Tests
;; ============================================================================

(deftest test-player-creation
  (testing "Creating players"
    (let [player (e/player "TestPlayer")]
      (is (= "TestPlayer" (:name player)))
      (is (empty? (:colonies player))))

    (let [player (e/player "TestPlayer" "TestAlliance")]
      (is (= "TestAlliance" (:alliance player))))))

(deftest test-enemy-player
  (testing "Creating enemy player"
    (let [enemy (e/enemy-player "BadGuy")]
      (is (= "BadGuy" (:name enemy)))
      (is (false? (:is-inactive enemy))))))

(deftest test-planet-creation
  (testing "Creating planets"
    (let [coords (e/coords 1 240 3)
          owner (e/player "Owner")
          planet (e/planet coords owner "Home")]
      (is (= coords (:coords planet)))
      (is (= owner (:owner planet)))
      (is (= "Home" (:name planet))))))

(deftest test-enemy-planet
  (testing "Creating enemy planet"
    (let [coords (e/coords 1 240 3)
          owner (e/enemy-player "Enemy")
          planet (e/enemy-planet coords owner)]
      (is (= coords (:coords planet)))
      (is (false? (:has-moon planet)))
      (is (false? (:has-debris planet)))
      (is (empty? (:espionage-history planet))))))

;; ============================================================================
;; Espionage Report Tests
;; ============================================================================

(deftest test-espionage-report
  (testing "Creating espionage report"
    (let [coords (e/coords 1 240 3)
          report (e/espionage-report "12345" (t/now) coords "<html>")]
      (is (= "12345" (:code report)))
      (is (= coords (:coords report)))
      (is (= 0 (:probes-sent report))))))

(deftest test-detail-level
  (testing "Espionage report detail levels"
    (let [basic-report (e/espionage-report "1" (t/now) (e/coords 1 1 1) "")
          fleet-report (assoc basic-report :fleet {"smallCargo" 10})
          defense-report (assoc fleet-report :defense {"rocketLauncher" 5})
          buildings-report (assoc defense-report :buildings {"metalMine" 20})
          research-report (assoc buildings-report :research {"espionageTechnology" 8})]
      (is (= (:resources e/detail-levels) (e/get-detail-level basic-report)))
      (is (= (:fleet e/detail-levels) (e/get-detail-level fleet-report)))
      (is (= (:defense e/detail-levels) (e/get-detail-level defense-report)))
      (is (= (:buildings e/detail-levels) (e/get-detail-level buildings-report)))
      (is (= (:research e/detail-levels) (e/get-detail-level research-report))))))

(deftest test-has-fleet
  (testing "Fleet detection in reports"
    (let [no-fleet (e/espionage-report "1" (t/now) (e/coords 1 1 1) "")
          empty-fleet (assoc no-fleet :fleet {})
          has-fleet (assoc no-fleet :fleet {"smallCargo" 5})]
      (is (true? (e/has-fleet? no-fleet))) ; nil = unknown = treat as true
      (is (false? (e/has-fleet? empty-fleet)))
      (is (true? (e/has-fleet? has-fleet))))))

(deftest test-has-defense
  (testing "Defense detection in reports"
    (let [no-defense (e/espionage-report "1" (t/now) (e/coords 1 1 1) "")
          empty-defense (assoc no-defense :defense {})
          has-defense (assoc no-defense :defense {"rocketLauncher" 10})]
      (is (true? (e/has-defense? no-defense)))
      (is (false? (e/has-defense? empty-defense)))
      (is (true? (e/has-defense? has-defense))))))

(deftest test-defended
  (testing "Planet defense status"
    (let [undefended (e/espionage-report "1" (t/now) (e/coords 1 1 1) "")
          _ (assoc undefended :fleet {} :defense {})
          defended-fleet (assoc undefended :fleet {"smallCargo" 5})
          defended-defense (assoc undefended :defense {"rocketLauncher" 10})]
      (is (true? (e/defended? defended-fleet)))
      (is (true? (e/defended? defended-defense))))))

;; ============================================================================
;; Mission Tests
;; ============================================================================

(deftest test-mission-creation
  (testing "Creating a mission"
    (let [source (e/own-planet (e/coords 1 240 3) (e/own-player) "Home")
          target (e/enemy-planet (e/coords 1 240 5) (e/enemy-player "Enemy"))
          fleet {"smallCargo" 50}
          resources (e/resources 10000 5000 2500)
          mission (e/mission :attack source target fleet resources 100)]
      (is (= :attack (:mission-type mission)))
      (is (= source (:source-planet mission)))
      (is (= target (:target-planet mission)))
      (is (= fleet (:fleet mission)))
      (is (= 100 (:speed-percentage mission))))))

(deftest test-mark-launched
  (testing "Marking mission as launched"
    (let [source (e/own-planet (e/coords 1 240 3) (e/own-player) "Home")
          target (e/enemy-planet (e/coords 1 240 5) (e/enemy-player "Enemy"))
          mission (e/mission :attack source target {"smallCargo" 50} (e/resources 0 0 0) 100)
          launch-time (t/now)
          flight-duration (t/minutes 5)
          launched (e/mark-launched mission launch-time flight-duration)]
      (is (some? (:launch-time launched)))
      (is (some? (:arrival-time launched)))
      (is (some? (:return-time launched)))
      (is (pos? (:distance launched))))))

;; ============================================================================
;; Get Best Report Tests
;; ============================================================================

(deftest test-get-best-espionage-report
  (testing "Finding best espionage report"
    (let [coords (e/coords 1 240 3)
          now (t/now)
          old-resources (e/espionage-report "1" (t/minus now (t/days 5)) coords "")
          old-fleet (assoc old-resources :fleet {"smallCargo" 10})
          new-resources (e/espionage-report "2" now coords "")
          new-defense (assoc new-resources :defense {"rocketLauncher" 5})
          reports [old-resources old-fleet new-resources new-defense]]

      ;; Should pick new-defense (highest detail level and most recent)
      (let [best (e/get-best-espionage-report reports)]
        (is (= "2" (:code best)))
        (is (some? (:defense best)))))))

(run-tests)
