(ns ogbot.utils-test
  (:require [clojure.test :refer :all]
            [ogbot.utils :as u]))

(deftest test-add-commas
  (testing "Adding thousand separators"
    (is (= "1,000" (u/add-commas 1000)))
    (is (= "10,000" (u/add-commas 10000)))
    (is (= "100,000" (u/add-commas 100000)))
    (is (= "1,000,000" (u/add-commas 1000000)))
    (is (= "123" (u/add-commas 123)))
    (is (= "0" (u/add-commas 0)))))

(deftest test-parse-time
  (testing "Parsing time strings"
    (let [time (u/parse-time "14:30:45")]
      (is (= 14 (:hour time)))
      (is (= 30 (:minute time)))
      (is (= 45 (:second time))))

    (let [time (u/parse-time "00:00:00")]
      (is (= 0 (:hour time)))
      (is (= 0 (:minute time)))
      (is (= 0 (:second time))))))

(deftest test-parse-list
  (testing "Parsing comma-separated lists"
    (is (= ["a" "b" "c"] (u/parse-list "a, b, c")))
    (is (= ["player1" "player2"] (u/parse-list "player1,player2")))
    (is (empty? (u/parse-list "")))
    (is (nil? (u/parse-list nil)))
    (is (= ["single"] (u/parse-list "single")))))

(deftest test-parse-dictionary
  (testing "Parsing dictionary strings"
    (let [dict (u/parse-dictionary "key1:value1, key2:value2")]
      (is (= "value1" (get dict "key1")))
      (is (= "value2" (get dict "key2"))))

    (is (empty? (u/parse-dictionary "")))
    (is (empty? (u/parse-dictionary "{}")))))

(deftest test-parse-list-of-dictionaries
  (testing "Parsing list of dictionaries"
    (let [result (u/parse-list-of-dictionaries "[{a:1, b:2}, {c:3, d:4}]")]
      (is (= 2 (count result)))
      (is (map? (first result))))

    (is (empty? (u/parse-list-of-dictionaries "[]")))
    (is (empty? (u/parse-list-of-dictionaries "")))))

(deftest test-bot-error
  (testing "Bot error creation"
    (let [err (u/bot-error "Test error")]
      (is (instance? clojure.lang.ExceptionInfo err))
      (is (= "Test error" (.getMessage err)))
      (is (= :bot-error (:type (ex-data err)))))))

(deftest test-no-free-slots-error
  (testing "No free slots error"
    (let [err (u/no-free-slots-error)]
      (is (instance? clojure.lang.ExceptionInfo err))
      (is (.contains (.getMessage err) "fleet slots")))))

(deftest test-not-enough-ships-error
  (testing "Not enough ships error"
    (let [err (u/not-enough-ships-error {"smallCargo" 100} {"smallCargo" 50} {"smallCargo" 30})]
      (is (instance? clojure.lang.ExceptionInfo err))
      (is (.contains (.getMessage err) "Requested"))
      (is (.contains (.getMessage err) "Available")))))

(run-tests)
