(defproject ogbot "3.1.0-SNAPSHOT"
  :description "Kovan's OGBot - Automated OGame bot translated to Clojure"
  :url "https://github.com/kovans-ogbot"
  :license {:name "GNU GPL v2"
            :url "https://www.gnu.org/licenses/gpl-2.0.html"}

  :dependencies [[org.clojure/clojure "1.11.1"]
                 ;; HTTP client
                 [clj-http "3.12.3"]
                 ;; HTML parsing
                 [enlive "1.1.6"]
                 [hickory "0.7.1"]
                 ;; Database
                 [org.xerial/sqlite-jdbc "3.44.1.0"]
                 [org.clojure/java.jdbc "0.7.12"]
                 [honeysql "1.0.461"]
                 ;; Async/concurrency
                 [org.clojure/core.async "1.6.681"]
                 ;; Configuration
                 [aero "1.1.6"]
                 ;; Logging
                 [org.clojure/tools.logging "1.2.4"]
                 [ch.qos.logback/logback-classic "1.2.12"]
                 ;; Web UI
                 [ring/ring-core "1.10.0"]
                 [ring/ring-jetty-adapter "1.10.0"]
                 [compojure "1.7.0"]
                 [hiccup "1.0.5"]
                 [cheshire "5.11.0"]
                 [http-kit "2.6.0"]
                 ;; Utilities
                 [clj-time "0.15.2"]
                 [com.taoensso/timbre "6.3.1"]
                 ;; Selenium automation
                 [etaoin "1.0.40"]
                 ;; HTTP client for API calls
                 [clj-http "3.12.3"]
                 ;; Desktop GUI (JavaFX)
                 [cljfx/cljfx "1.10.6"]]

  :main ^:skip-aot ogbot.core

  :target-path "target/%s"

  :source-paths ["src/clj"]
  :resource-paths ["resources" "languages"]

  :profiles {:uberjar {:aot :all
                       :jvm-opts ["-Dclojure.compiler.direct-linking=true"]}
             :dev {:dependencies [[org.clojure/tools.namespace "1.4.4"]]}}

  :jvm-opts ["-Xmx512m"]

  :aliases {"run-gui" ["run"]
            "check" ["do" "clean," "compile"]})
