"""
SEAtS Attendance Scraper
Scrapes attendance records from SEAtS system with manual authentication
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time

class SEAtsScraper:
    def __init__(self, base_url):
        self.base_url = base_url
        self.driver = None
        self.attendance_records = []
        
    def setup_driver(self):
        """Initialize Chrome driver with options"""
        options = webdriver.ChromeOptions()
        options.add_argument('--start-maximized')
        options.add_argument('--disable-blink-features=AutomationControlled')
        self.driver = webdriver.Chrome(options=options)
        
    def wait_for_authentication(self):
        """Wait for user to complete authentication manually"""
        print("\n=== MANUAL AUTHENTICATION REQUIRED ===")
        print("Please complete the login process in the browser window...")
        print("Navigate to your attendance page...")
        print("Waiting for attendance cards to appear...")
        
        self.driver.get(self.base_url)
        
        # Wait for attendance cards to be present
        try:
            WebDriverWait(self.driver, 600).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".mat-mdc-card-content.grid-container"))
            )
            print("✓ Authentication successful! Attendance page loaded.")
            time.sleep(2)  # Give it a moment to fully load
            return True
        except TimeoutException:
            print("✗ Timeout waiting for attendance page. Please try again.")
            return False
            
    def should_stop_scraping(self, card_element):
        """Check if we've reached the stop condition"""
        try:
            text_content = card_element.text.lower()
            
            # Check for stop conditions
            stop_phrases = [
                "not enrolled",
                "scheduled absence",
                "iect ne",
                "ne - ct"
            ]
            
            for phrase in stop_phrases:
                if phrase in text_content:
                    print(f"  ⚠ Stop condition found: '{phrase}'")
                    return True
                    
            return False
        except:
            return False
            
    def parse_attendance_card(self, card):
        """Parse individual attendance card element"""
        try:
            record = {}
            
            # Get the full text for debugging
            full_text = card.text
            
            # Extract status from icon
            try:
                icon = card.find_element(By.CSS_SELECTOR, "i.fa")
                icon_class = icon.get_attribute("class")
                color = icon.get_attribute("style")
                
                # Determine status based on icon class and color
                if "authorized-absent" in icon_class or "authorised-absent" in icon_class:
                    record['status'] = "Authorised Absent"
                elif "present" in icon_class or "attended" in icon_class:
                    record['status'] = "Present"
                elif "absent" in icon_class:
                    record['status'] = "Absent"
                else:
                    # Try to determine from color
                    if "94, 226, 160" in color:  # Green color for authorized
                        record['status'] = "Authorised Absent"
                    else:
                        record['status'] = "Unknown"
            except NoSuchElementException:
                record['status'] = "Unknown"
            
            # Extract information from cells with aria-labels
            cells = card.find_elements(By.CSS_SELECTOR, "div[role='cell']")
            
            for cell in cells:
                aria_label = cell.get_attribute("aria-label") or ""
                text = cell.text.strip()
                
                if not text:
                    continue
                    
                # Parse based on aria-label
                if "Item," in aria_label and not record.get('item'):
                    # Extract the status text (e.g., "Authorised Absent (Physical)")
                    record['item'] = text
                elif "Details," in aria_label:
                    record['details'] = text
                elif "Comment," in aria_label:
                    record['comment'] = text
                elif "User," in aria_label:
                    record['user'] = text
                elif "Date," in aria_label:
                    record['date'] = text
            
            # Fallback: if we didn't get status from icon, try from item or comment
            if record['status'] == "Unknown":
                item_text = (record.get('item', '') + ' ' + record.get('comment', '')).lower()
                if 'authorised' in item_text or 'authorized' in item_text:
                    record['status'] = "Authorised Absent"
                elif 'present' in item_text or 'attended' in item_text:
                    record['status'] = "Present"
                elif 'absent' in item_text:
                    record['status'] = "Absent"
                    
            return record
        except Exception as e:
            print(f"  ✗ Error parsing card: {e}")
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
    SEATS_URL = "https://your-university-seats-url.com/angular/"
    
    scraper = SEAtsScraper(SEATS_URL)
    
    # First run: force_reauth=True to authenticate
    # Subsequent runs: force_reauth=False to use saved cookies
    scraper.run(force_reauth=False)