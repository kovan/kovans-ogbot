(ns ogbot.gui
  "GUI wrapper - delegates to web UI"
  (:require [ogbot.webui :as webui])
  (:import [java.awt Desktop Desktop$Action]
           [java.net URI]))

(defn- wsl? []
  (try
    (and (.exists (java.io.File. "/proc/version"))
         (.contains (slurp "/proc/version") "microsoft"))
    (catch Exception _ false)))

(defn- open-browser! [url]
  (try
    (let [os-name (System/getProperty "os.name")
          runtime (Runtime/getRuntime)]
      (cond
        ;; WSL - use explorer.exe to open in Windows browser
        (wsl?)
        (do (.exec runtime (into-array String ["explorer.exe" url]))
            true)

        ;; Linux - use xdg-open
        (.contains os-name "Linux")
        (do (.exec runtime (into-array String ["xdg-open" url]))
            true)

        ;; macOS
        (.contains os-name "Mac")
        (do (.exec runtime (into-array String ["open" url]))
            true)

        ;; Windows
        (.contains os-name "Windows")
        (do (.exec runtime (into-array String ["cmd" "/c" "start" url]))
            true)

        ;; Fallback to Java Desktop API
        (Desktop/isDesktopSupported)
        (let [desktop (Desktop/getDesktop)]
          (when (.isSupported desktop Desktop$Action/BROWSE)
            (.browse desktop (URI. url))
            true))

        :else false))
    (catch Exception e
      (println "Could not open browser automatically:" (.getMessage e))
      false)))

(defn start-gui
  "Start the web-based GUI"
  ([] (start-gui 3000))
  ([port]
   (let [url (str "http://localhost:" port)]
     (webui/start-server! port)
     (println)
     (println "╔════════════════════════════════════════════════╗")
     (println "║          OGBot Web Interface Started          ║")
     (println "║                                                ║")
     (println (format "║   → Open http://localhost:%-5d              ║" port))
     (println "║                                                ║")
     (println "║   The web UI is now running.                   ║")
     (println "║   Use your browser to control the bot.        ║")
     (println "╚════════════════════════════════════════════════╝")
     (when (open-browser! url)
       (println "\nBrowser opened automatically.")))))

(defn -main [& args]
  (let [port (if (seq args)
               (Integer/parseInt (first args))
               3000)]
    (start-gui port)))
