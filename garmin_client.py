import datetime
import re

import os
import time

import unicodedata
from dateutil import parser
from dotenv import load_dotenv
from selenium.common import StaleElementReferenceException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc

# Load environment variables from .env file
load_dotenv()

class GarminClient:
    def login(self, driver, wait):
        try:
            print("Navigating to Garmin login page...")
            # Try multiple possible login URLs
            login_urls = [
                'https://connect.garmin.com/signin/',
                'https://connect.garmin.com/modern/',
                'https://connect.garmin.com/',
                'https://sso.garmin.com/sso/signin'
            ]
            
            for url in login_urls:
                try:
                    print(f"Trying URL: {url}")
                    driver.get(url)
                    time.sleep(2)
                    
                    # Check if we got a valid login page
                    current_url = driver.current_url
                    page_source = driver.page_source.lower()
                    
                    if 'email' in page_source and 'password' in page_source:
                        print(f"Found valid login page at: {current_url}")
                        break
                    else:
                        print(f"URL {url} does not appear to be a login page")
                        continue
                except Exception as e:
                    print(f"Error accessing {url}: {e}")
                    continue
            else:
                # If we get here, none of the URLs worked
                raise Exception("Could not access any valid Garmin login page")
            
            # Wait for page to load completely
            print("Waiting for page to load...")
            wait.until(lambda driver: driver.execute_script("return document.readyState") == "complete")
            
            # Wait a bit more for dynamic content to load
            time.sleep(3)
            
            # Check if we're on the right page
            current_url = driver.current_url
            print(f"Current URL after navigation: {current_url}")
            
            # Check if there are any error messages or if the page loaded correctly
            try:
                page_title = driver.title
                print(f"Page title: {page_title}")
            except:
                print("Could not get page title")
            
            # Check if the page contains expected elements
            try:
                page_source = driver.page_source
                if 'email' not in page_source.lower() or 'password' not in page_source.lower():
                    print("Warning: Page may not have loaded correctly - missing expected form elements")
                    driver.save_screenshot('garmin_page_load_issue.png')
                    print("Screenshot saved as garmin_page_load_issue.png")
            except:
                print("Could not check page source")
            
            print("Looking for email field...")
            email_field = wait.until(EC.visibility_of_element_located((By.ID, 'email')))
            print("Email field found, entering credentials...")
            email_field.clear()
            email_field.send_keys(os.getenv('GARMIN_EMAIL'))
            
            print("Looking for password field...")
            password_field = wait.until(EC.visibility_of_element_located((By.ID, 'password')))
            print("Password field found, entering password...")
            password_field.clear()
            password_field.send_keys(os.getenv('GARMIN_PASSWORD'))
            
            print("Looking for login button...")
            # Try multiple possible selectors for the login button
            login_button = None
            button_selectors = [
                "//button[@class='g__button g__button--contained g__button--contained--large g__button--contained--ocean-blue' and @data-testid='g__button' and @type='submit']",
                "//button[@type='submit']",
                "//input[@type='submit']",
                "//button[contains(@class, 'g__button') and contains(@class, 'g__button--contained')]",
                "//button[contains(text(), 'Sign In')]",
                "//button[contains(text(), 'Login')]",
                "//button[contains(text(), 'Log In')]"
            ]
            
            for selector in button_selectors:
                try:
                    print(f"Trying selector: {selector}")
                    login_button = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    print(f"Found login button with selector: {selector}")
                    break
                except:
                    print(f"Selector failed: {selector}")
                    continue
            
            if login_button is None:
                raise Exception("Could not find login button with any of the tried selectors")
            
            print("Clicking login button...")
            login_button.click()
            
            # Wait for login to complete (look for redirect or success indicators)
            print("Waiting for login to complete...")
            time.sleep(5)
            
            # Check for potential CAPTCHA or security challenges
            try:
                captcha_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'captcha') or contains(text(), 'CAPTCHA') or contains(text(), 'verify') or contains(text(), 'security')]")
                if captcha_elements:
                    print("Warning: Potential CAPTCHA or security challenge detected")
                    driver.save_screenshot('garmin_captcha_detected.png')
                    print("Screenshot saved as garmin_captcha_detected.png")
            except:
                pass
            
            # Check if we're still on the login page (indicating login failed)
            current_url = driver.current_url
            print(f"URL after login attempt: {current_url}")
            
            if 'signin' in current_url.lower() or 'login' in current_url.lower():
                print("Still on login page, login may have failed")
                # Check for error messages
                try:
                    error_elements = driver.find_elements(By.XPATH, "//*[contains(@class, 'error') or contains(@class, 'alert') or contains(text(), 'invalid') or contains(text(), 'incorrect')]")
                    if error_elements:
                        for element in error_elements:
                            print(f"Error message found: {element.text}")
                except:
                    pass
                
                # Take a screenshot for debugging
                driver.save_screenshot('garmin_login_failed.png')
                print("Screenshot saved as garmin_login_failed.png")
                raise Exception("Login failed - still on login page after attempt")
            else:
                print(f"Login successful, redirected to: {current_url}")
                
        except Exception as e:
            print(f"Error during Garmin login: {e}")
            # Take a screenshot for debugging
            try:
                driver.save_screenshot('garmin_login_error.png')
                print("Screenshot saved as garmin_login_error.png")
            except:
                pass
            raise

    def click_element(self, driver, wait, p_element):
        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                element = wait.until(EC.element_to_be_clickable(p_element))
                element.click()
                break
            except StaleElementReferenceException:
                retry_count += 1
                print(f"Stale element reference exception, retrying ({retry_count}/{max_retries})")
        if retry_count == max_retries:
            raise Exception("Failed to click previous button after max retries")

    def get_activity_date_from_list(self, driver, wait, element):
        driver.execute_script("arguments[0].scrollIntoView(true);", element)

        date_div = element.find_element(By.XPATH, ".//div[@class='pull-left activity-date date-col']")
        date_spans = date_div.find_elements(By.TAG_NAME, "span")
        date_text = " ".join([span.text for span in date_spans])

        # Convert date text to datetime object
        month_abbr, day, year = date_text.split()
        month_num = datetime.datetime.strptime(month_abbr, '%b').month
        date_obj = datetime.datetime(int(year), month_num, int(day))

        # Find link with class inline-edit-target and open in new tab
        actions = ActionChains(driver)
        actions.key_down(Keys.CONTROL).perform()
        link = element.find_element(By.CSS_SELECTOR, "a.inline-edit-target")
        actions.click(link).key_up(Keys.CONTROL).perform()
        driver.switch_to.window(driver.window_handles[-1])

        # Find span with class activity-title-time and extract time
        time_span = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "span.activity-title-time"))
        )
        time_text = time_span.text.strip()

        # Parse time text to datetime object
        time_obj = parser.parse(time_text)

        # Combine date and time objects
        date_obj = date_obj.replace(hour=time_obj.hour, minute=time_obj.minute)

        # Close new tab
        driver.close()
        driver.switch_to.window(driver.window_handles[-1])

        return date_obj

    def open_activity_overview(self, driver, wait):
        wait.until(EC.element_to_be_clickable((By.XPATH,
                                               "//button[@class='MainSidebar_menuItemLink__ec-sE' and @aria-label='Activities']"))).click()
        wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@class='MainSidebar_menuItemLink__ec-sE MainSidebar_menuItemLinkChild__AsXDn' and @aria-label='All Activities']"))).click()

    def open_calendar_view(self, driver, wait):
        wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@href='/modern/calendar']"))).click()

    def click_first_activity_in_overview(self, driver, wait):
        # Wait for the new modern interface activity list
        element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.ActivityListItem_listItem__aoJjV")))
        link = element.find_element(By.CSS_SELECTOR, "a[href*='/modern/activity/']")
        link.click()

    def click_previous_button(self, driver, wait):
        self.click_element(driver, wait, (By.XPATH, "//button[@aria-label='View Previous']"))

    def get_all_activities_after_date(self, driver, wait, date):
        comparisonDate = datetime.datetime.strptime(date, '%Y-%m-%d %H:%M:%S')

        while True:
            elements = wait.until(
                EC.presence_of_all_elements_located((By.XPATH, "//li[@class='list-item animated row-fluid']")))
            if len(elements) == 0 or self.get_activity_date_from_list(driver, wait, elements[-1]) <= comparisonDate:
                break
            time.sleep(2)

        return elements

    def get_all_activities_displayed_in_overview(self, driver, wait):
        """
            Waits for the presence of activity list items, then retrieves all activity elements.

            Args:
                wait (WebDriverWait): An instance of WebDriverWait
                driver (WebDriver): An instance of WebDriver

            Returns:
                list: A list of all activity elements
            """
        wait.until(EC.presence_of_element_located((By.XPATH, "//li[@class='list-item animated row-fluid']")))
        elements_list = driver.find_elements(By.XPATH, "//li[@class='list-item animated row-fluid']")
        return elements_list

    def get_date_time_from_activity(self, driver, wait):
        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                html_element = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "span.ActivityMetaInfo_time__HcDIK")))
                text = html_element.text.strip().lower()
                break
            except StaleElementReferenceException:
                retry_count += 1
                print(f"Stale element reference exception, retrying ({retry_count}/{max_retries})")
        if retry_count == max_retries:
            raise Exception("Failed to access element after max retries")

        # Check if the text contains "today", "yesterday", or a day of the week
        today = datetime.date.today()
        if "today" in text:
            dt = today
        elif "yesterday" in text:
            dt = today - datetime.timedelta(days=1)
        else:
            day_of_week = text.split(" ")[-4]
            if day_of_week in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
                day_of_week_num = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"].index(
                    day_of_week)
                dt = today - datetime.timedelta(days=(today.weekday() - day_of_week_num) % 7)
            else:
                date_parts = text.replace(",", "").split()[-6:]
                month, day, year, *_ = date_parts
                dt = parser.parse(f"{month} {day}, {year}")

        # Check if the text contains a time in the format "HH:MM AM/PM"
        time_match = re.search(r"(\d{1,2}):(\d{2}) (am|pm)", text)
        if time_match:
            hour, minute, am_pm = time_match.groups()
            hour = int(hour)
            if am_pm == "pm" and hour != 12:
                hour += 12
            dt = datetime.datetime.combine(dt, datetime.time(hour, int(minute)))

        return dt

    def get_name_from_activity(self, driver, wait):
        nameElement = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "span.InlineEdit_label__PShOX")))
        name = nameElement.text
        return name

    def open_activity_in_new_tab_and_get_date(self, driver, wait, element):
        driver.execute_script("arguments[0].scrollIntoView(true);", element)

        # Find link with class inline-edit-target and open in new tab
        actions = ActionChains(driver)
        actions.key_down(Keys.CONTROL).perform()
        link = element.find_element(By.CSS_SELECTOR, "a.inline-edit-target")
        actions.click(link).key_up(Keys.CONTROL).perform()
        driver.switch_to.window(driver.window_handles[-1])

        dt = self.get_date_time_from_activity(driver, wait)
        return dt

    def edit_current_garmin_activity(self, driver, wait, correspondingStravaActivity):
        self.click_element(driver, wait, (By.XPATH, "//button[@class='InlineEdit_editIcon__7vqhd' and @aria-label='Edit']"))
        actions = ActionChains(driver)
        actions.send_keys(correspondingStravaActivity['name'])
        actions.perform()
        self.click_element(driver, wait,
                           (By.XPATH, "//button[@class='InlineEdit_saveIcon__+WjjM' and @aria-label='Save']"))

        # Note: The edit note button structure has changed in the new Garmin website
        # The textarea is now directly accessible without needing to click an edit button

        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                descriptionTextarea = wait.until(EC.presence_of_element_located(
                    (By.XPATH, "//textarea[@aria-label='How was your run?']")))
                self.click_element(driver, wait, descriptionTextarea)
                actions = ActionChains(driver)
                actions.send_keys(correspondingStravaActivity['description'])
                actions.perform()
                break
            except StaleElementReferenceException:
                retry_count += 1
                print(f"Stale element reference exception, retrying ({retry_count}/{max_retries})")
        if retry_count == max_retries:
            raise Exception("Failed to click previous button after max retries")

        self.click_element(driver, wait,
                           (By.XPATH, "//button[@class='Button_btn__g8LLk Button_primary__7zt4j Button_small__waifo' and text()='Save']"))

def main():
    driver = uc.Chrome(headless=False, use_subprocess=False)
    wait = WebDriverWait(driver, 20)

    client = GarminClient()

    client.login(driver, wait)
    elements = client.get_all_activities_displayed_in_overview(driver, wait)
    print(client.open_activity_in_new_tab_and_get_date(driver, wait, elements[0]))

if __name__ == "__main__":
    main()