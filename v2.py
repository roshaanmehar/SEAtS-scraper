import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def calculate_attendance(lectures):
    """Calculates attendance statistics from a list of lecture statuses."""
    total_lectures = len(lectures)
    present = lectures.count("Present")
    absent = lectures.count("Absent")
    authorised_absent = lectures.count("Authorised Absent (Physical)") # Adjust as needed

    # Calculate attendance percentage
    # Formula: (Present / (Total - Authorised)) * 100
    effective_total = total_lectures - authorised_absent
    if effective_total > 0:
        attendance_percentage = (present / effective_total) * 100
    else:
        attendance_percentage = 100.0

    # Print the stats
    print("--- Attendance Statistics ---")
    print(f"Total Lectures Recorded: {total_lectures}")
    print(f"Present: {present}")
    print(f"Absent: {absent}")
    print(f"Authorised Absences: {authorised_absent}")
    print(f"Overall Attendance Percentage: {attendance_percentage:.2f}%")

def seats_attendance_scraper():
    """
    Scrapes attendance data from the SEAtS portal.
    """
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 20)
    
    # Navigate to the login page
    driver.get("https://hull.seats.cloud/angular/#/me") # Replace with the actual URL

    # --- Authentication Handling ---
    try:
        # Try to load cookies for automatic login
        with open("seats_cookies.json", "r") as f:
            cookies = json.load(f)
            for cookie in cookies:
                driver.add_cookie(cookie)
        
        # Refresh the page to apply cookies
        driver.refresh()
        
        # You might need to navigate to the attendance page directly here
        # driver.get("YOUR_SEATS_ATTENDANCE_URL")

    except FileNotFoundError:
        # If cookies file doesn't exist, handle manual login
        print("Cookies not found. Please log in manually.")
        # You would add a long wait here to allow the user to log in
        input("After you have logged in, press Enter to continue...")

        # Save cookies for future sessions
        with open("seats_cookies.json", "w") as f:
            json.dump(driver.get_cookies(), f)
    
    # --- Scraping the Attendance Data ---
    print("Scraping attendance data...")
    
    lecture_statuses = []
    
    # Wait for the lecture cards to be present
    wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "mat-card-content.grid-container")))
    
    # Find all the lecture entry cards
    lecture_cards = driver.find_elements(By.CSS_SELECTOR, "mat-card-content.grid-container")
    
    for card in lecture_cards:
        try:
            # Extract the status text. This selector will need to be precise.
            # Based on your HTML, it seems the status is within a div.
            status_element = card.find_element(By.CSS_SELECTOR, "div[aria-label*='Item,']")
            status_text = status_element.get_attribute('aria-label').split(',')[1].strip()

            # Stop scraping if we reach the specified conditions
            if "Scheduled Absence" in status_text or "IECT not enrolled" in status_text:
                print("Reached the stopping point. Ending scrape.")
                break
                
            lecture_statuses.append(status_text)
            
        except Exception as e:
            # This can help debug if the structure of a card is different
            print(f"Could not process a card: {e}")

    # Close the browser
    driver.quit()
    
    # --- Calculate and Display Statistics ---
    if lecture_statuses:
        calculate_attendance(lecture_statuses)
    else:
        print("No lecture data was scraped.")


if __name__ == "__main__":
    seats_attendance_scraper()