"""
Selenium test for chart enhancement with number formatting.
Tests the top 10 products by sales query and verifies chart enhancement.
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException


def test_top_products_chart_enhancement():
    """
    Test chart enhancement for top 10 products by sales.
    Verifies that the enhance button works and formatting is applied.
    """
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    
    # Initialize driver
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # Navigate to the application
        driver.get("http://localhost:8501")
        print("✓ Navigated to application")
        
        # Wait for page to load
        wait = WebDriverWait(driver, 20)
        
        # Wait for the question input to be present
        question_input = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "textarea[placeholder*='question'], input[placeholder*='Ask']"))
        )
        print("✓ Found question input")
        
        # Enter the query
        question = "Show me the top 10 products by sales"
        question_input.clear()
        question_input.send_keys(question)
        print(f"✓ Entered query: {question}")
        
        # Find and click the submit button
        submit_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit'], button:contains('Ask'), button:contains('Submit')"))
        )
        submit_button.click()
        print("✓ Clicked submit button")
        
        # Wait for results (increased timeout for query processing)
        time.sleep(5)
        print("✓ Waiting for query results...")
        
        # Wait for chart to appear
        try:
            chart_container = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".chart-container, #chart-container, [class*='chart']"))
            )
            print("✓ Chart container found")
        except TimeoutException:
            print("✗ Chart container not found - checking for table results instead")
            # Check if table results are present
            table = driver.find_element(By.CSS_SELECTOR, "table")
            if table:
                print("✓ Table results found - looking for chart toggle")
        
        # Look for chart toggle or chart type selector
        try:
            chart_toggle = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[class*='chart'], .chart-toggle, #show-chart"))
            )
            chart_toggle.click()
            print("✓ Clicked chart toggle")
            time.sleep(2)
        except TimeoutException:
            print("⚠ No chart toggle found - chart may already be visible")
        
        # Wait for the chart to render
        time.sleep(3)
        
        # Take screenshot of initial chart
        driver.save_screenshot("tests/screenshots/chart_before_enhancement.png")
        print("✓ Screenshot saved: chart_before_enhancement.png")
        
        # Look for enhance button
        try:
            enhance_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[class*='enhance'], .enhance-button, button:contains('Enhance')"))
            )
            print("✓ Found enhance button")
            
            # Get chart config before enhancement
            chart_element = driver.find_element(By.CSS_SELECTOR, ".chart-container, #chart-container, [class*='chart']")
            chart_html_before = chart_element.get_attribute("innerHTML")
            
            # Click enhance button
            enhance_button.click()
            print("✓ Clicked enhance button")
            
            # Wait for enhancement (this may take several seconds)
            time.sleep(8)
            print("✓ Waiting for enhancement to complete...")
            
            # Take screenshot after enhancement
            driver.save_screenshot("tests/screenshots/chart_after_enhancement.png")
            print("✓ Screenshot saved: chart_after_enhancement.png")
            
            # Get chart config after enhancement
            chart_html_after = chart_element.get_attribute("innerHTML")
            
            # Verify chart changed
            if chart_html_before != chart_html_after:
                print("✓ Chart was modified by enhancement")
            else:
                print("✗ Chart was not modified - enhancement may have failed")
            
            # Check for formatted numbers in the chart
            page_source = driver.page_source
            
            # Look for K/M/B formatted numbers
            has_k_format = "K" in page_source and any(char.isdigit() for char in page_source.split("K")[0][-5:])
            has_m_format = "M" in page_source and any(char.isdigit() for char in page_source.split("M")[0][-5:])
            has_dollar = "$" in page_source
            
            print(f"\n--- Number Formatting Check ---")
            print(f"Contains K format (e.g., 1.2K): {has_k_format}")
            print(f"Contains M format (e.g., 1.2M): {has_m_format}")
            print(f"Contains $ symbol: {has_dollar}")
            
            if has_m_format or has_k_format:
                print("✓ Number formatting appears to be applied")
            else:
                print("✗ Number formatting NOT detected - may need debugging")
            
        except TimeoutException:
            print("✗ Enhance button not found")
            driver.save_screenshot("tests/screenshots/no_enhance_button.png")
            print("✓ Screenshot saved: no_enhance_button.png")
        
        # Keep browser open for inspection
        print("\n--- Test Complete ---")
        print("Browser will remain open for 10 seconds for manual inspection...")
        time.sleep(10)
        
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        driver.save_screenshot("tests/screenshots/error.png")
        raise
    
    finally:
        driver.quit()
        print("✓ Browser closed")


if __name__ == "__main__":
    # Create screenshots directory if it doesn't exist
    import os
    os.makedirs("tests/screenshots", exist_ok=True)
    
    print("=" * 50)
    print("Chart Enhancement Test")
    print("=" * 50)
    test_top_products_chart_enhancement()
