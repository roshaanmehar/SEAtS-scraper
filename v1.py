"""
SEAtS Attendance Scraper
Scrapes attendance records from SEAtS system with authentication and statistics
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import pickle
import os
import time
from datetime import datetime

class SEAtsScraper:
    def __init__(self, base_url, cookies_file="seats_cookies.pkl"):
        self.base_url = base_url
        self.cookies_file = cookies_file
        self.driver = None
        self.attendance_records = []
        
    def setup_driver(self):
        """Initialize Chrome driver with options"""
        options = webdriver.ChromeOptions()
        options.add_argument('--start-maximized')
        # Uncomment below to run headless
        # options.add_argument('--headless')
        options.add_argument('--disable-blink-features=AutomationControlled')
        self.driver = webdriver.Chrome(options=options)
        
    def save_cookies(self):
        """Save cookies to file"""
        with open(self.cookies_file, 'wb') as f:
            pickle.dump(self.driver.get_cookies(), f)
        print(f"✓ Cookies saved to {self.cookies_file}")
        
    def load_cookies(self):
        """Load cookies from file"""
        if os.path.exists(self.cookies_file):
            self.driver.get(self.base_url)
            with open(self.cookies_file, 'rb') as f:
                cookies = pickle.load(f)
                for cookie in cookies:
                    self.driver.add_cookie(cookie)
            print(f"✓ Cookies loaded from {self.cookies_file}")
            return True
        return False
        
    def authenticate(self):
        """Handle authentication process"""
        print("\n=== AUTHENTICATION ===")
        print("Please complete the login process in the browser window...")
        print("The script will wait for you to reach the attendance page.")
        
        self.driver.get(self.base_url)
        
        # Wait for user to complete authentication
        # Looking for attendance-specific elements
        try:
            WebDriverWait(self.driver, 300).until(
                lambda d: "attendance" in d.current_url.lower() or 
                         len(d.find_elements(By.CLASS_NAME, "mat-mdc-card-content")) > 0
            )
            print("✓ Authentication successful!")
            self.save_cookies()
            return True
        except TimeoutException:
            print("✗ Authentication timeout. Please try again.")
            return False
            
    def navigate_to_attendance(self):
        """Navigate to attendance page if not already there"""
        if "attendance" not in self.driver.current_url.lower():
            print("Navigating to attendance page...")
            # You may need to adjust this based on actual navigation
            # For now, assuming direct URL access
            attendance_url = f"{self.base_url}/attendance"
            self.driver.get(attendance_url)
            time.sleep(3)
            
    def should_stop_scraping(self, card_element):
        """Check if we've reached the stop condition"""
        try:
            text_content = card_element.text.lower()
            
            # Check for "not enrolled" or "scheduled absence"
            if "not enrolled" in text_content or "scheduled absence" in text_content:
                return True
                
            # Check for the specific pattern "IECT NE - CT"
            if "iect ne" in text_content or "ne - ct" in text_content:
                return True
                
            return False
        except:
            return False
            
    def parse_attendance_card(self, card):
        """Parse individual attendance card element"""
        try:
            record = {}
            
            # Find all div elements within the card
            cells = card.find_elements(By.CSS_SELECTOR, "div[role='cell']")
            
            # Extract status/icon
            try:
                icon = card.find_element(By.CSS_SELECTOR, "i.fa")
                icon_class = icon.get_attribute("class")
                
                if "authorized-absent" in icon_class:
                    record['status'] = "Authorised Absent"
                elif "present" in icon_class or "attended" in icon_class:
                    record['status'] = "Present"
                elif "absent" in icon_class:
                    record['status'] = "Absent"
                else:
                    record['status'] = "Unknown"
            except NoSuchElementException:
                record['status'] = "Unknown"
            
            # Extract details, comment, user, and date from cells
            for cell in cells:
                aria_label = cell.get_attribute("aria-label") or ""
                text = cell.text.strip()
                
                if "Details," in aria_label:
                    record['details'] = text
                elif "Comment," in aria_label:
                    record['comment'] = text
                elif "User," in aria_label:
                    record['user'] = text
                elif "Date," in aria_label:
                    record['date'] = text
                    
            return record
        except Exception as e:
            print(f"Error parsing card: {e}")
            return None
            
    def scrape_attendance(self):
        """Scrape all attendance records until stop condition"""
        print("\n=== SCRAPING ATTENDANCE ===")
        
        # Wait for cards to load
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "mat-mdc-card-content"))
            )
        except TimeoutException:
            print("✗ No attendance cards found")
            return []
            
        # Scroll to load all content
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            
        # Find all attendance cards
        cards = self.driver.find_elements(By.CLASS_NAME, "mat-mdc-card-content")
        print(f"Found {len(cards)} attendance cards")
        
        for i, card in enumerate(cards, 1):
            # Check stop condition
            if self.should_stop_scraping(card):
                print(f"\n✓ Reached stop condition at card {i}")
                break
                
            record = self.parse_attendance_card(card)
            if record:
                self.attendance_records.append(record)
                print(f"  [{i}] {record.get('status', 'Unknown')} - {record.get('date', 'No date')}")
                
        return self.attendance_records
        
    def calculate_statistics(self):
        """Calculate attendance statistics"""
        if not self.attendance_records:
            return None
            
        stats = {
            'total_lectures': len(self.attendance_records),
            'present': 0,
            'absent': 0,
            'authorised_absent': 0,
            'unknown': 0
        }
        
        for record in self.attendance_records:
            status = record.get('status', 'Unknown').lower()
            
            if 'present' in status or 'attended' in status:
                stats['present'] += 1
            elif 'authorised' in status or 'authorized' in status:
                stats['authorised_absent'] += 1
            elif 'absent' in status:
                stats['absent'] += 1
            else:
                stats['unknown'] += 1
                
        # Calculate attendance percentage
        # Formula: (Present / (Total - Authorised Absent)) * 100
        denominator = stats['total_lectures'] - stats['authorised_absent']
        if denominator > 0:
            stats['attendance_percentage'] = (stats['present'] / denominator) * 100
        else:
            stats['attendance_percentage'] = 0
            
        return stats
        
    def print_statistics(self):
        """Print attendance statistics"""
        stats = self.calculate_statistics()
        
        if not stats:
            print("\n✗ No attendance data to analyze")
            return
            
        print("\n" + "="*50)
        print("ATTENDANCE STATISTICS")
        print("="*50)
        print(f"Total Lectures:        {stats['total_lectures']}")
        print(f"Present:               {stats['present']}")
        print(f"Absent:                {stats['absent']}")
        print(f"Authorised Absent:     {stats['authorised_absent']}")
        print(f"Unknown:               {stats['unknown']}")
        print("-"*50)
        print(f"Attendance %:          {stats['attendance_percentage']:.2f}%")
        print(f"(Present / (Total - Authorised) × 100)")
        print("="*50)
        
    def run(self, force_reauth=False):
        """Main execution flow"""
        try:
            self.setup_driver()
            
            # Try to load cookies if not forcing re-authentication
            if not force_reauth and self.load_cookies():
                print("Attempting to use saved session...")
                self.driver.refresh()
                time.sleep(3)
                
                # Check if still authenticated
                if "login" in self.driver.current_url.lower():
                    print("Session expired. Re-authenticating...")
                    if not self.authenticate():
                        return
            else:
                # Fresh authentication
                if not self.authenticate():
                    return
                    
            # Navigate to attendance page
            self.navigate_to_attendance()
            
            # Scrape attendance
            self.scrape_attendance()
            
            # Print statistics
            self.print_statistics()
            
        except Exception as e:
            print(f"\n✗ Error: {e}")
        finally:
            input("\nPress Enter to close the browser...")
            if self.driver:
                self.driver.quit()


# Usage
if __name__ == "__main__":
    # Replace with your actual SEAtS URL
    SEATS_URL = "https://hull.seats.cloud/angular/#/me"
    
    scraper = SEAtsScraper(SEATS_URL)
    
    # First run: force_reauth=True to authenticate
    # Subsequent runs: force_reauth=False to use saved cookies
    scraper.run(force_reauth=False)