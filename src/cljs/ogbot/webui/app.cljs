(ns ogbot.webui.app
  (:require [reagent.core :as r]
            [reagent.dom :as rdom]
            [ogbot.webui.state :as state]
            [ogbot.webui.components.controls :as controls]
            [ogbot.webui.components.activity-tab :as activity-tab]
            [ogbot.webui.components.database-tab :as database-tab]))

(defn tabs []
  (let [active-tab @state/active-tab]
    [:div.tabs
     [:button.tab-btn
      {:class (when (= active-tab :activity) "active")
       :on-click #(reset! state/active-tab :activity)}
      "Bot Activity"]
     [:button.tab-btn
      {:class (when (= active-tab :database) "active")
       :on-click #(do (reset! state/active-tab :database)
                      (state/load-planets!))}
      "Planet Database"]]))

(defn app []
  [:div.container
   [:h1 "Kovan's OGBot - Web Interface"]
   [controls/controls-panel]
   [tabs]
   (case @state/active-tab
     :activity [activity-tab/activity-tab]
     :database [database-tab/database-tab]
     [activity-tab/activity-tab])])

(defn ^:export init! []
  (state/start-polling!)
  (rdom/render [app] (.getElementById js/document "app")))

;; Auto-init when DOM is ready
(set! (.-onload js/window) init!)
