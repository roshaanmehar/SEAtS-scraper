import time
from collections import Counter

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ========= CONFIG =========
BASE_URL = "https://<your-seats-domain-here>/"  # e.g. https://myschool.seatssoftware.com/
LOGIN_AND_NAV_TIMEOUT = 600  # seconds to give you to log in + open attendance page
# ==========================


def create_driver(headless=False):
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--start-maximized")
    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )


def wait_for_user_login_and_attendance_page(driver):
    """
    1. Open SEAtS base URL.
    2. You log in manually in the browser.
    3. You navigate to the attendance page that shows the lecture cards.
    4. Script waits until it can see mat-card-content.grid-container.
    """
    print("Opening SEAtS in a browser window...")
    driver.get(BASE_URL)

    print(
        "\n=== ACTION REQUIRED ===\n"
        "- Log in manually in the SEAtS window.\n"
        "- Navigate to the page that lists your lectures/attendance.\n"
        "- Once you can see the list of lectures, I will automatically start scraping.\n"
    )

    # Wait until Angular has rendered the cards.
    WebDriverWait(driver, LOGIN_AND_NAV_TIMEOUT).until(
        EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, "mat-card-content.grid-container")
        )
    )

    print("Detected attendance cards on the page. Starting scrape...\n")


def get_text_or_empty(card, aria_prefix):
    """
    Helper: find element with aria-label starting with aria_prefix and return text.
    """
    try:
        el = card.find_element(By.CSS_SELECTOR, f"[aria-label^='{aria_prefix}']")
        return el.text.strip()
    except Exception:
        return ""


def extract_lecture_from_card(card):
    """
    Given a <mat-card-content class='grid-container'> element,
    extract structured information.
    """
    full_text = card.text.strip()

    # Status label (e.g. "Authorised Absent (Physical)")
    status_text = ""
    try:
        # The mobile layout often uses aria-label="Item, Authorised Absent (Physical)"
        status_el = card.find_element(By.CSS_SELECTOR, "[aria-label^='Item,']")
        status_text = status_el.text.strip()
    except Exception:
        # Fallback: first cell
        try:
            first_cell = card.find_elements(By.CSS_SELECTOR, "div[role='cell']")[0]
            status_text = first_cell.text.strip()
        except Exception:
            status_text = ""

    # Icon classes (e.g. "fa fa-authorized-absent-attended icon")
    icon_classes = ""
    try:
        icon_el = card.find_element(By.CSS_SELECTOR, "i.icon")
        icon_classes = icon_el.get_attribute("class") or ""
    except Exception:
        icon_classes = ""

    details = get_text_or_empty(card, "Details")
    comment = get_text_or_empty(card, "Comment")
    user = get_text_or_empty(card, "User")
    date_text = get_text_or_empty(card, "Date")

    return {
        "raw_text": full_text,
        "status": status_text,
        "icon_classes": icon_classes,
        "details": details,
        "comment": comment,
        "user": user,
        "date": date_text,
    }


def classify_lecture(rec):
    """
    Map a record to one of:
      - present
      - absent
      - skipped
      - authorised_absent
      - unknown
    """
    combined = " ".join([
        rec.get("status", ""),
        rec.get("comment", ""),
        rec.get("icon_classes", ""),
        rec.get("raw_text", "")
    ]).lower()

    # Authorised absences
    if "authorised absent" in combined or "authorized absent" in combined \
       or "authorized-absent" in combined:
        return "authorised_absent"

    # Present / attended (avoid false positive on "absent")
    if ("present" in combined or "attended" in combined) and "absent" not in combined:
        return "present"

    # Skipped / not attended (unexcused)
    if "skipped" in combined or "not attended" in combined or "did not attend" in combined:
        return "skipped"

    # Generic absent
    if "absent" in combined:
        return "absent"

    return "unknown"


def scrape_lectures(driver):
    """
    Scrape all lecture cards on the current page,
    stopping at 'Scheduled Absence ... IECT not enrolled'.
    """
    # Small pause for Angular to fully settle
    time.sleep(2)

    cards = driver.find_elements(By.CSS_SELECTOR, "mat-card-content.grid-container")
    lectures = []

    for card in cards:
        rec = extract_lecture_from_card(card)
        lower_text = rec["raw_text"].lower()

        # Stop condition: the block like
        # "Scheduled Absence\n\nIECT not enrolled\n\nIECT NE - CT 16/10/2025 (IT issues)\n\nCallum Thompson..."
        if "scheduled absence" in lower_text and "iect not enrolled" in lower_text:
            print("Reached 'Scheduled Absence / IECT not enrolled' section. Stopping scrape.")
            break

        rec["category"] = classify_lecture(rec)
        lectures.append(rec)

    print(f"Scraped {len(lectures)} lecture entries before Scheduled Absence block.")
    return lectures


def compute_stats(lectures):
    """
    Compute counts and attendance percentage.
    Attendance % = present / (total - authorised_absent) * 100
    """
    cats = [rec["category"] for rec in lectures]
    c = Counter(cats)

    total = len(lectures)
    present = c.get("present", 0)
    authorised_absent = c.get("authorised_absent", 0)
    absent = c.get("absent", 0)
    skipped = c.get("skipped", 0)
    unknown = c.get("unknown", 0)

    effective_total = total - authorised_absent
    if effective_total > 0:
        attendance_pct = present / effective_total * 100.0
    else:
        attendance_pct = 0.0

    return {
        "total": total,
        "present": present,
        "absent": absent,
        "skipped": skipped,
        "authorised_absent": authorised_absent,
        "unknown": unknown,
        "effective_total": effective_total,
        "attendance_pct": attendance_pct,
    }


def main():
    driver = create_driver(headless=False)
    try:
        wait_for_user_login_and_attendance_page(driver)
        lectures = scrape_lectures(driver)
        stats = compute_stats(lectures)

        print("\n=== Sample of scraped lectures (first 5) ===")
        for rec in lectures[:5]:
            print(
                f"- {rec['date']} | {rec['status']} | {rec['comment']} "
                f"| {rec['category']} | {rec['details'][:60]}"
            )

        print("\n=== Attendance Stats ===")
        print(f"Total lectures:                {stats['total']}")
        print(f"Present:                       {stats['present']}")
        print(f"Absent (unexcused):            {stats['absent']}")
        print(f"Skipped / not attended:        {stats['skipped']}")
        print(f"Authorised absences:           {stats['authorised_absent']}")
        print(f"Unknown / unclassified:        {stats['unknown']}")
        print(f"Total used in calculation:     {stats['effective_total']} (total - authorised)")
        print(f"Attendance percentage:         {stats['attendance_pct']:.2f}%")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
