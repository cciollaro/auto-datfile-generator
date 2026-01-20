import os
import time
import zipfile
import shutil
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Define the systems we want to scrape (Name: ID)
SYSTEMS = {
    "Nintendo - Nintendo Entertainment System": "45",
    "Nintendo - Super Nintendo Entertainment System": "49",
    "Nintendo - Nintendo 64": "24",
    "Nintendo - Game Boy": "39",
    "Nintendo - Game Boy Color": "57",
    "Nintendo - Game Boy Advance": "23",
    "Nintendo - GameCube": "28"
}

def main():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    
    # Configure Firefox
    options = webdriver.FirefoxOptions()
    options.set_preference("browser.download.folderList", 2)
    options.set_preference("browser.download.manager.showWhenStarting", False)
    options.set_preference("browser.download.dir", dir_path)
    options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/zip, text/xml, application/xml, text/plain, application/octet-stream")
    options.add_argument("-headless") 

    service = webdriver.FirefoxService(log_output="firefox-webdriver.log", service_args=["--log", "debug"])
    driver = webdriver.Firefox(service=service, options=options)
    wait = WebDriverWait(driver, 60) # Increased timeout to 60s

    downloaded_files = []

    try:
        print("Starting Custom DAT Scraper (v2)...")

        for sys_name, sys_id in SYSTEMS.items():
            print(f"Processing: {sys_name} (ID: {sys_id})")
            
            # Navigate to Standard DAT page
            url = f"https://datomatic.no-intro.org/index.php?page=download&s={sys_id}&op=dat"
            driver.get(url)
            
            # Application/Wait logic
            try:
                # Wait for Prepare button
                prepare_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='submit' and @value='Prepare']")))
            except Exception as e:
                print(f"  - Failed to load form: {e}")
                # Debug: print page source snippet
                print(f"  - Source snippet: {driver.page_source[:500]}")
                continue
            
            # --- Apply Settings ---
            # Using try/passes aggressively to ensure we keep going even if a checkbox is missing (e.g. GB might not have aftermarket)
            
            # 1. Aftermarket (Life span) -> lifespan_2
            try:
                am_box = driver.find_element(By.NAME, "lifespan_2")
                if not am_box.is_selected():
                    am_box.click()
                    print("  - Enabled Aftermarket")
            except:
                pass # Checkbox might not exist for this system

            # 2. MIA ROMs -> inc_mia value="2" (tagged)
            try:
                mia_tagged = driver.find_element(By.XPATH, "//input[@name='inc_mia' and @value='2']")
                if not mia_tagged.is_selected():
                    mia_tagged.click()
                    print("  - Enabled MIA (Tagged)")
            except:
                pass

            # 3. Format -> Headered (value="0") ONLY for NES
            if "Nintendo Entertainment System" in sys_name and "Super" not in sys_name:
                try:
                    headered = driver.find_element(By.XPATH, "//input[@name='format' and @value='0']")
                    if not headered.is_selected():
                        headered.click()
                        print("  - Set Format: Headered")
                except:
                    pass

            # --- Download ---
            try:
                prepare_btn.click()
                print("  - 'Prepare' clicked...")
            except Exception as e:
                print(f"  - Error clicking Prepare: {e}")
                continue

            # Wait Loop for File or Secondary "Download" Button
            found_new_file = False
            start_time = time.time()
            initial_files = set([f for f in os.listdir(dir_path) if not f.endswith('.part')])
            
            # Check for a secondary "Download" button appearing
            # Sometimes "Prepare" reloads the page with a "Download" button
            try:
                 # We wait up to 10s for either a file to appear OR a download button
                 # But file monitoring is continuous. 
                 # Let's check for Download button intermittently.
                 pass
            except:
                pass
            
            while time.time() - start_time < 90: # 90s total wait
                # Check file system
                current_files = set([f for f in os.listdir(dir_path) if not f.endswith('.part')])
                new_files = current_files - initial_files
                for f in new_files:
                    if f.endswith(".dat") or f.endswith(".zip"):
                        print(f"  - Downloaded: {f}")
                        downloaded_files.append(f)
                        found_new_file = True
                        break
                if found_new_file:
                    break
                
                # Check for secondary button
                try:
                    dl_btn = driver.find_elements(By.XPATH, "//input[@value='Download']")
                    if dl_btn:
                        dl_btn[0].click()
                        print("  - Clicked secondary 'Download' button...")
                        # Reset start time to give it time to download? Or just continue loop?
                        # Continuing loop is safer, don't want to get stuck.
                        time.sleep(2) 
                except:
                    pass
                
                time.sleep(1)

            if not found_new_file:
                print("  - TIMEOUT: No file received.")
                # Look for error messages on page
                try:
                    body_text = driver.find_element(By.TAG_NAME, "body").text
                    print(f"  - Page text dump: {body_text[:200]}...")
                except:
                    pass

    except Exception as e:
        print(f"Global Error: {e}")
    finally:
        driver.quit()

    # Package
    print("\nPackage Creation...")
    archive_name = "no-intro.zip"
    archive_path = os.path.join(dir_path, archive_name)
    
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        if not downloaded_files:
            print("Warning: No files downloaded. Archive will be empty.")
        
        for f in downloaded_files:
            file_path = os.path.join(dir_path, f)
            if not os.path.exists(file_path):
                print(f"Skipping missing file: {f}")
                continue
                
            if f.endswith(".zip"):
                try:
                    with zipfile.ZipFile(file_path, 'r') as subzip:
                        for name in subzip.namelist():
                            if name.endswith(".dat"):
                                content = subzip.read(name)
                                zf.writestr(name, content)
                                print(f"  - Added {name} from {f}")
                except Exception as e:
                    print(f"Error reading {f}: {e}")
            elif f.endswith(".dat"):
                zf.write(file_path, arcname=f)
                print(f"  - Added {f}")

    print(f"\nFinal Archive Created: {archive_path}")

if __name__ == "__main__":
    main()
