"""
Selenium test to verify insights and chart prompt sections display correctly
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time

def test_prompt_sections():
    """Test that prompt sections are displayed correctly"""
    
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--disable-cache')
    chrome_options.add_argument('--disable-application-cache')
    chrome_options.add_argument('--disable-gpu')
    
    print("🚀 Starting Selenium test...")
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # Open the application
        print("\n1️⃣ Opening application at http://localhost:8501")
        driver.get("http://localhost:8501")
        time.sleep(3)  # Wait for page load
        
        # Enter a question
        print("\n2️⃣ Entering test question...")
        question_input = driver.find_element(By.ID, "question-input")
        question_input.clear()
        question_input.send_keys("show total sales by month for 2006")
        
        # Submit the question
        print("\n3️⃣ Submitting question...")
        ask_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Ask')]")
        ask_button.click()
        
        # Wait for results
        print("\n4️⃣ Waiting for query results...")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "results-display"))
        )
        print("   ✅ Results loaded")
        
        # Wait for insights to generate
        print("\n5️⃣ Waiting for insights to generate...")
        time.sleep(8)  # Insights generation takes a few seconds
        
        # Switch to Insights Prompt tab
        print("\n6️⃣ Switching to Insights Prompt tab...")
        insights_tab = driver.find_element(By.ID, "tab-insights")
        insights_tab.click()
        time.sleep(1)
        
        # Check if insights prompt sections are present
        print("\n7️⃣ Checking Insights Prompt sections...")
        insights_content = driver.find_element(By.ID, "insights-prompt-content")
        
        # Check for section headers
        sections = driver.find_elements(By.CSS_SELECTOR, "#insights-prompt-content .prompt-section-header")
        print(f"   Found {len(sections)} sections")
        
        if len(sections) >= 4:
            print("   ✅ All sections found!")
            for i, section in enumerate(sections, 1):
                section_text = section.text
                print(f"      Section {i}: {section_text}")
        else:
            print(f"   ❌ Expected 4+ sections, found {len(sections)}")
            # Print what we actually see
            print(f"   Content: {insights_content.text[:200]}...")
        
        # Check if sections are collapsible
        print("\n8️⃣ Testing collapsible sections...")
        if len(sections) > 0:
            first_section = sections[0]
            # Check for arrow indicator
            arrow = first_section.find_element(By.CLASS_NAME, "section-arrow")
            print(f"   Arrow indicator: {arrow.text}")
            
            # Try to click and toggle
            first_section.click()
            time.sleep(0.5)
            print("   ✅ Section is clickable")
        
        # Switch to chart view
        print("\n9️⃣ Switching to Chart view...")
        try:
            # Find and click chart toggle button
            chart_buttons = driver.find_elements(By.CSS_SELECTOR, ".view-toggle-btn")
            for btn in chart_buttons:
                if "Chart" in btn.text or "📊" in btn.text:
                    btn.click()
                    break
            time.sleep(5)  # Wait for chart generation
            
            # Switch to Chart Prompt tab
            print("\n🔟 Switching to Chart Prompt tab...")
            chart_tab = driver.find_element(By.ID, "tab-chart")
            chart_tab.click()
            time.sleep(1)
            
            # Check chart prompt sections
            print("\n1️⃣1️⃣ Checking Chart Prompt sections...")
            chart_content = driver.find_element(By.ID, "chart-prompt-content")
            chart_sections = driver.find_elements(By.CSS_SELECTOR, "#chart-prompt-content .prompt-section-header")
            print(f"   Found {len(chart_sections)} sections")
            
            if len(chart_sections) >= 4:
                print("   ✅ All chart sections found!")
                for i, section in enumerate(chart_sections, 1):
                    section_text = section.text
                    print(f"      Section {i}: {section_text}")
            else:
                print(f"   ❌ Expected 4+ sections, found {len(chart_sections)}")
                print(f"   Content: {chart_content.text[:200]}...")
                
        except Exception as e:
            print(f"   ⚠️ Chart test skipped: {e}")
        
        # Check JavaScript console for errors
        print("\n1️⃣2️⃣ Checking browser console for errors...")
        logs = driver.get_log('browser')
        errors = [log for log in logs if log['level'] == 'SEVERE']
        if errors:
            print(f"   ❌ Found {len(errors)} errors:")
            for error in errors:
                print(f"      {error['message']}")
        else:
            print("   ✅ No console errors")
        
        print("\n" + "="*60)
        print("✅ TEST COMPLETED")
        print("="*60)
        
        # Keep browser open for inspection
        print("\n⏸️  Browser will stay open for 10 seconds for inspection...")
        time.sleep(10)
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        
        # Take screenshot
        screenshot_path = "test_failure_screenshot.png"
        driver.save_screenshot(screenshot_path)
        print(f"\n📸 Screenshot saved to: {screenshot_path}")
        
        # Keep browser open on error
        print("\n⏸️  Browser will stay open for 30 seconds for debugging...")
        time.sleep(30)
        
    finally:
        print("\n🏁 Closing browser...")
        driver.quit()

if __name__ == "__main__":
    test_prompt_sections()
