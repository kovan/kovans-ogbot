(ns ogbot.utils
  "Utility functions"
  (:require [clojure.string :as str])
  (:import [java.util Random]))

;; Exception types
(defn bot-error [msg]
  (ex-info msg {:type :bot-error}))

(defn bot-fatal-error [msg]
  (ex-info msg {:type :bot-fatal-error}))

(defn manually-terminated [msg]
  (ex-info msg {:type :manually-terminated}))

(defn fleet-send-error [msg]
  (ex-info msg {:type :fleet-send-error}))

(defn no-free-slots-error []
  (ex-info "No fleet slots available" {:type :no-free-slots}))

(defn not-enough-ships-error [all-fleet-available requested available]
  (ex-info (format "Requested: %s. Available: %s" requested available)
           {:type :not-enough-ships
            :all-fleet-available all-fleet-available
            :requested requested
            :available available}))

;; Thread messaging
(defrecord BotToGuiMsg [method-name args])
(defrecord GuiToBotMsg [type param])

(def gui-msg-types
  {:stop 0
   :pause 1
   :resume 2
   :attack-large-cargo 3
   :attack-small-cargo 4
   :spy 5})

;; Utility functions
(defn add-commas
  "Add thousand separators to a number"
  [n]
  (let [s (str n)
        len (count s)]
    (if (< len 4)
      s
      (str/join "," (reverse (map str/join (partition-all 3 (reverse s))))))))

(def ^Random rng (Random.))

(defn my-sleep
  "Sleep for a random amount of time between seconds and seconds+10"
  [seconds]
  (Thread/sleep (* 1000 (+ seconds (.nextInt rng 11)))))

(defn parse-time
  "Parse time string in HH:MM:SS format"
  [time-str]
  (let [[h m s] (str/split time-str #":")]
    {:hour (Integer/parseInt h)
     :minute (Integer/parseInt m)
     :second (Integer/parseInt s)}))

(defn parse-list
  "Parse comma-separated list from string"
  [list-str]
  (when (and list-str (not= list-str ""))
    (->> (str/split list-str #",")
         (map str/trim)
         (remove empty?)
         vec)))

(defn parse-dictionary
  "Parse dictionary string from INI file"
  [dict-str]
  (let [cleaned (-> dict-str
                    (str/replace "\n" "")
                    (str/replace "{" "")
                    (str/replace "}" "")
                    str/trim)]
    (if (empty? cleaned)
      {}
      (into {}
            (for [pair (str/split cleaned #",")
                  :let [[k v] (str/split pair #":" 2)]
                  :when (and k v)]
              [(str/trim k) (str/trim (str/replace v #"['\"]" ""))])))))

(defn parse-list-of-dictionaries
  "Parse list of dictionaries from INI file"
  [dict-list-str]
  (let [cleaned (-> dict-list-str
                    (str/replace "\n" "")
                    (str/trim))]
    (if (or (empty? cleaned) (= cleaned "[]"))
      []
      (->> (str/split cleaned #"\}")
           (map str/trim)
           (remove empty?)
           (map parse-dictionary)
           vec))))
