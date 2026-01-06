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
   :follow-redirects true})

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
     (fetch-url adapter url))))

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
        research-levels (atom {})]
    (when page
      (doseq [tech constants/ingame-types
              :when (instance? ogbot.entities.Research tech)]
        (let [class-selector (str "research" (:code tech))
              ;; This is simplified - actual implementation would parse HTML properly
              level 0]
          (swap! research-levels assoc (:name tech) level))))
    (assoc player :research-levels @research-levels)))

(defn get-available-fleet [adapter page]
  (let [hickory (:hickory page)
        fleet (atom {})]
    (doseq [ship constants/ingame-types
            :when (instance? ogbot.entities.Ship ship)
            :when (not= "solarSatellite" (:name ship))]
      (let [button-id (str "button" (:code ship))
            ;; Simplified - actual implementation would extract from HTML
            quantity 0]
        (swap! fleet assoc (:name ship) quantity)))
    @fleet))

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

(defn launch-mission [adapter mission abort-if-not-enough? fleet-slots-to-reserve]
  ;; Step 1: Select fleet
  (let [page (fetch-php adapter "index.php" {:page "fleet1"})
        free-slots (get-free-fleet-slots adapter nil page)
        available-fleet (get-available-fleet adapter page)]

    (when (<= free-slots fleet-slots-to-reserve)
      (throw (utils/no-free-slots-error)))

    ;; Validate fleet availability
    (doseq [[ship-type requested] (:fleet mission)]
      (let [available (get available-fleet ship-type 0)]
        (when (or (zero? available)
                 (and abort-if-not-enough? (< available requested)))
          (throw (utils/not-enough-ships-error
                 available-fleet
                 {ship-type requested}
                 available)))))

    ;; This is simplified - actual implementation would submit forms
    ;; through multiple steps like the Python version
    (println "Launching mission:" mission)
    mission))

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
