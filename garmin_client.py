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
        driver.get('https://connect.garmin.com/signin/')

        wait.until(EC.visibility_of_element_located((By.ID, 'email'))).send_keys(
            os.getenv('GARMIN_EMAIL'))  # userame/email
        wait.until(EC.visibility_of_element_located((By.ID, 'password'))).send_keys(
            os.getenv('GARMIN_PASSWORD'))  # password
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@class='g__button g__button--contained "
                                                         "g__button--contained--large g__button--contained--ocean-blue' "
                                                         "and @data-testid='g__button' and @type='submit']"))).click()

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
                                               "//a[@href='' and @class='main-nav-link' and contains(.//span[@class='nav-text'], 'Activities')]"))).click()
        wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@href='/modern/activities']"))).click()

    def open_calendar_view(self, driver, wait):
        wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@href='/modern/calendar']"))).click()

    def click_first_activity_in_overview(self, driver, wait):
        element = wait.until(EC.presence_of_element_located((By.XPATH, "//li[@class='list-item animated row-fluid']")))
        link = element.find_element(By.CSS_SELECTOR, "a.inline-edit-target")
        link.click()

    def click_previous_button(self, driver, wait):
        self.click_element(driver, wait, (By.XPATH, "//button[@class='page-previous page-navigation-action' and @aria-label='Previous']"))

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
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.pull-left.activity-detail-title")))
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
        nameElement = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "span.inline-edit-target.page-title-overflow")))
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
        self.click_element(driver, wait, (By.XPATH, "//button[@class='inline-edit-trigger modal-trigger' and @aria-label='Edit']"))
        actions = ActionChains(driver)
        actions.send_keys(correspondingStravaActivity['name'])
        actions.perform()
        self.click_element(driver, wait,
                           (By.XPATH, "//button[@class='inline-edit-save icon-checkmark' and @aria-label='Save']"))

        element = wait.until(
            EC.presence_of_element_located((By.XPATH, "//a[@class='edit-note-button colored' and @href='#']")))
        if element.value_of_css_property("display") != "none":
            self.click_element(driver, wait, element)

        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                descriptionTextarea = wait.until(EC.presence_of_element_located(
                    (By.XPATH, "//textarea[@class='noteTextarea']")))
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
                           (By.XPATH, "//button[@class='btn btn-small add-note-button' and text()='Save']"))

def main():
    driver = uc.Chrome(headless=False, use_subprocess=False)
    wait = WebDriverWait(driver, 20)

    client = GarminClient()

    client.login(driver, wait)
    elements = client.get_all_activities_displayed_in_overview(driver, wait)
    print(client.open_activity_in_new_tab_and_get_date(driver, wait, elements[0]))

if __name__ == "__main__":
    main()