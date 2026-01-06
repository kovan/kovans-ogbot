(ns ogbot.config
  "Configuration management using INI files"
  (:require [clojure.java.io :as io]
            [clojure.string :as str]
            [ogbot.utils :as utils]
            [ogbot.entities :as entities])
  (:import [java.io File]))

(defn load-ini-file
  "Load INI file and return map of key-value pairs"
  [file-path]
  (when-not (.exists (io/file file-path))
    (throw (utils/bot-fatal-error (str "File " file-path " does not exist"))))

  (let [lines (str/split-lines (slurp file-path))
        config (atom {})]
    (doseq [line lines
            :let [trimmed (str/trim line)]
            :when (and (not (empty? trimmed))
                      (not (str/starts-with? trimmed ";"))
                      (not (str/starts-with? trimmed "#"))
                      (not (str/starts-with? trimmed "[")))
            :let [[k v] (str/split trimmed #"=" 2)]
            :when (and k v)]
      (swap! config assoc (str/trim k) (str/trim v)))
    @config))

(defn save-ini-file
  "Save configuration map to INI file"
  [file-path config-map]
  (with-open [w (io/writer file-path)]
    (.write w "[options]\n")
    (doseq [[k v] config-map]
      (.write w (format "%s = %s\n" k v)))))

(def default-config
  {:username ""
   :password ""
   :webpage "uni1.ogame.org"
   :attack-radius 10
   :slots-to-reserve 0
   :attacking-ship "smallCargo"
   :source-planets ""
   :players-to-avoid ""
   :probes-to-send 1
   :alliances-to-avoid ""
   :systems-per-galaxy 499
   :proxy ""
   :user-agent "Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1)"
   :rentability-formula "(metal + 1.5 * crystal + 3 * deuterium) / flightTime"
   :pre-midnight-pause-time "22:00:00"
   :inactives-appearance-time "0:06:00"
   :deuterium-source-planet ""
   :max-probes 15
   :wait-between-attack-checks 45
   :fleet-point "[{}]"
   :building-point "[{}]"
   :defense-point "[{}]"
   :research-point "[{}]"})

(defn kebab-to-camel [k]
  (-> k
      name
      (str/replace "-" "")))

(defn load-bot-configuration
  "Load bot configuration from file with validation"
  [file-path]
  (let [raw-config (merge default-config (load-ini-file file-path))
        config (atom {})]

    ;; Convert keys from INI format to kebab-case
    (doseq [[k v] raw-config]
      (let [kebab-key (keyword (str/replace k #"(?<!^)(?=[A-Z])" "-"))]
        (swap! config assoc kebab-key v)))

    ;; Parse special fields
    (swap! config update :pre-midnight-pause-time utils/parse-time)
    (swap! config update :inactives-appearance-time utils/parse-time)
    (swap! config update :webpage #(str/replace % "http://" ""))
    (swap! config update :proxy #(str/replace % "http://" ""))
    (swap! config update :building-point utils/parse-list-of-dictionaries)
    (swap! config update :fleet-point utils/parse-list-of-dictionaries)
    (swap! config update :defense-point utils/parse-list-of-dictionaries)
    (swap! config update :research-point utils/parse-list-of-dictionaries)
    (swap! config update :players-to-avoid utils/parse-list)
    (swap! config update :alliances-to-avoid utils/parse-list)
    (swap! config update :source-planets utils/parse-list)

    ;; Convert source planets to Coords objects
    (when-let [source-planets (:source-planets @config)]
      (swap! config assoc :source-planets
             (mapv entities/parse-coords source-planets)))

    ;; Convert deuterium source planet to Coords
    (when-let [deut-planet (:deuterium-source-planet @config)]
      (when (not (empty? deut-planet))
        (try
          (swap! config assoc :deuterium-source-planet
                 (entities/parse-coords deut-planet))
          (catch Exception _ nil))))

    ;; Validate required fields
    (when (or (empty? (:username @config))
              (empty? (:password @config))
              (empty? (:webpage @config)))
      (throw (utils/bot-error "Empty username, password or webpage.")))

    ;; Validate attacking ship
    (when-not (#{"smallCargo" "largeCargo"} (:attacking-ship @config))
      (throw (utils/bot-error "Invalid attacking ship type.")))

    ;; Validate rentability formula
    (try
      (let [metal 1 crystal 1 deuterium 1 flight-time 1]
        (eval (read-string (:rentability-formula @config))))
      (catch Exception e
        (throw (utils/bot-error (str "Invalid rentability formula: " (.getMessage e))))))

    @config))

(defn load-translations
  "Load all translation files from languages directory"
  []
  (let [translations (atom {})]
    (doseq [^File file (.listFiles (io/file "languages"))
            :when (and (.isFile file)
                      (str/ends-with? (.getName file) ".ini")
                      (not (str/starts-with? (.getName file) ".")))]
      (try
        (let [translation (load-ini-file (.getPath file))
              lang-code (get translation "languageCode")]
          (swap! translations assoc lang-code translation))
        (catch Exception e
          (throw (utils/bot-error
                  (str "Malformed language file (" (.getName file) "): "
                       (.getMessage e)))))))
    @translations))

(defrecord ResourceSimulation [base-resources metal-mine crystal-mine
                                deuterium-synthesizer simulation-start])

(defn create-resource-simulation
  [base-resources mines]
  (->ResourceSimulation
   base-resources
   (or (get mines "metalMine") 16)
   (or (get mines "crystalMine") 14)
   (or (get mines "deuteriumSynthesizer") 9)
   (System/currentTimeMillis)))

(defn calculate-production
  "Calculate resource production over time interval (in seconds)"
  [^ResourceSimulation sim time-interval-seconds]
  (let [production-hours (/ time-interval-seconds 3600.0)
        metal (* 30 (:metal-mine sim)
                (Math/pow 1.1 (:metal-mine sim))
                production-hours)
        crystal (* 20 (:crystal-mine sim)
                  (Math/pow 1.1 (:crystal-mine sim))
                  production-hours)
        deuterium (* 10 (:deuterium-synthesizer sim)
                    (Math/pow 1.1 (:deuterium-synthesizer sim))
                    production-hours
                    (+ (* -0.002 60) 1.28))] ; 60 = planet temp at position 7
    (entities/mul-resources
     (entities/resources (long metal) (long crystal) (long deuterium))
     0.95)))

(defn get-simulated-resources
  "Get current simulated resources based on production"
  [^ResourceSimulation sim]
  (let [elapsed-ms (- (System/currentTimeMillis) (:simulation-start sim))
        elapsed-seconds (/ elapsed-ms 1000.0)
        produced (calculate-production sim elapsed-seconds)]
    (entities/add-resources (:base-resources sim) produced)))
