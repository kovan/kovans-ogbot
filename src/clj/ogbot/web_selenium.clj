(ns ogbot.web-selenium
  "Selenium-based HTTP and HTML handling for OGame interaction"
  (:require [etaoin.api :as e]
            [clojure.string :as str]
            [clojure.java.io :as io]
            [clj-time.core :as t]
            [clj-time.format :as f]
            [clj-time.coerce :as tc]
            [ogbot.entities :as entities]
            [ogbot.constants :as constants]
            [ogbot.utils :as utils]
            [ogbot.config :as config])
  (:import [java.time Duration LocalDateTime]))

;; ============================================================================
;; Server Data
;; ============================================================================

(defrecord ServerData [charset version language time-delta])

(defn current-server-time [^ServerData server-data]
  (t/plus (t/now) (:time-delta server-data)))

;; ============================================================================
;; Web Adapter - Main Selenium Interface
;; ============================================================================

(defrecord WebAdapter [config translations translations-by-local-text
                       server-data session driver last-fetched-url
                       check-thread-msgs-fn event-mgr])

(defn log-and-print [event-mgr msg]
  (let [timestamped (str (f/unparse (f/formatter "yyyy-MM-dd HH:mm:ss") (t/now)) " " msg)]
    (println timestamped)))

(defn connection-error [event-mgr reason]
  (log-and-print event-mgr (str "** CONNECTION ERROR: " reason)))

(defn logged-in [event-mgr username session]
  (log-and-print event-mgr (str "Logged in with user " username)))

(defn activity-msg [event-mgr msg]
  (log-and-print event-mgr msg))

;; ============================================================================
;; Selenium Driver Management
;; ============================================================================

(defn create-driver
  "Create a Chrome WebDriver instance"
  []
  (e/chrome {:args ["--disable-blink-features=AutomationControlled"
                    "--disable-infobars"
                    "--window-size=1280,800"]
             :prefs {:credentials_enable_service false
                     :profile.password_manager_enabled false}}))

(defn quit-driver [adapter]
  (when-let [driver (:driver adapter)]
    (try
      (e/quit driver)
      (catch Exception _ nil))))

;; ============================================================================
;; URL Building
;; ============================================================================

(defn build-game-url
  "Build a URL for the game page"
  [adapter page params]
  (let [webpage (get-in adapter [:config :webpage])
        session (:session adapter)
        query-params (assoc params :session session)
        query-string (->> query-params
                          (map (fn [[k v]] (str (name k) "=" v)))
                          (str/join "&"))]
    (format "https://%s/game/%s?%s" webpage page query-string)))

;; ============================================================================
;; Page Navigation
;; ============================================================================

(defn wait-for-page-load
  "Wait for page to be fully loaded"
  [driver timeout-sec]
  (try
    (e/wait-visible driver {:css "#pageContent, #inhalt, .OGameClock"} {:timeout timeout-sec})
    true
    (catch Exception _
      false)))

(defn navigate-to-page
  "Navigate to a game page and wait for it to load"
  [adapter page params]
  (let [driver (:driver adapter)
        url (build-game-url adapter page params)]
    (try
      (e/go driver url)
      (wait-for-page-load driver 15)
      url
    (catch Exception e
      (connection-error (:event-mgr adapter) (.getMessage e))
      nil))))

(defn get-current-url [adapter]
  (e/get-url (:driver adapter)))

(defn get-page-source [adapter]
  (e/get-source (:driver adapter)))

(defn save-page-to-disk [adapter]
  (let [debug-dir (io/file "debug")]
    (when-not (.exists debug-dir)
      (.mkdir debug-dir))
    (let [files (seq (.listFiles debug-dir))
          file-count (count files)]
      (when (>= file-count 30)
        (let [sorted-files (sort-by #(.getName %) files)]
          (io/delete-file (first sorted-files) true))))
    (let [timestamp (f/unparse (f/formatter "yyyy-MM-dd_HH.mm.ss") (t/now))
          url (get-current-url adapter)
          php-part (or (second (re-find #"/(\w+\.php.*)" url)) "page")
          clean-php (-> php-part
                        (str/replace "?" ",")
                        (str/replace "&" ","))
          filename (format "debug/%s,%s.html" timestamp clean-php)]
      (spit filename
            (-> (get-page-source adapter)
                (str/replace "<script" "<noscript")
                (str/replace "</script>" "</noscript>"))))))

;; ============================================================================
;; Element Querying Helpers
;; ============================================================================

(defn query-element
  "Query a single element, returns nil if not found"
  [driver selector]
  (try
    (e/query driver selector)
    (catch Exception _ nil)))

(defn query-all-elements
  "Query all matching elements, returns empty vector if none found"
  [driver selector]
  (try
    (e/query-all driver selector)
    (catch Exception _ [])))

(defn get-element-text-safe
  "Get element text, returns empty string if element not found"
  [driver selector]
  (try
    (e/get-element-text driver selector)
    (catch Exception _ "")))

(defn get-element-attr-safe
  "Get element attribute, returns nil if element not found"
  [driver selector attr]
  (try
    (e/get-element-attr driver selector attr)
    (catch Exception _ nil)))

(defn element-exists?
  "Check if element exists on page"
  [driver selector]
  (try
    (e/exists? driver selector)
    (catch Exception _ false)))

(defn click-element
  "Click an element with optional wait"
  [driver selector]
  (try
    (e/wait-visible driver selector {:timeout 5})
    (e/click driver selector)
    true
    (catch Exception _ false)))

(defn fill-input
  "Fill an input field"
  [driver selector value]
  (try
    (e/wait-visible driver selector {:timeout 5})
    (e/clear driver selector)
    (e/fill driver selector (str value))
    true
    (catch Exception _ false)))

;; ============================================================================
;; Login
;; ============================================================================

(defn do-login!
  "Perform login using Selenium"
  [adapter]
  (let [driver (:driver adapter)
        config (:config adapter)
        webpage (:webpage config)
        ;; Navigate to the lobby login page
        base-domain (str/join "." (rest (str/split webpage #"\.")))
        lobby-url (str "https://lobby." base-domain "/")]

    (log-and-print (:event-mgr adapter) (str "Navigating to " lobby-url))
    (e/go driver lobby-url)
    (Thread/sleep 3000)

    ;; Wait for and click the login tab/button if needed
    (when (element-exists? driver {:css "[data-tab='login'], .tabsList .loginTab, #loginTab"})
      (click-element driver {:css "[data-tab='login'], .tabsList .loginTab, #loginTab"})
      (Thread/sleep 1000))

    ;; Fill login form
    (log-and-print (:event-mgr adapter) "Filling login form...")

    ;; Try different possible selectors for email/username field
    (let [email-selectors [{:css "input[name='email']"}
                           {:css "input[name='login']"}
                           {:css "input[type='email']"}
                           {:css "#usernameLogin"}
                           {:css ".loginForm input[type='text']"}]
          password-selectors [{:css "input[name='password']"}
                              {:css "input[type='password']"}
                              {:css "#passwordLogin"}
                              {:css ".loginForm input[type='password']"}]]

      ;; Find and fill email field
      (doseq [selector email-selectors]
        (when (element-exists? driver selector)
          (fill-input driver selector (:username config))))

      (Thread/sleep 500)

      ;; Find and fill password field
      (doseq [selector password-selectors]
        (when (element-exists? driver selector)
          (fill-input driver selector (:password config)))))

    (Thread/sleep 1000)

    ;; Click submit button
    (let [submit-selectors [{:css "button[type='submit']"}
                            {:css "input[type='submit']"}
                            {:css ".loginSubmit"}
                            {:css "#loginSubmit"}
                            {:css ".loginForm button"}]]
      (doseq [selector submit-selectors]
        (when (element-exists? driver selector)
          (click-element driver selector))))

    (Thread/sleep 5000)

    ;; After login, we need to select a server and enter the game
    ;; Look for server list and click on the configured server
    (when (element-exists? driver {:css ".serverList, #serverList, .accountList"})
      (log-and-print (:event-mgr adapter) "Selecting server...")
      ;; Try to find and click the server/account entry
      (let [server-entries (query-all-elements driver {:css ".accountCard, .serverItem, .server-item"})]
        (when (seq server-entries)
          (click-element driver (first server-entries)))))

    (Thread/sleep 3000)

    ;; Look for play button
    (when (element-exists? driver {:css ".btn_play, .playButton, [data-action='play']"})
      (click-element driver {:css ".btn_play, .playButton, [data-action='play']"})
      (Thread/sleep 5000))

    ;; Now we should be in the game - extract session from URL
    (let [current-url (e/get-url driver)
          session-match (re-find #"[?&]session=([0-9A-Fa-f]{12})" current-url)
          session (if session-match
                    (second session-match)
                    ;; Try to find session in page source
                    (let [source (e/get-source driver)
                          source-match (re-find #"session['\"]?\s*[:=]\s*['\"]?([0-9A-Fa-f]{12})" source)]
                      (when source-match (second source-match))))]

      (if session
        (do
          (logged-in (:event-mgr adapter) (:username config) session)
          (Thread/sleep 2000)
          session)
        (throw (utils/bot-fatal-error "Could not extract session ID after login"))))))

;; ============================================================================
;; Data Extraction from Pages
;; ============================================================================

(defn get-my-planets
  "Extract player's planets from the planet sidebar"
  [adapter player page]
  (let [driver (:driver adapter)
        ;; Navigate to overview if needed
        _ (when-not page
            (navigate-to-page adapter "index.php" {:page "ingame" :component "overview"}))
        ;; Query planet elements in sidebar
        planet-elements (query-all-elements driver {:css ".smallplanet, #planetList .planet"})
        colonies (atom [])]

    (doseq [planet-el planet-elements]
      (try
        ;; Get planet name
        (let [name-el (e/child driver planet-el {:css ".planet-name, .planetlink .planet-name"})
              name (when name-el (e/get-element-text-el driver name-el))
              ;; Get coordinates
              coord-el (e/child driver planet-el {:css ".planet-koords, .planetlink .planet-koords"})
              coord-text (when coord-el (e/get-element-text-el driver coord-el))
              coords (when coord-text (entities/parse-coords coord-text))]
          (when (and name coords)
            (swap! colonies conj (entities/own-planet coords player name))))
        (catch Exception _ nil)))

    (assoc player :colonies @colonies)))

(defn get-research-levels
  "Extract research levels from the research page"
  [adapter player]
  (navigate-to-page adapter "index.php" {:page "ingame" :component "research"})
  (Thread/sleep 2000)

  (let [driver (:driver adapter)
        research-levels (reduce
                         (fn [levels tech]
                           (if (not (instance? ogbot.entities.Research tech))
                             levels
                             (let [code (:code tech)
                                   ;; Try different selector patterns
                                   selectors [(format ".technology.research%d .level" code)
                                              (format "#research%d .level" code)
                                              (format "[data-technology='%d'] .level" code)]
                                   level (loop [[sel & rest-sels] selectors]
                                           (if sel
                                             (let [level-text (get-element-text-safe driver {:css sel})]
                                               (if (and (not (empty? level-text))
                                                       (re-matches #"\d+" (str/trim level-text)))
                                                 (Integer/parseInt (str/trim level-text))
                                                 (recur rest-sels)))
                                             0))]
                               (assoc levels (:name tech) level))))
                         {}
                         constants/ingame-types)
        ;; Validate critical technologies
        impulse-drive (get research-levels "impulseDrive" 0)
        combustion-drive (get research-levels "combustionDrive" 0)]

    (when (and (zero? impulse-drive) (zero? combustion-drive))
      (throw (utils/bot-fatal-error "Not enough technologies researched to run the bot")))

    (assoc player :research-levels research-levels)))

(defn- try-parse-int
  "Try to parse an integer from text, returns nil on failure"
  [text]
  (when (and text (not (empty? text)))
    (try
      (Integer/parseInt (str/replace (str/trim text) "." ""))
      (catch Exception _ nil))))

(defn- find-quantity-from-selectors
  "Try each selector until we find a valid quantity"
  [driver selectors]
  (loop [[sel & rest-sels] selectors]
    (if sel
      (let [qty-text (get-element-text-safe driver {:css sel})
            parsed (when (and (not (empty? qty-text))
                              (re-matches #"[\d\.]+" (str/trim (str/replace qty-text "." ""))))
                     (try-parse-int qty-text))]
        (if parsed
          parsed
          (recur rest-sels)))
      0)))

(defn get-available-fleet
  "Extract available fleet from the fleet page"
  [adapter]
  (let [driver (:driver adapter)]
    ;; Check if there's a warning div indicating no fleet
    (if (element-exists? driver {:css "#warning, .noFleet, .warning"})
      {}
      ;; Extract fleet quantities for each ship type
      (reduce (fn [fleet ship]
                (if (or (not (instance? ogbot.entities.Ship ship))
                        (= "solarSatellite" (:name ship)))
                  fleet
                  (let [code (:code ship)
                        selectors [(format "#button%d .level" code)
                                   (format ".technology%d .amount" code)
                                   (format "[data-technology='%d'] .amount" code)
                                   (format "li.%s .level" (:name ship))]
                        quantity (find-quantity-from-selectors driver selectors)]
                    (assoc fleet (:name ship) quantity))))
              {}
              constants/ingame-types))))

(defn get-free-fleet-slots
  "Extract free fleet slots from page"
  [adapter]
  (let [driver (:driver adapter)
        ;; Look for fleet slot indicator (usually shows X/Y format)
        slot-selectors [{:css ".fleetStatus .fleetSlots"}
                        {:css "#slots .fleetSlots"}
                        {:css ".fleet_slots"}
                        {:css "[data-slots]"}]
        slot-text (loop [[sel & rest-sels] slot-selectors]
                    (if sel
                      (let [text (get-element-text-safe driver sel)]
                        (if (and (not (empty? text)) (str/includes? text "/"))
                          text
                          (recur rest-sels)))
                      nil))]
    (if slot-text
      (let [match (re-find #"(\d+)/(\d+)" slot-text)]
        (if match
          (- (Integer/parseInt (nth match 2))
             (Integer/parseInt (nth match 1)))
          0))
      0)))

;; ============================================================================
;; Message Parsing (Espionage Reports)
;; ============================================================================

(defn parse-espionage-report
  "Parse an espionage report from a message element"
  [adapter message-el]
  (let [driver (:driver adapter)]
    (try
      (let [code (get-element-attr-safe driver message-el "data-msg-id")
            ;; Extract coordinates from subject
            subject-el (e/child driver message-el {:css ".msg_title, .msgTitle, .subject"})
            subject (when subject-el (e/get-element-text-el driver subject-el))
            coords (when subject (try (entities/parse-coords subject) (catch Exception _ nil)))]
        (when coords
          (entities/espionage-report code (t/now) coords "")))
      (catch Exception _ nil))))

(defn get-game-messages
  "Get messages from the messages page"
  ([adapter] (get-game-messages adapter nil))
  ([adapter msg-class]
   (navigate-to-page adapter "index.php" {:page "messages"})
   (Thread/sleep 2000)

   (let [driver (:driver adapter)
         ;; Click on espionage tab if needed
         _ (when (element-exists? driver {:css ".tabs_btn[data-tabid='20'], [data-subtab='espionage']"})
             (click-element driver {:css ".tabs_btn[data-tabid='20'], [data-subtab='espionage']"})
             (Thread/sleep 1000))
         ;; Query message elements
         message-elements (query-all-elements driver {:css ".msg, .message, [data-msg-id]"})
         messages (atom [])]

     (doseq [msg-el message-elements]
       (when-let [report (parse-espionage-report adapter msg-el)]
         (swap! messages conj report)))

     @messages)))

(defn delete-messages
  "Delete messages by checking their checkboxes and clicking delete"
  [adapter messages]
  (let [driver (:driver adapter)]
    (doseq [message messages]
      (try
        ;; Find and check the message checkbox
        (let [msg-id (:code message)
              checkbox-selector {:css (format "[data-msg-id='%s'] input[type='checkbox'], #msg_%s input" msg-id msg-id)}]
          (when (element-exists? driver checkbox-selector)
            (click-element driver checkbox-selector)))
        (catch Exception _ nil)))

    ;; Click delete button
    (Thread/sleep 500)
    (when (element-exists? driver {:css ".delete_btn, #deleteMarked, .msgDeleteButton"})
      (click-element driver {:css ".delete_btn, #deleteMarked, .msgDeleteButton"}))))

;; ============================================================================
;; Fleet Operations
;; ============================================================================

(defn validate-fleet-availability
  "Validate that we have enough ships and free fleet slots."
  [available-fleet mission-fleet abort-if-not-enough? free-slots fleet-slots-to-reserve]
  (when (<= free-slots fleet-slots-to-reserve)
    (throw (utils/no-free-slots-error)))

  (doseq [[ship-type requested] mission-fleet]
    (let [available (get available-fleet ship-type 0)]
      (when (or (zero? available)
                (and abort-if-not-enough? (< available requested)))
        (throw (utils/not-enough-ships-error
                available-fleet
                {ship-type requested}
                available))))))

(defn fill-fleet-selection
  "Fill ship quantities on fleet1 page"
  [adapter mission-fleet]
  (let [driver (:driver adapter)]
    (doseq [[ship-type quantity] mission-fleet]
      (let [ship (constants/get-by-name ship-type)
            code (:code ship)
            ;; Try different input selectors
            input-selectors [(format "#ship_%d" code)
                             (format "input[name='am%d']" code)
                             (format ".technology%d input" code)
                             (format "[data-technology='%d'] input" code)]]
        (doseq [sel input-selectors]
          (when (element-exists? driver {:css sel})
            (fill-input driver {:css sel} (int quantity))))))))

(defn fill-destination
  "Fill destination coordinates on fleet2 page"
  [adapter mission]
  (let [driver (:driver adapter)
        coords (:coords (:target-planet mission))
        speed-pct (:speed-percentage mission)]
    ;; Fill coordinates
    (fill-input driver {:css "input[name='galaxy'], #galaxy"} (:galaxy coords))
    (fill-input driver {:css "input[name='system'], #system"} (:solar-system coords))
    (fill-input driver {:css "input[name='position'], #position"} (:planet coords))

    ;; Select coordinate type (planet/moon/debris)
    (let [coord-type (get entities/coord-types (:coords-type coords) 1)]
      (when (element-exists? driver {:css (format "input[name='type'][value='%d']" coord-type)})
        (click-element driver {:css (format "input[name='type'][value='%d']" coord-type)})))

    ;; Set speed
    (let [speed-val (quot speed-pct 10)]
      (when (element-exists? driver {:css (format "#speedPercentage[value='%d'], .speed%d" speed-val speed-val)})
        (click-element driver {:css (format "#speedPercentage[value='%d'], .speed%d" speed-val speed-val)})))))

(defn extract-flight-time
  "Extract flight time from page"
  [adapter]
  (let [driver (:driver adapter)
        ;; Look for flight time display
        time-selectors [{:css "#flighttime, .flightTime"}
                        {:css ".duration span"}
                        {:css "[data-duration]"}]
        time-text (loop [[sel & rest-sels] time-selectors]
                    (if sel
                      (let [text (get-element-text-safe driver sel)]
                        (if (and (not (empty? text)) (re-find #"\d+:\d+" text))
                          text
                          (recur rest-sels)))
                      nil))]
    (when time-text
      (when-let [match (re-find #"(\d+):(\d+):(\d+)" time-text)]
        (let [hours (Integer/parseInt (nth match 1))
              mins (Integer/parseInt (nth match 2))
              secs (Integer/parseInt (nth match 3))]
          (* 1000 (+ (* hours 3600) (* mins 60) secs)))))))

(defn select-mission-type
  "Select mission type on fleet3 page"
  [adapter mission]
  (let [driver (:driver adapter)
        mission-code (get entities/mission-types (:mission-type mission) 3)
        resources (:resources mission)]
    ;; Select mission type radio button
    (let [mission-selectors [(format "#button%d, .missionButton%d" mission-code mission-code)
                             (format "input[name='mission'][value='%d']" mission-code)
                             (format "[data-mission='%d']" mission-code)]]
      (doseq [sel mission-selectors]
        (when (element-exists? driver {:css sel})
          (click-element driver {:css sel}))))

    ;; Fill resources
    (fill-input driver {:css "input[name='metal'], #metal"} (:metal resources))
    (fill-input driver {:css "input[name='crystal'], #crystal"} (:crystal resources))
    (fill-input driver {:css "input[name='deuterium'], #deuterium"} (:deuterium resources))))

(defn check-mission-result
  "Check the result of mission submission"
  [adapter available-fleet mission-fleet]
  (let [driver (:driver adapter)
        page-source (e/get-source driver)
        translations (:translations adapter)]
    (cond
      ;; Check for error messages
      (element-exists? driver {:css ".error, .errorMessage, #errorbox"})
      (let [error-text (get-element-text-safe driver {:css ".error, .errorMessage, #errorbox"})]
        (cond
          (str/includes? error-text (get translations "fleetLimitReached" "limit"))
          (throw (utils/no-free-slots-error))

          (str/includes? error-text (get translations "noShipSelected" "no ship"))
          (throw (utils/not-enough-ships-error available-fleet mission-fleet 0))

          :else
          {:status :retry :reason error-text}))

      ;; Check for success
      (or (element-exists? driver {:css ".success, .successMessage"})
          (str/includes? page-source "success"))
      {:status :success}

      ;; Generic failure
      (str/includes? page-source (get translations "fleetCouldNotBeSent" "could not be sent"))
      {:status :retry :reason "Fleet could not be sent"}

      :else
      {:status :success}))) ;; Assume success if no errors

(defn launch-mission
  "Launch a fleet mission through OGame's multi-step form process using Selenium"
  [adapter mission abort-if-not-enough? fleet-slots-to-reserve]
  (loop [retry-count 0]
    (when (> retry-count 5)
      (throw (utils/fleet-send-error "Too many retries launching mission")))

    (let [mission (update mission :fleet
                          (fn [fleet]
                            (into {} (map (fn [[k v]] [k (int v)]) fleet))))]

      ;; Step 1: Navigate to fleet page
      (navigate-to-page adapter "index.php" {:page "ingame" :component "fleetdispatch"})
      (Thread/sleep 2000)

      (let [free-slots (get-free-fleet-slots adapter)
            available-fleet (get-available-fleet adapter)]

        ;; Validate availability
        (validate-fleet-availability available-fleet (:fleet mission)
                                     abort-if-not-enough? free-slots fleet-slots-to-reserve)

        ;; Fill fleet selection
        (fill-fleet-selection adapter (:fleet mission))
        (Thread/sleep 1000)

        ;; Click continue button
        (if-not (click-element (:driver adapter) {:css "#continueToFleet2, .continue, [data-step='2']"})
          (recur (inc retry-count))

          (do
            (Thread/sleep 2000)

            ;; Step 2: Fill destination
            (fill-destination adapter mission)
            (Thread/sleep 1000)

            ;; Click continue
            (if-not (click-element (:driver adapter) {:css "#continueToFleet3, .continue, [data-step='3']"})
              (recur (inc retry-count))

              (do
                (Thread/sleep 2000)

                ;; Step 3: Extract flight time and select mission
                (let [flight-time (or (extract-flight-time adapter) 60000)]

                  (select-mission-type adapter mission)
                  (Thread/sleep 1000)

                  ;; Click send fleet
                  (if-not (click-element (:driver adapter) {:css "#sendFleet, .send_fleet, [data-action='send']"})
                    (recur (inc retry-count))

                    (do
                      (Thread/sleep 2000)

                      ;; Check result
                      (let [result (check-mission-result adapter available-fleet (:fleet mission))]
                        (case (:status result)
                          :retry (recur (inc retry-count))
                          :success (let [server-time (current-server-time (:server-data adapter))
                                         launched-mission (entities/mark-launched
                                                          mission
                                                          server-time
                                                          (t/millis flight-time))]
                                    (activity-msg (:event-mgr adapter)
                                                  (format "Mission launched to %s"
                                                          (str (:coords (:target-planet mission)))))
                                    launched-mission))))))))))))))

;; ============================================================================
;; Galaxy Scanning
;; ============================================================================

(defn scan-solar-system
  "Scan a solar system for planets"
  [adapter galaxy solar-system]
  (navigate-to-page adapter "index.php" {:page "ingame"
                                          :component "galaxy"
                                          :galaxy galaxy
                                          :system solar-system})
  (Thread/sleep 2000)

  (let [driver (:driver adapter)
        found-planets (atom [])
        players-by-name (atom {})
        ;; Query planet rows
        row-elements (query-all-elements driver {:css "#galaxyContent tr, .galaxyRow, [data-position]"})]

    (doseq [row-el row-elements]
      (try
        ;; Check if row has a planet
        (let [planet-el (e/child driver row-el {:css ".planetname, .cellPlanet"})
              owner-el (e/child driver row-el {:css ".playername, .cellPlayerName a"})
              position-el (e/child driver row-el {:css ".position, .cellPosition"})]
          (when (and planet-el owner-el)
            (let [owner-name (str/trim (e/get-element-text-el driver owner-el))
                  position-text (when position-el (e/get-element-text-el driver position-el))
                  position (if position-text
                            (try (Integer/parseInt (str/trim position-text)) (catch Exception _ 1))
                            1)]
              (when-not (empty? owner-name)
                (let [owner (or (@players-by-name owner-name)
                               (let [new-player (entities/enemy-player owner-name)]
                                 (swap! players-by-name assoc owner-name new-player)
                                 new-player))
                      coords (entities/coords galaxy solar-system position)
                      planet (entities/enemy-planet coords owner)]
                  ;; Check for inactive status
                  (let [inactive? (element-exists? driver row-el {:css ".inactive, .longinactive"})]
                    (swap! found-planets conj
                           (if inactive?
                             (assoc-in planet [:owner :is-inactive] true)
                             planet))))))))
        (catch Exception _ nil)))

    @found-planets))

(defn get-solar-systems
  "Scan multiple solar systems for planets"
  [adapter solar-systems deuterium-source-planet]
  (flatten
   (for [[galaxy system] solar-systems]
     (do
       (activity-msg (:event-mgr adapter) (format "Scanning %d:%d" galaxy system))
       (scan-solar-system adapter galaxy system)))))

;; ============================================================================
;; Initialization
;; ============================================================================

(defn create-web-adapter
  "Create a Selenium-based web adapter"
  [config translations check-thread-msgs-fn event-mgr]
  (log-and-print event-mgr "Starting Chrome browser...")
  (let [driver (create-driver)
        adapter (->WebAdapter config
                              translations
                              {} ;; translations-by-local-text
                              (->ServerData "" 0.0 "" (t/hours 0))
                              "000000000000"
                              driver
                              nil
                              check-thread-msgs-fn
                              event-mgr)]
    ;; Perform login
    (let [session (do-login! adapter)]
      (log-and-print event-mgr (str "Session established: " session))
      (assoc adapter :session session))))

(defn shutdown-adapter
  "Shutdown the web adapter and close the browser"
  [adapter]
  (quit-driver adapter))
