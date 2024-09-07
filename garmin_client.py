import os
import time

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import undetected_chromedriver as uc

# Load environment variables from .env file
load_dotenv()

class GarminClient:
    def scrollDown(self, driver, wait):
        page_height = driver.execute_script("return document.body.scrollHeight")
        driver.execute_script("window.scrollTo(0, {});".format(page_height))

    def login(self, driver, wait):
        driver.get('https://connect.garmin.com/signin/')

        wait.until(EC.visibility_of_element_located((By.ID, 'email'))).send_keys(
            os.getenv('GARMIN_EMAIL'))  # userame/email
        wait.until(EC.visibility_of_element_located((By.ID, 'password'))).send_keys(
            os.getenv('GARMIN_PASSWORD'))  # password
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@class='g__button g__button--contained "
                                                         "g__button--contained--large g__button--contained--ocean-blue' "
                                                         "and @data-testid='g__button' and @type='submit']"))).click()

    def get_activity_list(self, driver, wait, activityNum):
        self.login(driver, wait)

        wait.until(EC.element_to_be_clickable((By.XPATH,
                                               "//a[@href='' and @class='main-nav-link' and contains(.//span[@class='nav-text'], 'Activities')]"))).click()
        wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@href='/modern/activities']"))).click()

        wait.until(EC.visibility_of_element_located((By.XPATH, "//li[@class='list-item animated row-fluid']")))
        elements = driver.find_elements(By.XPATH, "//li[@class='list-item animated row-fluid']")

        while len(elements) < activityNum:
            elements[-1].location_once_scrolled_into_view
            time.sleep(2)
            elements = driver.find_elements(By.XPATH,"//li[@class='list-item animated row-fluid']")  # Update the elements list

        return elements

def main():
    driver = uc.Chrome(headless=False, use_subprocess=False)
    wait = WebDriverWait(driver, 20)

    client = GarminClient()

    client.get_activity_list(driver=driver, wait=wait, activityNum=400)

if __name__ == "__main__":
    main()