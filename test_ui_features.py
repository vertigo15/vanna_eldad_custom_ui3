"""Test UI features using Selenium."""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time

def test_sort_and_filter():
    """Test table sorting and filtering functionality."""
    
    # Setup Chrome driver
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run in background
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--ignore-certificate-errors')
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # Navigate to the app
        print("1. Opening http://localhost:8501...")
        driver.get('http://localhost:8501')
        time.sleep(2)
        
        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "question-input"))
        )
        print("✓ Page loaded")
        
        # Enter a question
        print("\n2. Entering question...")
        question_input = driver.find_element(By.ID, "question-input")
        question_input.send_keys("What are the top 10 products by sales?")
        
        # Submit question
        print("3. Submitting question...")
        question_input.send_keys(Keys.RETURN)
        
        # Wait for results (up to 30 seconds for LLM response)
        print("4. Waiting for results...")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "results-table"))
        )
        print("✓ Results table loaded")
        time.sleep(1)
        
        # Check if filter input exists
        print("\n5. Checking filter input...")
        try:
            filter_input = driver.find_element(By.ID, "result-filter")
            print(f"✓ Filter input found: {filter_input.get_attribute('placeholder')}")
        except Exception as e:
            print(f"✗ Filter input NOT found: {e}")
            driver.save_screenshot("filter_input_missing.png")
            return False
        
        # Check console for errors
        print("\n6. Checking browser console...")
        logs = driver.get_log('browser')
        errors = [log for log in logs if log['level'] == 'SEVERE']
        if errors:
            print("✗ Console errors found:")
            for error in errors:
                print(f"  - {error['message']}")
        else:
            print("✓ No console errors")
        
        # Test filter functionality
        print("\n7. Testing filter...")
        filter_input.clear()
        filter_input.send_keys("Road")
        time.sleep(1)
        
        # Count visible rows
        rows = driver.find_elements(By.CSS_SELECTOR, "#results-table tbody tr.data-row")
        print(f"✓ Rows after filter: {len(rows)}")
        
        # Check row count text
        row_count = driver.find_element(By.ID, "row-count")
        print(f"✓ Row count text: {row_count.text}")
        
        # Clear filter
        print("\n8. Clearing filter...")
        filter_input.clear()
        time.sleep(1)
        rows_after_clear = driver.find_elements(By.CSS_SELECTOR, "#results-table tbody tr.data-row")
        print(f"✓ Rows after clear: {len(rows_after_clear)}")
        
        # Test sorting
        print("\n9. Testing sort...")
        headers = driver.find_elements(By.CSS_SELECTOR, "#results-table thead th")
        print(f"✓ Found {len(headers)} column headers")
        
        if headers:
            print(f"10. Clicking first column header: {headers[0].text}")
            
            # Check if onclick is present
            onclick = headers[0].get_attribute('onclick')
            print(f"   onclick attribute: {onclick}")
            
            headers[0].click()
            time.sleep(1)
            
            # Check for sort icon
            header_text = headers[0].text
            print(f"   Header after click: {header_text}")
            if '▲' in header_text or '▼' in header_text:
                print("✓ Sort icon appeared!")
            else:
                print("✗ No sort icon visible")
        
        # Get final console logs
        print("\n11. Final console check...")
        logs = driver.get_log('browser')
        for log in logs[-10:]:  # Last 10 logs
            print(f"   [{log['level']}] {log['message']}")
        
        # Take screenshot
        print("\n12. Saving screenshot...")
        driver.save_screenshot("test_results.png")
        print("✓ Screenshot saved as test_results.png")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        driver.save_screenshot("test_error.png")
        print("✓ Error screenshot saved as test_error.png")
        
        # Print page source for debugging
        with open("page_source.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("✓ Page source saved as page_source.html")
        
        return False
        
    finally:
        driver.quit()


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Sort and Filter Functionality")
    print("=" * 60)
    success = test_sort_and_filter()
    print("\n" + "=" * 60)
    if success:
        print("✓ TEST PASSED")
    else:
        print("✗ TEST FAILED")
    print("=" * 60)
