(ns ogbot.webui.components.controls
  (:require [ogbot.webui.state :as state]
            [clojure.string :as str]))

(defn controls-panel []
  (let [status @state/bot-status]
    [:div.controls
     [:button.btn-start {:on-click state/start-bot!} "Start"]
     [:button.btn-stop {:on-click state/stop-bot!} "Stop"]
     [:button.btn-pause {:on-click state/pause-bot!} "Pause"]
     [:button.btn-pause {:on-click state/resume-bot!} "Resume"]
     [:span.status {:class status} (str/upper-case status)]]))
