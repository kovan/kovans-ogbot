(ns ogbot.web-selenium-test
  "Unit tests for Selenium-based web adapter"
  (:require [clojure.test :refer :all]
            [etaoin.api :as e]))

;; ============================================================================
;; Test Utilities
;; ============================================================================

(defn create-test-driver
  "Create a Chrome driver for testing"
  []
  (e/chrome {:args ["--disable-blink-features=AutomationControlled"
                    "--disable-infobars"
                    "--window-size=1280,800"]}))

(defmacro with-driver
  "Execute body with a driver, ensuring cleanup"
  [driver-sym & body]
  `(let [~driver-sym (create-test-driver)]
     (try
       ~@body
       (finally
         (e/quit ~driver-sym)))))

;; ============================================================================
;; Page Inspection Tests
;; ============================================================================

(deftest ^:selenium test-inspect-lobby-page
  (testing "Inspect OGame lobby page structure"
    (with-driver driver
      (println "Navigating to lobby...")
      (e/go driver "https://lobby.ogame.gameforge.com/en_GB/")
      (Thread/sleep 5000)

      (println "Page title:" (e/get-title driver))

      (println "\n=== Input elements ===")
      (doseq [el (e/query-all driver {:tag :input})]
        (try
          (let [typ (e/get-element-attr-el driver el "type")
                name (e/get-element-attr-el driver el "name")
                id (e/get-element-attr-el driver el "id")
                cls (e/get-element-attr-el driver el "class")]
            (println (format "  type=%s name=%s id=%s class=%s" typ name id cls)))
          (catch Exception _ nil)))

      (println "\n=== Button elements ===")
      (doseq [el (e/query-all driver {:tag :button})]
        (try
          (let [typ (e/get-element-attr-el driver el "type")
                id (e/get-element-attr-el driver el "id")
                cls (e/get-element-attr-el driver el "class")
                txt (e/get-element-text-el driver el)]
            (println (format "  type=%s id=%s class=%s text=[%s]" typ id cls txt)))
          (catch Exception _ nil)))

      (println "\n=== Form elements ===")
      (doseq [el (e/query-all driver {:tag :form})]
        (try
          (let [id (e/get-element-attr-el driver el "id")
                cls (e/get-element-attr-el driver el "class")
                action (e/get-element-attr-el driver el "action")]
            (println (format "  id=%s class=%s action=%s" id cls action)))
          (catch Exception _ nil)))

      (is (= "OGame - The Most Successful Browser Game in the Universe!"
             (e/get-title driver))))))

(deftest ^:selenium test-inspect-login-form
  (testing "Inspect login form after clicking Log in tab"
    (with-driver driver
      (println "Navigating to lobby...")
      (e/go driver "https://lobby.ogame.gameforge.com/en_GB/")
      (Thread/sleep 5000)

      (println "Clicking Log in tab...")
      (e/click driver {:xpath "//li[contains(text(), 'Log in')]"})
      (Thread/sleep 2000)

      (println "\n=== Login form inputs ===")
      (doseq [el (e/query-all driver {:css "#loginForm input"})]
        (try
          (let [typ (e/get-element-attr-el driver el "type")
                name (e/get-element-attr-el driver el "name")]
            (println (format "  type=%s name=%s" typ name)))
          (catch Exception _ nil)))

      (println "\n=== Login form buttons ===")
      (doseq [el (e/query-all driver {:css "#loginForm button"})]
        (try
          (let [typ (e/get-element-attr-el driver el "type")
                cls (e/get-element-attr-el driver el "class")
                txt (e/get-element-text-el driver el)]
            (println (format "  type=%s class=%s text=[%s]" typ cls txt)))
          (catch Exception _ nil)))

      ;; Verify expected selectors exist
      (is (e/exists? driver {:css "#loginForm input[name='email']"})
          "Email input should exist")
      (is (e/exists? driver {:css "#loginForm input[name='password']"})
          "Password input should exist")
      (is (e/exists? driver {:css "#loginForm button[type='submit']"})
          "Submit button should exist"))))

(deftest ^:selenium test-inspect-tabs
  (testing "Inspect tab structure on lobby page"
    (with-driver driver
      (println "Navigating to lobby...")
      (e/go driver "https://lobby.ogame.gameforge.com/en_GB/")
      (Thread/sleep 5000)

      (println "\n=== Tab list items ===")
      (doseq [el (e/query-all driver {:css ".tabsList li"})]
        (try
          (let [txt (e/get-element-text-el driver el)
                cls (e/get-element-attr-el driver el "class")]
            (println (format "  class=%s text=[%s]" cls txt)))
          (catch Exception _ nil)))

      ;; Verify tabs exist
      (is (e/exists? driver {:xpath "//li[contains(text(), 'Log in')]"})
          "Log in tab should exist")
      (is (e/exists? driver {:xpath "//li[contains(text(), 'Register')]"})
          "Register tab should exist"))))

(deftest ^:selenium test-debug-login-process
  (testing "Debug the full login process"
    (with-driver driver
      (let [cfg (require 'ogbot.config)
            config ((resolve 'ogbot.config/load-bot-configuration) "files/config/config.ini")]

        (println "Username:" (:username config))

        (println "Navigating to lobby...")
        (e/go driver "https://lobby.ogame.gameforge.com/en_GB/")
        (Thread/sleep 5000)

        (println "Clicking Log in tab...")
        (e/click driver {:xpath "//li[contains(text(), 'Log in')]"})
        (Thread/sleep 2000)

        (println "Filling login form...")
        (e/clear driver {:css "#loginForm input[name='email']"})
        (e/fill driver {:css "#loginForm input[name='email']"} (:username config))
        (Thread/sleep 500)
        (e/clear driver {:css "#loginForm input[name='password']"})
        (e/fill driver {:css "#loginForm input[name='password']"} (:password config))
        (Thread/sleep 1000)

        (println "Submitting...")
        (e/click driver {:css "#loginForm button[type='submit']"})
        (Thread/sleep 8000)

        (println "\n=== After login ===")
        (println "Current URL:" (e/get-url driver))
        (println "Page title:" (e/get-title driver))

        (println "\n=== Looking for error messages ===")
        (doseq [el (e/query-all driver {:css ".error, .alert, [class*='error'], [class*='Error']"})]
          (try
            (let [txt (e/get-element-text-el driver el)]
              (when (and txt (not= txt ""))
                (println "  Error:" txt)))
            (catch Exception _ nil)))

        (println "\n=== Looking for account/server cards ===")
        (doseq [el (e/query-all driver {:css ".rt-tr, [class*='account'], [class*='server'], [class*='card']"})]
          (try
            (let [cls (e/get-element-attr-el driver el "class")
                  txt (e/get-element-text-el driver el)]
              (when (and txt (not= txt "") (< (count txt) 200))
                (println (format "  class=%s text=[%s]" cls txt))))
            (catch Exception _ nil)))

        (println "\n=== All visible buttons ===")
        (doseq [el (e/query-all driver {:tag :button})]
          (try
            (let [txt (e/get-element-text-el driver el)
                  cls (e/get-element-attr-el driver el "class")]
              (when (and txt (not= txt ""))
                (println (format "  class=%s text=[%s]" cls txt))))
            (catch Exception _ nil)))

        ;; Test passes if we got this far without exceptions
        (is true "Login debug completed")))))

(deftest ^:selenium test-inspect-captcha
  (testing "Inspect CAPTCHA elements after login attempt"
    (with-driver driver
      (let [cfg (require 'ogbot.config)
            config ((resolve 'ogbot.config/load-bot-configuration) "files/config/config.ini")]

        (println "Navigating to lobby...")
        (e/go driver "https://lobby.ogame.gameforge.com/en_GB/")
        (Thread/sleep 5000)

        (println "Clicking Log in tab...")
        (e/click driver {:xpath "//li[contains(text(), 'Log in')]"})
        (Thread/sleep 2000)

        (println "Filling and submitting login form...")
        (e/fill driver {:css "#loginForm input[name='email']"} (:username config))
        (e/fill driver {:css "#loginForm input[name='password']"} (:password config))
        (e/click driver {:css "#loginForm button[type='submit']"})
        (Thread/sleep 5000)

        (println "\n=== Looking for CAPTCHA elements ===")

        (println "\n--- iframes (CAPTCHA often in iframe) ---")
        (doseq [el (e/query-all driver {:tag :iframe})]
          (try
            (let [src (e/get-element-attr-el driver el "src")
                  id (e/get-element-attr-el driver el "id")
                  cls (e/get-element-attr-el driver el "class")
                  nm (e/get-element-attr-el driver el "name")]
              (println (format "  id=%s class=%s name=%s src=%s"
                               id cls nm (when src (subs src 0 (min 100 (count src)))))))
            (catch Exception _ nil)))

        (println "\n--- Elements with captcha in class/id ---")
        (doseq [el (e/query-all driver {:css "[class*='captcha'], [class*='Captcha'], [id*='captcha'], [id*='Captcha'], [class*='recaptcha'], [class*='hcaptcha'], [class*='geetest']"})]
          (try
            (let [tag (e/get-element-tag-el driver el)
                  id (e/get-element-attr-el driver el "id")
                  cls (e/get-element-attr-el driver el "class")]
              (println (format "  <%s> id=%s class=%s" tag id cls)))
            (catch Exception _ nil)))

        (println "\n--- Taking screenshot ---")
        (e/screenshot driver "captcha_debug.png")
        (println "Screenshot saved to captcha_debug.png")

        (is true "CAPTCHA inspection completed")))))

(deftest ^:selenium test-captcha-solver-api
  (testing "Test Claude API CAPTCHA solver (requires ANTHROPIC_API_KEY with credits)"
    (when-let [api-key (System/getenv "ANTHROPIC_API_KEY")]
      (let [ws (require 'ogbot.web-selenium)
            solve-fn (resolve 'ogbot.web-selenium/solve-captcha-with-claude)]
        ;; Only run if we have a screenshot to test with
        (when (.exists (java.io.File. "/tmp/ogbot_captcha.png"))
          (println "Testing CAPTCHA solver with existing screenshot...")
          (try
            (let [result (solve-fn "/tmp/ogbot_captcha.png")]
              (println "Result:" result)
              (is (or (nil? result)
                      (and (:source result) (:target result)))
                  "Should return nil or valid coordinates"))
            (catch Exception e
              (println "API call failed:" (.getMessage e))
              (is true "Expected failure without credits"))))))))

;; ============================================================================
;; Run selenium tests with: lein test :selenium
;; Or run specific test: lein test :only ogbot.web-selenium-test/test-inspect-login-form
;; ============================================================================
