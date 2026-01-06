(ns ogbot.db
  "SQLite database for planet storage"
  (:require [clojure.java.jdbc :as jdbc]
            [clojure.edn :as edn]
            [ogbot.entities :as entities])
  (:import [java.util.concurrent.locks ReentrantLock]))

(def ^:private db-lock (ReentrantLock.))

(defn create-db-spec [db-file]
  {:classname "org.sqlite.JDBC"
   :subprotocol "sqlite"
   :subname db-file})

(defn init-planet-db!
  "Initialize planet database with schema"
  [db-spec]
  (jdbc/execute! db-spec
                 ["CREATE TABLE IF NOT EXISTS planets (
                    coords TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    last_updated INTEGER NOT NULL
                  )"]))

(defn with-lock [f]
  (.lock db-lock)
  (try
    (f)
    (finally
      (.unlock db-lock))))

(defn serialize-planet
  "Serialize planet to EDN string"
  [planet]
  (pr-str planet))

(defn deserialize-planet
  "Deserialize planet from EDN string"
  [edn-str]
  (edn/read-string edn-str))

(defn write-planet!
  "Write a single planet to database"
  [db-spec planet]
  (with-lock
    (fn []
      (let [coords-str (str (:coords planet))
            data (serialize-planet planet)
            now (System/currentTimeMillis)]
        (jdbc/execute! db-spec
                      ["INSERT OR REPLACE INTO planets (coords, data, last_updated)
                        VALUES (?, ?, ?)"
                       coords-str data now])))))

(defn write-many-planets!
  "Write multiple planets to database in a transaction"
  [db-spec planets]
  (with-lock
    (fn []
      (jdbc/with-db-transaction [tx db-spec]
        (let [now (System/currentTimeMillis)]
          (doseq [planet planets
                  :let [coords-str (str (:coords planet))
                        data (serialize-planet planet)]]
            (jdbc/execute! tx
                          ["INSERT OR REPLACE INTO planets (coords, data, last_updated)
                            VALUES (?, ?, ?)"
                           coords-str data now])))))))

(defn read-planet
  "Read a planet by coordinates string"
  [db-spec coords-str]
  (with-lock
    (fn []
      (when-let [row (first (jdbc/query db-spec
                                       ["SELECT data FROM planets WHERE coords = ?"
                                        coords-str]))]
        (deserialize-planet (:data row))))))

(defn read-all-planets
  "Read all planets from database"
  [db-spec]
  (with-lock
    (fn []
      (let [rows (jdbc/query db-spec ["SELECT data FROM planets"])]
        (mapv #(deserialize-planet (:data %)) rows)))))

(defn search-planets
  "Search planets matching a predicate function"
  [db-spec predicate]
  (with-lock
    (fn []
      (let [all-planets (read-all-planets db-spec)]
        (filterv predicate all-planets)))))

(defn delete-planet!
  "Delete a planet by coordinates"
  [db-spec coords-str]
  (with-lock
    (fn []
      (jdbc/execute! db-spec
                    ["DELETE FROM planets WHERE coords = ?" coords-str]))))

(defn clear-db!
  "Clear all planets from database"
  [db-spec]
  (with-lock
    (fn []
      (jdbc/execute! db-spec ["DELETE FROM planets"]))))

(defn planet-count
  "Get total count of planets in database"
  [db-spec]
  (with-lock
    (fn []
      (-> (jdbc/query db-spec ["SELECT COUNT(*) as count FROM planets"])
          first
          :count))))

;; Planet list management (in-memory with disk persistence)
(defrecord PlanetList [planets])

(defn create-planet-list
  "Create a new planet list"
  ([] (->PlanetList {}))
  ([planets-vec]
   (->PlanetList
    (into {} (map (fn [p] [(str (:coords p)) p]) planets-vec)))))

(defn add-planet
  "Add a planet to the list"
  [^PlanetList pl planet]
  (assoc-in pl [:planets (str (:coords planet))] planet))

(defn save-planet-list!
  "Save planet list to EDN file"
  [^PlanetList pl file-path]
  (spit file-path (pr-str (:planets pl))))

(defn load-planet-list
  "Load planet list from EDN file"
  [file-path]
  (try
    (let [data (edn/read-string (slurp file-path))]
      (->PlanetList data))
    (catch Exception _
      (->PlanetList {}))))
