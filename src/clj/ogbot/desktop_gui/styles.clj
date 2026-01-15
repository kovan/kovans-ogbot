(ns ogbot.desktop-gui.styles
  "Color constants and CSS style functions for the desktop GUI.
   Translated from MyColors in the original Python GUI.")

;; ============================================================================
;; Color Constants (from PyQt4 gui.py MyColors class)
;; ============================================================================

(def colors
  {:light-green    "#bfffbf"   ; QColor(191,255,191)
   :light-red      "#ffbfbf"   ; QColor(255,191,191)
   :light-yellow   "#ffffbf"   ; QColor(255,255,191)
   :light-grey     "#bfbfbf"   ; QColor(191,191,191)
   :very-light-grey "#dfdfdf"  ; QColor(223,223,223)
   :white          "#ffffff"
   :black          "#000000"})

;; ============================================================================
;; Status Label Styles
;; ============================================================================

(defn connection-status-style
  "Style for connection status label."
  [status]
  (let [bg-color (case status
                   :ok (:light-green colors)
                   :error (:light-red colors)
                   "transparent")]
    (str "-fx-background-color: " bg-color "; "
         "-fx-font-weight: bold; "
         "-fx-alignment: center; "
         "-fx-padding: 5px; "
         "-fx-background-radius: 3px;")))

(defn bot-status-style
  "Style for bot status label based on current status."
  [status]
  (let [bg-color (case status
                   :running (:light-green colors)
                   :paused (:light-yellow colors)
                   :stopped (:light-red colors)
                   "transparent")]
    (str "-fx-background-color: " bg-color "; "
         "-fx-font-weight: bold; "
         "-fx-alignment: center; "
         "-fx-padding: 5px; "
         "-fx-background-radius: 3px;")))

;; ============================================================================
;; Rentability Cell Coloring
;; ============================================================================

(defn rentability-cell-style
  "Calculate background color for rentability cell.
   Higher rentability = more green, lower = closer to white.
   Equivalent to the PyQt simulationsUpdate coloring logic."
  [rentability max-rentability]
  (if (and (number? rentability)
           (pos? rentability)
           (number? max-rentability)
           (pos? max-rentability))
    (let [value (int (* (/ rentability max-rentability) 255))
          ;; Green channel stays at 255, red and blue decrease proportionally
          r (- 255 value)
          g 255
          b (- 255 value)]
      (str "-fx-background-color: rgb(" r ", " g ", " b ");"))
    ""))

(defn rentability-positive-style []
  (str "-fx-text-fill: #28a745; -fx-font-weight: bold;"))

(defn rentability-negative-style []
  (str "-fx-text-fill: #dc3545; -fx-font-weight: bold;"))

;; ============================================================================
;; Table Row Styles
;; ============================================================================

(def alternating-row-style
  "-fx-control-inner-background-alt: derive(-fx-control-inner-background, -2%);")

;; ============================================================================
;; Button Styles
;; ============================================================================

(def start-button-style
  "-fx-background-color: #28a745; -fx-text-fill: white; -fx-font-weight: bold;")

(def stop-button-style
  "-fx-background-color: #dc3545; -fx-text-fill: white; -fx-font-weight: bold;")

(def pause-button-style
  "-fx-background-color: #ffc107; -fx-text-fill: black; -fx-font-weight: bold;")

(def default-button-style
  "-fx-background-color: #6c757d; -fx-text-fill: white;")

;; ============================================================================
;; Panel Styles
;; ============================================================================

(def panel-style
  "-fx-background-color: #f8f9fa; -fx-padding: 10px;")

(def titled-pane-style
  "-fx-font-weight: bold;")

;; ============================================================================
;; Main Window Style
;; ============================================================================

(def main-window-style
  "-fx-font-family: 'Segoe UI', 'Arial', sans-serif; -fx-font-size: 12px;")
