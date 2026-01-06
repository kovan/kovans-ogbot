(ns ogbot.db
  "SQLite database for planet storage"
  (:require [clojure.java.jdbc :as jdbc]
            [ogbot.entities :as e])
  (:import [java.util.concurrent.locks ReentrantLock]))

(def ^:private db-lock (ReentrantLock.))

(defn create-db-spec [db-file]
  {:classname "org.sqlite.JDBC"
   :subprotocol "sqlite"
   :subname db-file})

(defn init-planet-db!
  "Initialize planet database with proper SQL schema"
  [db-spec]
  (jdbc/execute! db-spec
                 ["CREATE TABLE IF NOT EXISTS planets (
                    coords TEXT PRIMARY KEY,
                    galaxy INTEGER NOT NULL,
                    solar_system INTEGER NOT NULL,
                    planet INTEGER NOT NULL,
                    coords_type INTEGER NOT NULL,
                    name TEXT,
                    owner_name TEXT NOT NULL,
                    owner_alliance TEXT,
                    owner_is_inactive INTEGER NOT NULL,
                    has_moon INTEGER NOT NULL,
                    has_debris INTEGER NOT NULL,
                    last_updated INTEGER NOT NULL
                  )"]))

(defn with-lock [f]
  (.lock db-lock)
  (try
    (f)
    (finally
      (.unlock db-lock))))

(defn planet->row
  "Convert planet entity to database row"
  [planet]
  (let [coords (:coords planet)
        owner (:owner planet)]
    {:coords (str coords)
     :galaxy (:galaxy coords)
     :solar_system (:solar-system coords)
     :planet (:planet coords)
     :coords_type (:coords-type coords)
     :name (or (:name planet) "")
     :owner_name (:name owner)
     :owner_alliance (or (:alliance owner) "")
     :owner_is_inactive (if (:is-inactive owner) 1 0)
     :has_moon (if (:has-moon planet) 1 0)
     :has_debris (if (:has-debris planet) 1 0)
     :last_updated (System/currentTimeMillis)}))

(defn row->planet
  "Convert database row to planet entity"
  [row]
  (let [coords (e/coords (:galaxy row)
                         (:solar_system row)
                         (:planet row))
        owner (e/->EnemyPlayer (:owner_name row)
                               (:owner_alliance row)
                               []
                               0
                               0
                               nil
                               (= 1 (:owner_is_inactive row)))]
    (e/->EnemyPlanet coords
                     owner
                     (:name row)
                     (= 1 (:has_moon row))
                     (= 1 (:has_debris row))
                     []
                     []
                     nil)))

(defn write-planet!
  "Write a single planet to database"
  [db-spec planet]
  (with-lock
    (fn []
      (let [row (planet->row planet)]
        (jdbc/execute! db-spec
                      ["INSERT OR REPLACE INTO planets
                        (coords, galaxy, solar_system, planet, coords_type, name,
                         owner_name, owner_alliance, owner_is_inactive,
                         has_moon, has_debris, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                       (:coords row)
                       (:galaxy row)
                       (:solar_system row)
                       (:planet row)
                       (:coords_type row)
                       (:name row)
                       (:owner_name row)
                       (:owner_alliance row)
                       (:owner_is_inactive row)
                       (:has_moon row)
                       (:has_debris row)
                       (:last_updated row)])))))

(defn write-many-planets!
  "Write multiple planets to database in a transaction"
  [db-spec planets]
  (with-lock
    (fn []
      (jdbc/with-db-transaction [tx db-spec]
        (doseq [planet planets]
          (let [row (planet->row planet)]
            (jdbc/execute! tx
                          ["INSERT OR REPLACE INTO planets
                            (coords, galaxy, solar_system, planet, coords_type, name,
                             owner_name, owner_alliance, owner_is_inactive,
                             has_moon, has_debris, last_updated)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                           (:coords row)
                           (:galaxy row)
                           (:solar_system row)
                           (:planet row)
                           (:coords_type row)
                           (:name row)
                           (:owner_name row)
                           (:owner_alliance row)
                           (:owner_is_inactive row)
                           (:has_moon row)
                           (:has_debris row)
                           (:last_updated row)])))))))

(defn read-planet
  "Read a planet by coordinates string"
  [db-spec coords-str]
  (with-lock
    (fn []
      (when-let [row (first (jdbc/query db-spec
                                       ["SELECT * FROM planets WHERE coords = ?"
                                        coords-str]))]
        (row->planet row)))))

(defn read-all-planets
  "Read all planets from database"
  [db-spec]
  (with-lock
    (fn []
      (let [rows (jdbc/query db-spec ["SELECT * FROM planets"])]
        (mapv row->planet rows)))))

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
  "Save planet list to database"
  [db-spec ^PlanetList pl]
  (let [planets (vals (:planets pl))]
    (write-many-planets! db-spec planets)))

(defn load-planet-list
  "Load planet list from database"
  [db-spec]
  (try
    (let [planets (read-all-planets db-spec)]
      (create-planet-list planets))
    (catch Exception _
      (->PlanetList {}))))
