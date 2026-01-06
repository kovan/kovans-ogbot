(ns ogbot.gui
  "GUI wrapper - delegates to web UI"
  (:require [ogbot.webui :as webui]))

(defn start-gui
  "Start the web-based GUI"
  ([] (start-gui 3000))
  ([port]
   (webui/start-server! port)
   (println)
   (println "╔════════════════════════════════════════════════╗")
   (println "║          OGBot Web Interface Started          ║")
   (println "║                                                ║")
   (println (format "║   → Open http://localhost:%-5d              ║" port))
   (println "║                                                ║")
   (println "║   The web UI is now running.                   ║")
   (println "║   Use your browser to control the bot.        ║")
   (println "╚════════════════════════════════════════════════╝")))

(defn -main [& args]
  (let [port (if (seq args)
               (Integer/parseInt (first args))
               3000)]
    (start-gui port)))
