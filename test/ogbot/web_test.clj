(ns ogbot.web-test
  (:require [clojure.test :refer :all]
            [ogbot.web :as web]
            [ogbot.entities :as e]
            [ogbot.constants :as constants]))

;; ============================================================================
;; Launch Mission Helper Functions Tests
;; ============================================================================

(deftest test-build-fleet-form
  (testing "Building fleet form data"
    (let [mission-fleet {"smallCargo" 50 "largeCargo" 25}
          form (web/build-fleet-form mission-fleet)]
      ;; Small cargo code is 202
      (is (= "50" (get form "am202")))
      ;; Large cargo code is 203
      (is (= "25" (get form "am203"))))))

(deftest test-build-destination-form
  (testing "Building destination form data"
    (let [coords (e/coords 2 150 7)
          target-planet (e/enemy-planet coords (e/enemy-player "Enemy"))
          mission (e/mission :attack
                            (e/own-planet (e/coords 1 1 1) (e/own-player) "Home")
                            target-planet
                            {"smallCargo" 10}
                            (e/resources 0 0 0)
                            100)
          form (web/build-destination-form mission)]
      (is (= "2" (:galaxy form)))
      (is (= "150" (:system form)))
      (is (= "7" (:position form)))
      (is (= "1" (:type form))) ; planet type
      (is (= "10" (:speed form)))))) ; 100% / 10

(deftest test-extract-flight-time
  (testing "Extracting flight time from HTML"
    (let [html-with-time "Duration: <span id='duration'>02:15:30</span>"
          flight-time (web/extract-flight-time html-with-time)]
      ;; 2 hours + 15 mins + 30 secs = 8130 seconds = 8130000 milliseconds
      (is (= 8130000 flight-time)))

    (let [html-without-time "No time here"
          flight-time (web/extract-flight-time html-without-time)]
      (is (nil? flight-time)))))

(deftest test-build-mission-form
  (testing "Building mission form data"
    (let [resources (e/resources 10000 5000 2500)
          mission (e/mission :attack
                            (e/own-planet (e/coords 1 1 1) (e/own-player) "Home")
                            (e/enemy-planet (e/coords 1 1 2) (e/enemy-player "Enemy"))
                            {"smallCargo" 10}
                            resources
                            100)
          form (web/build-mission-form mission)]
      ;; Attack mission type code is 1
      (is (= "1" (:mission form)))
      (is (= "10000" (:resource1 form)))
      (is (= "5000" (:resource2 form)))
      (is (= "2500" (:resource3 form))))))

(deftest test-check-mission-result
  (testing "Checking mission submission results"
    ;; Test generic failure
    (let [result (web/check-mission-result
                  "Fleet could not be sent"
                  {"fleetCouldNotBeSent" "could not be sent"}
                  {}
                  {})]
      (is (= :retry (:status result))))

    ;; Test success
    (let [result (web/check-mission-result
                  "<div class=\"success\">Fleet sent!</div>"
                  {}
                  {}
                  {})]
      (is (= :success (:status result))))

    ;; Test no success message
    (let [result (web/check-mission-result
                  "Some other message"
                  {}
                  {}
                  {})]
      (is (= :retry (:status result))))))

(deftest test-validate-fleet-availability
  (testing "Fleet availability validation"
    ;; Test with enough ships
    (let [available-fleet {"smallCargo" 100 "largeCargo" 50}
          mission-fleet {"smallCargo" 50}]
      (is (nil? (web/validate-fleet-availability
                 available-fleet
                 mission-fleet
                 true
                 10
                 0))))

    ;; Test with not enough fleet slots - should throw
    (is (thrown? Exception
                (web/validate-fleet-availability
                 {"smallCargo" 100}
                 {"smallCargo" 50}
                 true
                 0  ; free slots
                 1))) ; slots to reserve

    ;; Test with no ships available - should throw
    (is (thrown? Exception
                (web/validate-fleet-availability
                 {"smallCargo" 0}
                 {"smallCargo" 50}
                 true
                 10
                 0)))

    ;; Test with not enough ships when abort-if-not-enough is true - should throw
    (is (thrown? Exception
                (web/validate-fleet-availability
                 {"smallCargo" 25}
                 {"smallCargo" 50}
                 true  ; abort if not enough
                 10
                 0)))

    ;; Test with not enough ships when abort-if-not-enough is false - should not throw
    (is (nil? (web/validate-fleet-availability
               {"smallCargo" 25}
               {"smallCargo" 50}
               false  ; don't abort if not enough
               10
               0)))))

;; ============================================================================
;; Coordinate and Distance Tests
;; ============================================================================

(deftest test-coords-to-string
  (testing "Coordinate string representation"
    (let [coords (e/coords 1 240 3)]
      (is (= "[1:240:3]" (str coords))))))

;; ============================================================================
;; Mission Type Constants Tests
;; ============================================================================

(deftest test-mission-types
  (testing "Mission type codes"
    (is (= 1 (get e/mission-types :attack)))
    (is (= 3 (get e/mission-types :transport)))
    (is (= 6 (get e/mission-types :spy)))))

;; ============================================================================
;; Coord Types Tests
;; ============================================================================

(deftest test-coord-types
  (testing "Coordinate type codes"
    (is (= 1 (get e/coord-types :planet)))
    (is (= 2 (get e/coord-types :debris)))
    (is (= 3 (get e/coord-types :moon)))))

(run-tests)
