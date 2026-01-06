(ns ogbot.constants-test
  (:require [clojure.test :refer :all]
            [ogbot.constants :as c]
            [ogbot.entities :as e]))

(deftest test-supported-version
  (testing "Supported OGame version"
    (is (number? c/supported-ogame-version))
    (is (pos? c/supported-ogame-version))))

(deftest test-file-paths
  (testing "File paths configuration"
    (is (map? c/file-paths))
    (is (contains? c/file-paths :config))
    (is (contains? c/file-paths :planetdb))
    (is (contains? c/file-paths :log))
    (is (string? (:config c/file-paths)))))

(deftest test-ingame-types-populated
  (testing "In-game types list"
    (is (vector? c/ingame-types))
    (is (pos? (count c/ingame-types)))
    (is (> (count c/ingame-types) 50)))) ; Should have many types

(deftest test-ships-exist
  (testing "Ships in ingame types"
    (let [ships (filter #(instance? ogbot.entities.Ship %) c/ingame-types)]
      (is (pos? (count ships)))
      (is (some #(= "smallCargo" (:name %)) ships))
      (is (some #(= "largeCargo" (:name %)) ships))
      (is (some #(= "espionageProbe" (:name %)) ships)))))

(deftest test-buildings-exist
  (testing "Buildings in ingame types"
    (let [buildings (filter #(instance? ogbot.entities.Building %) c/ingame-types)]
      (is (pos? (count buildings)))
      (is (some #(= "metalMine" (:name %)) buildings))
      (is (some #(= "crystalMine" (:name %)) buildings))
      (is (some #(= "shipyard" (:name %)) buildings)))))

(deftest test-defense-exist
  (testing "Defense in ingame types"
    (let [defenses (filter #(instance? ogbot.entities.Defense %) c/ingame-types)]
      (is (pos? (count defenses)))
      (is (some #(= "rocketLauncher" (:name %)) defenses))
      (is (some #(= "lightLaser" (:name %)) defenses)))))

(deftest test-research-exist
  (testing "Research in ingame types"
    (let [research (filter #(instance? ogbot.entities.Research %) c/ingame-types)]
      (is (pos? (count research)))
      (is (some #(= "espionageTechnology" (:name %)) research))
      (is (some #(= "combustionDrive" (:name %)) research)))))

(deftest test-lookup-by-name
  (testing "Looking up types by name"
    (is (map? c/ingame-types-by-name))

    (let [small-cargo (c/get-by-name "smallCargo")]
      (is (some? small-cargo))
      (is (= "smallCargo" (:name small-cargo)))
      (is (= 202 (:code small-cargo)))
      (is (instance? ogbot.entities.Ship small-cargo)))

    (let [metal-mine (c/get-by-name "metalMine")]
      (is (some? metal-mine))
      (is (= "metalMine" (:name metal-mine)))
      (is (= 1 (:code metal-mine))))

    (is (nil? (c/get-by-name "nonexistent")))))

(deftest test-lookup-by-code
  (testing "Looking up types by code"
    (is (map? c/ingame-types-by-code))

    (let [small-cargo (c/get-by-code 202)]
      (is (some? small-cargo))
      (is (= "smallCargo" (:name small-cargo))))

    (let [metal-mine (c/get-by-code 1)]
      (is (some? metal-mine))
      (is (= "metalMine" (:name metal-mine))))

    (is (nil? (c/get-by-code 99999)))))

(deftest test-ship-properties
  (testing "Ship-specific properties"
    (let [small-cargo (c/get-by-name "smallCargo")]
      (is (pos? (:capacity small-cargo)))
      (is (pos? (:consumption small-cargo)))
      (is (= 5000 (:capacity small-cargo))))

    (let [large-cargo (c/get-by-name "largeCargo")]
      (is (> (:capacity large-cargo) (:capacity (c/get-by-name "smallCargo")))))))

(deftest test-costs
  (testing "All types have costs"
    (doseq [type c/ingame-types]
      (is (some? (:cost type)))
      (is (instance? ogbot.entities.Resources (:cost type)))
      ;; At least one resource should be non-zero (except gravitonTechnology)
      (let [cost (:cost type)]
        (when-not (= "gravitonTechnology" (:name type))
          (is (or (pos? (:metal cost))
                  (pos? (:crystal cost))
                  (pos? (:deuterium cost)))))))))

(deftest test-unique-codes
  (testing "All type codes are unique"
    (let [codes (map :code c/ingame-types)]
      (is (= (count codes) (count (distinct codes)))))))

(deftest test-unique-names
  (testing "All type names are unique"
    (let [names (map :name c/ingame-types)]
      (is (= (count names) (count (distinct names)))))))

(run-tests)
