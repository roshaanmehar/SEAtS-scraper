import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from collections import Counter

# --- 1. CONFIGURATION: UPDATE THESE VALUES ---

# --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- ---
# The URL for the SEAtS login page
LOGIN_URL = "https://your-seats-login-url.com"

# The URL of the page that shows your attendance (after you've logged in)
ATTENDANCE_PAGE_URL = "https://your-seats-url.com/angular/attendance"

# --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- ---


def scrape_seats_attendance():
    """
    Opens browser, asks user to log in manually, then scrapes attendance.
    """
    print("--- SEAtS Attendance Scraper ---")
    driver = webdriver.Chrome()
    
    try:
        # --- 1. Manual Login ---
        driver.get(LOGIN_URL)
        print("\n" + "="*50)
        print("A browser window has opened. Please log in to SEAtS manually.")
        print("After you are successfully logged in and on the main dashboard,")
        print("press Enter in this console window to continue...")
        print("="*50)
        
        # Pause the script and wait for the user to press Enter
        input() 
        
        print("Login complete. Navigating to attendance page...")

        # --- 2. Navigate to Attendance Page ---
        # This ensures we are on the correct page after you log in
        driver.get(ATTENDANCE_PAGE_URL)
        
        # Wait for the lecture cards to be loaded.
        # Based on your HTML, 'mat-card-content' is a good locator.
        wait = WebDriverWait(driver, 30) # Wait up to 30 seconds
        
        # This locator finds ALL elements with the class 'mat-mdc-card-content'
        card_locator = (By.CSS_SELECTOR, "mat-card-content.grid-container")
        
        print("Waiting for attendance cards to load...")
        wait.until(EC.presence_of_element_located(card_locator))
        print("Cards loaded. Starting scrape...")
        
        # Get all lecture cards
        lecture_cards = driver.find_elements(*card_locator)
        
        all_lectures = []
        
        # --- 3. Scrape Data ---
        for card in lecture_cards:
            try:
                # Get all text from the card
                card_text = card.text
                
                # --- A. Check for your "Stop Condition" ---
                if "Scheduled Absence" in card_text and "IECT not enrolled" in card_text:
                    print("---")
                    print("Reached 'Scheduled Absence' entry. Stopping scrape.")
                    print(f"Stop Entry Details: {card_text.replace('\n', ' | ')}")
                    print("---")
                    break # Exit the loop
                
                # --- B. Parse the status ---
                status = "Unknown"
                
                # We find the status by looking for the icon's class.
                # This is an educated guess based on your 'Authorised' example.
                # We look for an <i> tag with a class containing 'fa fa-'
                icon = card.find_element(By.CSS_SELECTOR, "i[class*='fa fa-']")
                icon_class = icon.get_attribute("class")
                
                # !!! IMPORTANT !!!
                # You MUST inspect the HTML for "Present" and "Absent"
                # to see what their icon classes are and update this logic.
                if "present" in icon_class: # This is a guess!
                    status = "Present"
                elif "authorized-absent" in icon_class: # From your example
                    status = "Authorized"
                elif "absent" in icon_class: # This is a guess!
                    status = "Absent"
                else:
                    # Fallback: check the text content if icon class is not found
                    if "Present" in card_text:
                        status = "Present"
                    elif "Authorised" in card_text or "Authorized" in card_text:
                        status = "Authorized"
                    elif "Absent" in card_text:
                        status = "Absent"

                all_lectures.append(status)
                
            except Exception as e:
                # This might catch cards that aren't lectures (e.g., headers)
                print(f"Could not parse a card. Skipping. (This is common for non-lecture cards)")

        
        # --- 4. Calculate and Print Stats ---
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
        print("Scraping finished. Closing browser.")
        driver.quit()


# --- Main execution ---
if __name__ == "__main__":
    scrape_seats_attendance()