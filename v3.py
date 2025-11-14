import time
import json
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from collections import Counter

# --- 1. CONFIGURATION: UPDATE THESE VALUES ---

# --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- ---
# The URL for the SEAtS login page
LOGIN_URL = "https://hull.seats.cloud/"

# The URL of the page that shows your attendance (after you've logged in)
ATTENDANCE_PAGE_URL = "https://hull.seats.cloud/angular/#/me"

# The name of the file to store your session data
SESSION_FILE = "seats_session.json"

# --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- ---


def save_session_data(driver):
    """
    Saves cookies, localStorage, and sessionStorage to a file.
    """
    print("Saving session data...")
    session_data = {
        'cookies': driver.get_cookies(),
        'local_storage': driver.execute_script("return window.localStorage;"),
        'session_storage': driver.execute_script("return window.sessionStorage;")
    }
    with open(SESSION_FILE, 'w') as f:
        json.dump(session_data, f)
    print(f"Session data saved to {SESSION_FILE}")


def load_session_data(driver):
    """
    Loads cookies, localStorage, and sessionStorage from a file.
    
    NOTE: This requires visiting the domain *before* loading data.
    """
    print(f"Loading session data from {SESSION_FILE}...")
    with open(SESSION_FILE, 'r') as f:
        session_data = json.load(f)

    # We must be on the domain to set data
    # We'll go to the base login URL first
    driver.get(LOGIN_URL) 

    # Load Cookies
    for cookie in session_data['cookies']:
        # Selenium can be picky about cookie domains
        if 'domain' in cookie:
            del cookie['domain']
        driver.add_cookie(cookie)

    # Load Local Storage
    driver.execute_script(
        "var data = arguments[0]; "
        "for (var key in data) { "
        "  window.localStorage.setItem(key, data[key]); "
        "}",
        session_data['local_storage']
    )
    
    # Load Session Storage
    driver.execute_script(
        "var data = arguments[0]; "
        "for (var key in data) { "
        "  window.sessionStorage.setItem(key, data[key]); "
        "}",
        session_data['session_storage']
    )
    print("Session data loaded.")


def first_time_login():
    """
    Opens browser, asks user to log in manually, then saves the session.
    """
    print("--- First-Time Login ---")
    print("A browser window will open. Please log in to SEAtS manually.")
    print("After you are successfully logged in and on the main dashboard,")
    print("press Enter in this console window to continue...")

    driver = webdriver.Chrome()
    driver.get(LOGIN_URL)

    # Wait for the user to press Enter
    input() 

    # User has logged in, now save the session
    save_session_data(driver)
    driver.quit()
    print("Login complete. You can now run the script normally.")


def scrape_attendance_data():
    """
    Loads the saved session, navigates to the attendance page,
    and scrapes all lecture data.
    """
    print("--- Scraping Attendance Data ---")
    driver = webdriver.Chrome()
    
    try:
        # Load the session *before* navigating to the target page
        load_session_data(driver)
        
        # Now, go to the attendance page
        driver.get(ATTENDANCE_PAGE_URL)
        
        # Wait for the lecture cards to be loaded.
        # Based on your HTML, 'mat-card-content' is a good locator.
        wait = WebDriverWait(driver, 30) # Wait up to 30 seconds
        
        # This locator finds ALL elements with the class 'mat-mdc-card-content'
        # that are also inside the main angular app root.
        # You may need to make this more specific.
        card_locator = (By.CSS_SELECTOR, "mat-card-content.grid-container")
        
        print("Waiting for attendance cards to load...")
        wait.until(EC.presence_of_element_located(card_locator))
        print("Cards loaded. Starting scrape...")
        
        # Get all lecture cards
        lecture_cards = driver.find_elements(*card_locator)
        
        all_lectures = []
        
        for card in lecture_cards:
            try:
                # Get all text from the card
                card_text = card.text
                
                # --- 1. Check for your "Stop Condition" ---
                if "Scheduled Absence" in card_text and "IECT not enrolled" in card_text:
                    print("---")
                    print("Reached 'Scheduled Absence' entry. Stopping scrape.")
                    print(f"Stop Entry Details: {card_text.replace('\n', ' | ')}")
                    print("---")
                    break # Exit the loop
                
                # --- 2. Parse the status ---
                status = "Unknown"
                
                # We find the status by looking for the icon's class.
                # This is an educated guess based on your 'Authorised' example.
                # We look for an <i> tag with a class containing 'fa fa-'
                icon = card.find_element(By.CSS_SELECTOR, "i[class*='fa fa-']")
                icon_class = icon.get_attribute("class")
                
                # You MUST inspect the HTML for "Present" and "Absent"
                # to see what their icon classes are and update this logic.
                if "present" in icon_class:
                    status = "Present"
                elif "authorized-absent" in icon_class: # From your example
                    status = "Authorized"
                elif "absent" in icon_class: # This is a guess!
                    status = "Absent"
                else:
                    # Fallback: check the text content
                    if "Present" in card_text:
                        status = "Present"
                    elif "Authorised" in card_text or "Authorized" in card_text:
                        status = "Authorized"
                    elif "Absent" in card_text:
                        status = "Absent"

                all_lectures.append(status)
                
            except Exception as e:
                # This might catch cards that aren't lectures (e.g., headers)
                print(f"Could not parse a card. Skipping. Error: {e}")

        
        # --- 3. Calculate and Print Stats ---
        if not all_lectures:
            print("No lectures were found. Exiting.")
            return

        print("\n--- Scraping Complete. Calculating Stats... ---")
        
        stats = Counter(all_lectures)
        
        present_count = stats.get("Present", 0)
        absent_count = stats.get("Absent", 0)
        authorized_count = stats.get("Authorized", 0)
        unknown_count = stats.get("Unknown", 0)
        total_lectures = len(all_lectures)
        
        print(f"Total Entries Scraped: {total_lectures}")
        print(f"  - Present:    {present_count}")
        print(f"  - Absent:     {absent_count}")
        print(f"  - Authorized: {authorized_count}")
        print(f"  - Unknown:    {unknown_count}")

        # Your formula: (Present / (Total - Authorized)) * 100
        denominator = total_lectures - authorized_count
        
        if denominator > 0:
            attendance_percentage = (present_count / denominator) * 100
            print("---")
            print(f"Total Attendance: {attendance_percentage:.2f}%")
            print(f"(Calculated as: ({present_count} / ({total_lectures} - {authorized_count})) * 100)")
        else:
            print("---")
            print("Could not calculate attendance (no valid lectures).")

    except Exception as e:
        print(f"An error occurred during scraping: {e}")
    finally:
        driver.quit()


# --- Main execution ---
if __name__ == "__main__":
    if not os.path.exists(SESSION_FILE):
        # File doesn't exist, run the first-time login
        first_time_login()
    else:
        # Session file exists, run the scraper
        scrape_attendance_data()