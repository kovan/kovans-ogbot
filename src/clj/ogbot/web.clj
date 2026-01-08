(ns ogbot.web
  "HTTP and HTML parsing for OGame interaction"
  (:require [clj-http.client :as http]
            [clj-http.cookies :as cookies]
            [clojure.string :as str]
            [clojure.java.io :as io]
            [hickory.core :as h]
            [hickory.select :as s]
            [clj-time.core :as t]
            [clj-time.format :as f]
            [clj-time.coerce :as tc]
            [ogbot.entities :as entities]
            [ogbot.constants :as constants]
            [ogbot.utils :as utils]
            [ogbot.config :as config])
  (:import [java.net URI]
           [java.time Duration LocalDateTime]
           [java.util.regex Pattern]))

;; ============================================================================
;; Server Data
;; ============================================================================

(defrecord ServerData [charset version language time-delta])

(defn current-server-time [^ServerData server-data]
  (t/plus (t/now) (:time-delta server-data)))

;; ============================================================================
;; Web Page Handling
;; ============================================================================

(defrecord WebPage [url text hickory])

(defn parse-web-page [response]
  (let [body (:body response)
        url (str (:request response))]
    (->WebPage url body (h/as-hickory (h/parse body)))))

(defn save-page-to-disk [^WebPage page]
  (let [debug-dir (io/file "debug")]
    (when-not (.exists debug-dir)
      (.mkdir debug-dir))
    (let [files (seq (.listFiles debug-dir))
          file-count (count files)]
      (when (>= file-count 30)
        (let [sorted-files (sort-by #(.getName %) files)]
          (io/delete-file (first sorted-files) true))))
    (let [timestamp (f/unparse (f/formatter "yyyy-MM-dd_HH.mm.ss") (t/now))
          php-part (or (second (re-find #"/(\w+\.php.*)" (:url page))) "")
          clean-php (-> php-part
                        (str/replace "?" ",")
                        (str/replace "&" ","))
          filename (format "debug/%s,%s.html" timestamp clean-php)]
      (spit filename
            (-> (:text page)
                (str/replace "<script" "<noscript")
                (str/replace "</script>" "</noscript>"))))))

;; ============================================================================
;; Web Adapter - Main HTTP/HTML Interface
;; ============================================================================

(defrecord WebAdapter [config translations translations-by-local-text
                       server-data session cookie-store last-fetched-page
                       check-thread-msgs-fn event-mgr regexps])

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
;; HTTP Requests
;; ============================================================================

(defn build-request-options [adapter url]
  {:headers {"User-Agent" (get-in adapter [:config :user-agent])
             "Referer" (or (:url (:last-fetched-page adapter)) "")}
   :cookie-store (:cookie-store adapter)
   :socket-timeout 10000
   :conn-timeout 10000
   :throw-exceptions false
   :follow-redirects true
   :redirect-strategy :lax})

(defn fetch-url [adapter url]
  (try
    (let [opts (build-request-options adapter url)
          response (http/get url opts)]
      (when (= 200 (:status response))
        (parse-web-page response)))
    (catch Exception e
      (connection-error (:event-mgr adapter) (.getMessage e))
      nil)))

(defn fetch-php
  ([adapter php] (fetch-php adapter php {}))
  ([adapter php params]
   (let [session (:session adapter)
         webpage (get-in adapter [:config :webpage])
         query-params (assoc params :session session)
         url (format "http://%s/game/%s?%s"
                    webpage
                    php
                    (http/generate-query-string query-params))]
     (fetch-url adapter url)
     (save-page-to-disk webpage))))

(defn fetch-php-post [adapter php post-data params]
  (let [session (:session adapter)
        webpage (get-in adapter [:config :webpage])
        query-params (assoc params :session session)
        url (format "http://%s/game/%s?%s"
                   webpage
                   php
                   (http/generate-query-string query-params))
        opts (assoc (build-request-options adapter url)
                    :form-params post-data)]
    (try
      (let [response (http/post url opts)]
        (when (= 200 (:status response))
          (parse-web-page response)))
      (catch Exception e
        (connection-error (:event-mgr adapter) (.getMessage e))
        nil))))

;; ============================================================================
;; Login
;; ============================================================================

(defn do-login! [adapter]
  (let [config (:config adapter)
        webpage (:webpage config)
        base-url (str "http://" (str/join "." (rest (str/split webpage #"\."))))
        login-page (fetch-url adapter base-url)]
    (when login-page
      ;; Simulate form submission
      (let [login-url (format "http://%s/game/reg/login2.php" webpage)
            form-data {:uni_url webpage
                      :login (:username config)
                      :pass (:password config)}
            opts (assoc (build-request-options adapter login-url)
                       :form-params form-data)
            response (http/post login-url opts)
            page (parse-web-page response)
            session-match (re-find #"[0-9A-Fa-f]{12}" (:text page))]
        (if session-match
          (do
            (logged-in (:event-mgr adapter) (:username config) session-match)
            (Thread/sleep 5000)
            session-match)
          (throw (utils/bot-fatal-error "Invalid username and/or password")))))))

;; ============================================================================
;; Data Extraction from Pages
;; ============================================================================

(defn extract-with-xpath [hickory xpath-expr]
  ;; Simplified XPath-like extraction using Hickory selectors
  ;; This is a basic implementation - full XPath support would require more work
  (s/select (s/tag :div) hickory))

(defn get-my-planets [adapter player page]
  (let [hickory (:hickory page)
        planet-names (s/select (s/class "planet-name") hickory)
        planet-coords (s/select (s/class "planet-koords") hickory)
        colonies (atom [])]
    (doseq [[name-node coord-node] (map vector planet-names planet-coords)]
      (let [name (get-in name-node [:content 0])
            coord-text (get-in coord-node [:content 0])
            coords (entities/parse-coords coord-text)]
        (swap! colonies conj (entities/own-planet coords player name))))
    (assoc player :colonies @colonies)))

(defn get-research-levels [adapter player]
  (let [page (fetch-php adapter "index.php" {:page "research"})
        hickory (:hickory page)
        research-levels (reduce (fn [levels tech]
                                 (if (not (instance? ogbot.entities.Research tech))
                                   levels
                                   (let [code (:code tech)
                                         ;; Try normal class first
                                         class-name (str "research" code)
                                         nodes (s/select (s/descendant
                                                         (s/class class-name)
                                                         (s/class "level"))
                                                        hickory)
                                         ;; If not found, try with "tips" suffix (being built)
                                         nodes (if (empty? nodes)
                                                (s/select (s/descendant
                                                          (s/class (str class-name " tips"))
                                                          (s/class "level"))
                                                         hickory)
                                                nodes)
                                         level-text (when (seq nodes)
                                                     (-> nodes first :content first))
                                         level (if level-text
                                                (try
                                                  (Integer/parseInt (str level-text))
                                                  (catch Exception _ 0))
                                                0)]
                                     (assoc levels (:name tech) level))))
                               {}
                               constants/ingame-types)
        ;; Validate critical technologies
        impulse-drive (get research-levels "impulseDrive" 0)
        combustion-drive (get research-levels "combustionDrive" 0)]
    (when (or (zero? impulse-drive) (zero? combustion-drive))
      (throw (utils/bot-fatal-error "Not enough technologies researched to run the bot")))
    (assoc player :research-levels research-levels)))

(defn get-available-fleet [adapter page]
  (let [hickory (:hickory page)]
    ;; Check if there's a warning div indicating no fleet
    (if (seq (s/select (s/id "warning") hickory))
      {}
      ;; Extract fleet quantities for each ship type
      (reduce (fn [fleet ship]
                (if (or (not (instance? ogbot.entities.Ship ship))
                       (= "solarSatellite" (:name ship)))
                  fleet
                  (let [button-id (str "button" (:code ship))
                        ;; Select the quantity from: #button{code} .level
                        level-nodes (s/select (s/descendant
                                               (s/id button-id)
                                               (s/class "level"))
                                             hickory)
                        quantity-text (when (seq level-nodes)
                                       (-> level-nodes first :content first))
                        quantity (if quantity-text
                                  (try
                                    (Integer/parseInt (str/replace (str quantity-text) "." ""))
                                    (catch Exception _ 0))
                                  0)]
                    (assoc fleet (:name ship) quantity))))
              {}
              constants/ingame-types))))

(defn get-free-fleet-slots [adapter player page]
  (let [text (:text page)
        match (re-find #"(\d+)/(\d+)" text)]
    (if match
      (- (Integer/parseInt (nth match 2))
         (Integer/parseInt (nth match 1)))
      0)))

;; ============================================================================
;; Message Parsing (Espionage Reports)
;; ============================================================================

(defn parse-time [time-str]
  (try
    (f/parse (f/formatter "dd.MM.yyyy HH:mm:ss") time-str)
    (catch Exception _
      (t/now))))

(defn parse-espionage-report [adapter message-node]
  (let [code (get-in message-node [:attrs :id])
        sender (str (first (s/select (s/class "from") message-node)))
        subject-nodes (s/select (s/class "subject") message-node)
        subject (when (seq subject-nodes)
                 (get-in (first subject-nodes) [:content 1]))
        coords (when subject (entities/parse-coords subject))
        report (entities/espionage-report code (t/now) coords "")]
    report))

(defn get-game-messages
  ([adapter] (get-game-messages adapter nil))
  ([adapter msg-class]
   (let [post-data {:ajax "1"}
         page (fetch-php-post adapter "index.php" post-data {:page "messages"})
         messages (atom [])]
     (when page
       (let [hickory (:hickory page)
             message-rows (s/select (s/and (s/tag :tr)
                                           (s/not (s/class "first"))
                                           (s/not (s/class "last")))
                                   hickory)]
         (doseq [msg-row message-rows]
           (let [report (parse-espionage-report adapter msg-row)]
             (swap! messages conj report)))))
     @messages)))

(defn delete-messages [adapter messages]
  (doseq [message messages]
    (fetch-php-post adapter "index.php"
                   {:ajax "1" "deleteMessageIds[]" (:code message)}
                   {:page "messages"})))

;; ============================================================================
;; Fleet Operations
;; ============================================================================

;; ============================================================================
;; Fleet Mission Launch - Multi-step Process
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

(defn build-fleet-form
  "Build form data for fleet selection (step 1)."
  [mission-fleet]
  (reduce (fn [form [ship-type quantity]]
            (let [ship-code (:code (constants/get-by-name ship-type))]
              (assoc form (str "am" ship-code) (str (int quantity)))))
          {}
          mission-fleet))

(defn build-destination-form
  "Build form data for destination and speed (step 2)."
  [mission]
  (let [coords (:coords (:target-planet mission))]
    {:galaxy (str (:galaxy coords))
     :system (str (:solar-system coords))
     :position (str (:planet coords))
     :type (str (get entities/coord-types (:coords-type coords) 1))
     :speed (str (quot (:speed-percentage mission) 10))}))

(defn extract-flight-time
  "Extract flight time from page HTML."
  [page-text]
  (when-let [match (re-find #"(\d+):(\d+):(\d+)" page-text)]
    (let [hours (Integer/parseInt (nth match 1))
          mins (Integer/parseInt (nth match 2))
          secs (Integer/parseInt (nth match 3))]
      (* 1000 (+ (* hours 3600) (* mins 60) secs)))))

(defn build-mission-form
  "Build form data for mission type and resources (step 3)."
  [mission]
  (let [resources (:resources mission)]
    {:mission (str (get entities/mission-types (:mission-type mission) 3))
     :resource1 (str (:metal resources))
     :resource2 (str (:crystal resources))
     :resource3 (str (:deuterium resources))}))

(defn check-mission-result
  "Check the result of mission submission and handle errors."
  [page-text translations available-fleet mission-fleet]
  (cond
    ;; Generic failure message
    (str/includes? page-text (get translations "fleetCouldNotBeSent" "could not be sent"))
    {:status :retry :reason "Fleet could not be sent"}

    ;; Check for specific errors
    :else
    (let [error-matches (re-seq #"<span class=\"error\">(.*?)</span>" page-text)]
      (if (seq error-matches)
        (let [errors (map second error-matches)
              error-text (str/join " " errors)]
          (cond
            (some #(str/includes? % (get translations "fleetLimitReached" "limit")) errors)
            (throw (utils/no-free-slots-error))

            (some #(str/includes? % (get translations "noShipSelected" "no ship")) errors)
            (throw (utils/not-enough-ships-error available-fleet mission-fleet 0))

            :else
            (throw (utils/fleet-send-error (str "Fleet send error: " error-text)))))
        ;; No errors, check for success
        (if (str/includes? page-text "class=\"success\"")
          {:status :success}
          {:status :retry :reason "No success message"})))))

(defn launch-mission
  "Launch a fleet mission through OGame's 4-step form process.
  Returns the mission object with launch time and flight duration set."
  [adapter mission abort-if-not-enough? fleet-slots-to-reserve]
  (loop [retry-count 0]
    (when (> retry-count 5)
      (throw (utils/fleet-send-error "Too many retries launching mission")))

    ;; Ensure fleet quantities are integers
    (let [mission (update mission :fleet
                         (fn [fleet]
                           (into {} (map (fn [[k v]] [k (int v)]) fleet))))]

      ;; Step 1: Select fleet (fleet1 page)
      (let [page1 (fetch-php adapter "index.php" {:page "fleet1"})
            free-slots (get-free-fleet-slots adapter nil page1)
            available-fleet (get-available-fleet adapter page1)]

        ;; Validate we have enough ships and slots
        (validate-fleet-availability available-fleet (:fleet mission)
                                    abort-if-not-enough? free-slots fleet-slots-to-reserve)

        ;; Build and submit fleet selection form
        (let [fleet-form (build-fleet-form (:fleet mission))]
          (Thread/sleep 3000) ; Delay between steps

          ;; Step 2: Select destination and speed (fleet2 page)
          (let [page2 (fetch-php-post adapter "index.php" fleet-form {:page "fleet2"})]

            ;; Check if we reached fleet2 (should have "fleet3" in action)
            (if-not (str/includes? (:text page2) "fleet3")
              (recur (inc retry-count))

              ;; Build and submit destination form
              (let [dest-form (build-destination-form mission)]
                (Thread/sleep 3000) ; Delay between steps

                ;; Step 3: Select mission type and resources (fleet3 page)
                (let [page3 (fetch-php-post adapter "index.php" dest-form {:page "fleet3"})]

                  ;; Check if we reached fleet3
                  (if-not (str/includes? (:text page3) "fleet3")
                    (recur (inc retry-count))

                    ;; Extract flight time and build mission form
                    (let [flight-time (extract-flight-time (:text page3))
                          mission-form (build-mission-form mission)]
                      (Thread/sleep 3000) ; Delay between steps

                      ;; Step 4: Confirm and check result (fleet4 page)
                      (let [page4 (fetch-php-post adapter "index.php" mission-form {:page "fleet4"})
                            result (check-mission-result (:text page4)
                                                        (:translations adapter)
                                                        available-fleet
                                                        (:fleet mission))]

                        (case (:status result)
                          :retry (recur (inc retry-count))
                          :success (let [server-time (current-server-time (:server-data adapter))
                                        launched-mission (entities/mark-launched mission server-time flight-time)]
                                    (activity-msg (:event-mgr adapter)
                                                 (format "Mission launched to %s"
                                                        (str (:coords (:target-planet mission)))))
                                    launched-mission))))))))))))))

;; ============================================================================
;; Galaxy Scanning
;; ============================================================================

(defn scan-solar-system [adapter galaxy solar-system]
  (let [params {:session (:session adapter)
               :galaxy galaxy
               :system solar-system
               :ajax 1}
        webpage (get-in adapter [:config :webpage])
        url (format "http://%s/game/index.php?page=galaxyContent&ajax=1&%s"
                   webpage
                   (http/generate-query-string params))
        page (fetch-url adapter url)
        found-planets (atom [])
        players-by-name (atom {})]

    (when page
      (let [hickory (:hickory page)
            rows (s/select (s/and (s/id "galaxytable")
                                 (s/class "row"))
                          hickory)]
        (doseq [row rows]
          (let [owner-name (str/trim (or (get-in row [:content 0]) ""))]
            (when-not (empty? owner-name)
              (let [owner (or (@players-by-name owner-name)
                            (let [new-player (entities/enemy-player owner-name)]
                              (swap! players-by-name assoc owner-name new-player)
                              new-player))
                    planet-num 1  ;; Simplified - would parse from HTML
                    coords (entities/coords galaxy solar-system planet-num)
                    planet (entities/enemy-planet coords owner)]
                (swap! found-planets conj planet)))))))
    @found-planets))

(defn get-solar-systems [adapter solar-systems deuterium-source-planet]
  ;; Simplified version - Python uses multi-threading
  (flatten
   (for [[galaxy system] solar-systems]
     (scan-solar-system adapter galaxy system))))

;; ============================================================================
;; Initialization
;; ============================================================================

(defn create-web-adapter [config translations check-thread-msgs-fn event-mgr]
  (let [cookie-store (cookies/cookie-store)
        adapter (->WebAdapter config
                             translations
                             {} ;; translations-by-local-text
                             (->ServerData "" 0.0 "" (t/hours 0))
                             "000000000000"
                             cookie-store
                             nil
                             check-thread-msgs-fn
                             event-mgr
                             {})]
    ;; Perform initial setup
    (let [session (do-login! adapter)]
      (assoc adapter :session session))))
