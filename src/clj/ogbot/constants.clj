(ns ogbot.constants
  "Game constants and in-game entity definitions"
  (:require [ogbot.entities :refer [resources ->Ship ->Building ->Defense ->Research]]))

(def supported-ogame-version 1.1)

(def file-paths
  {:config "files/config/config.ini"
   :botstate "files/botdata/bot.state.edn"
   :webstate "files/botdata/webadapter.state.edn"
   :planetdb "files/botdata/planets.db"
   :gamedata "files/botdata/gamedata.edn"
   :newinactives "files/botdata/newinactives.edn"
   :cookies "files/botdata/cookies.txt"
   :log "files/log/ogbot.log"})

;; All in-game types with their codes and costs
(def ingame-types
  [(->Building "metalMine" 1 (resources 60 15 0) "")
   (->Building "crystalMine" 2 (resources 48 24 0) "")
   (->Building "deuteriumSynthesizer" 3 (resources 225 75 0) "")
   (->Building "solarPlant" 4 (resources 75 30 0) "")
   (->Building "fusionReactor" 12 (resources 900 360 180) "")
   (->Building "roboticsFactory" 14 (resources 400 120 200) "")
   (->Building "naniteFactory" 15 (resources 1000000 500000 100000) "")
   (->Building "shipyard" 21 (resources 400 200 100) "")
   (->Building "metalStorage" 22 (resources 2000 0 0) "")
   (->Building "crystalStorage" 23 (resources 2000 1000 0) "")
   (->Building "deuteriumTank" 24 (resources 2000 2000 0) "")
   (->Building "researchLab" 31 (resources 200 400 200) "")
   (->Building "terraformer" 33 (resources 0 50000 100000) "")
   (->Building "allianceDepot" 34 (resources 20000 40000 0) "")
   (->Building "lunarBase" 41 (resources 20000 40000 20000) "")
   (->Building "sensorPhalanx" 42 (resources 20000 40000 20000) "")
   (->Building "jumpGate" 43 (resources 2000000 4000000 2000000) "")
   (->Building "missileSilo" 44 (resources 20000 20000 1000) "")

   (->Research "espionageTechnology" 106 (resources 200 1000 200) "")
   (->Research "computerTechnology" 108 (resources 0 400 600) "")
   (->Research "weaponsTechnology" 109 (resources 800 200 0) "")
   (->Research "shieldingTechnology" 110 (resources 200 600 0) "")
   (->Research "armourTechnology" 111 (resources 1000 0 0) "")
   (->Research "energyTechnology" 113 (resources 0 900 400) "")
   (->Research "hyperspaceTechnology" 114 (resources 0 4000 2000) "")
   (->Research "combustionDrive" 115 (resources 400 0 600) "")
   (->Research "impulseDrive" 117 (resources 2000 4000 600) "")
   (->Research "hyperspaceDrive" 118 (resources 10000 20000 6000) "")
   (->Research "laserTechnology" 120 (resources 200 100 0) "")
   (->Research "ionTechnology" 121 (resources 1000 300 100) "")
   (->Research "plasmaTechnology" 122 (resources 2000 4000 100) "")
   (->Research "intergalacticResearchNetwork" 123 (resources 240000 400000 160000) "")
   (->Research "astrophysics" 124 (resources 4000 8000 4000) "")
   (->Research "gravitonTechnology" 199 (resources 0 0 0) "")

   (->Ship "smallCargo" 202 (resources 2000 2000 0) 5000 20 "")
   (->Ship "largeCargo" 203 (resources 6000 6000 0) 25000 50 "")
   (->Ship "lightFighter" 204 (resources 3000 1000 0) 50 20 "")
   (->Ship "heavyFighter" 205 (resources 6000 4000 0) 100 75 "")
   (->Ship "cruiser" 206 (resources 20000 7000 2000) 800 300 "")
   (->Ship "battleShip" 207 (resources 45000 15000 0) 1500 500 "")
   (->Ship "colonyShip" 208 (resources 10000 20000 10000) 7500 1000 "")
   (->Ship "recycler" 209 (resources 10000 6000 2000) 20000 300 "")
   (->Ship "espionageProbe" 210 (resources 0 1000 0) 1 1 "")
   (->Ship "bomber" 211 (resources 50000 25000 15000) 500 1000 "")
   (->Ship "solarSatellite" 212 (resources 0 2000 500) 0 0 "")
   (->Ship "destroyer" 213 (resources 60000 50000 15000) 2000 1000 "")
   (->Ship "deathStar" 214 (resources 5000000 4000000 1000000) 1000000 1 "")
   (->Ship "battlecruiser" 215 (resources 30000 40000 15000) 750 250 "")

   (->Defense "rocketLauncher" 401 (resources 2000 0 0) "")
   (->Defense "lightLaser" 402 (resources 1500 500 0) "")
   (->Defense "heavyLaser" 403 (resources 6000 2000 0) "")
   (->Defense "gaussCannon" 404 (resources 20000 15000 2000) "")
   (->Defense "ionCannon" 405 (resources 2000 6000 0) "")
   (->Defense "plasmaTurret" 406 (resources 50000 50000 30000) "")
   (->Defense "smallShieldDome" 407 (resources 10000 10000 0) "")
   (->Defense "largeShieldDome" 408 (resources 50000 50000 0) "")
   (->Defense "antiBallisticMissile" 502 (resources 8000 0 2000) "")
   (->Defense "interplanetaryMissile" 503 (resources 12500 2500 10000) "")])

;; Lookup maps for quick access
(def ingame-types-by-name
  (into {} (map (fn [t] [(:name t) t]) ingame-types)))

(def ingame-types-by-code
  (into {} (map (fn [t] [(:code t) t]) ingame-types)))

;; Helper functions
(defn get-by-name [name]
  (get ingame-types-by-name name))

(defn get-by-code [code]
  (get ingame-types-by-code code))
