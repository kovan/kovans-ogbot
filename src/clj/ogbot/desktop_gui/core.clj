(ns ogbot.desktop-gui.core
  "Main entry point for the desktop GUI using cljfx/JavaFX."
  (:require [cljfx.api :as fx]
            [ogbot.desktop-gui.state :as state]
            [ogbot.desktop-gui.events :as events]
            [ogbot.desktop-gui.styles :as styles]
            [ogbot.desktop-gui.views.activity-tab :as activity-tab]
            [ogbot.desktop-gui.views.database-tab :as database-tab]
            [ogbot.desktop-gui.views.fleetsave-tab :as fleetsave-tab]
            [ogbot.desktop-gui.views.dialogs :as dialogs])
  (:import [javafx.application Platform]))

;; ============================================================================
;; Main Window View
;; ============================================================================

(defn main-view [{:keys [fx/context]}]
  {:fx/type :stage
   :showing true
   :title "Kovan's OGBot - Desktop Edition"
   :width 719
   :height 622
   :on-close-request (fn [_]
                       (let [bot-state (fx/sub-ctx context state/sub-bot-state)]
                         (when bot-state
                           (reset! (:running? bot-state) false)))
                       (Platform/exit))
   :scene {:fx/type :scene
           :stylesheets [(str "data:text/css," (java.net.URLEncoder/encode styles/main-window-style "UTF-8"))]
           :root {:fx/type :tab-pane
                  :tabs [{:fx/type :tab
                          :text "Bot activity"
                          :closable false
                          :content {:fx/type activity-tab/activity-tab}}
                         {:fx/type :tab
                          :text "Planet database"
                          :closable false
                          :content {:fx/type database-tab/database-tab}}
                         {:fx/type :tab
                          :text "Auto fleetsave"
                          :closable false
                          :content {:fx/type fleetsave-tab/fleetsave-tab}}]}}})

;; ============================================================================
;; Root Component
;; ============================================================================

(defn root [{:keys [fx/context]}]
  {:fx/type fx/ext-many
   :desc [{:fx/type main-view}
          {:fx/type dialogs/about-dialog}
          {:fx/type dialogs/options-dialog}]})

;; ============================================================================
;; Application Renderer
;; ============================================================================

(defonce renderer
  (atom nil))

(defn mount-renderer []
  (reset! renderer
          (fx/create-renderer
           :middleware (comp
                        fx/wrap-context-desc
                        (fx/wrap-map-desc (fn [_] {:fx/type root})))
           :opts {:fx.opt/map-event-handler events/event-handler
                  :fx.opt/type->lifecycle #(or (fx/keyword->lifecycle %)
                                               (fx/fn->lifecycle-with-context %))})))

;; ============================================================================
;; Entry Point
;; ============================================================================

(defn start-desktop-gui
  "Start the desktop GUI application."
  []
  (Platform/setImplicitExit true)
  (mount-renderer)
  (fx/mount-renderer state/*state @renderer)

  (println)
  (println "Desktop GUI started.")
  (println "Close the window to exit.")

  ;; Keep the main thread alive
  (while (not (.isShutdown (java.util.concurrent.ForkJoinPool/commonPool)))
    (Thread/sleep 1000)))

(defn stop-desktop-gui
  "Stop the desktop GUI application."
  []
  (when @renderer
    (fx/unmount-renderer state/*state @renderer)
    (reset! renderer nil))
  (Platform/exit))

(defn -main [& _args]
  (start-desktop-gui))
