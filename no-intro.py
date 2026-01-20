import os
import time
import zipfile
import shutil
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Define the systems we want to scrape (Name: ID)
# IDs sourced from Dat-O-Matic
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
    options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/zip, text/xml, application/xml, text/plain")
    options.add_argument("-headless") 

    service = webdriver.FirefoxService(log_output="firefox-webdriver.log", service_args=["--log", "debug"])
    driver = webdriver.Firefox(service=service, options=options)
    wait = WebDriverWait(driver, 30)

    downloaded_files = []

    try:
        print("Starting Custom DAT Scraper...")

        for sys_name, sys_id in SYSTEMS.items():
            print(f"Processing: {sys_name} (ID: {sys_id})")
            
            # Navigate to Standard DAT page for this system
            url = f"https://datomatic.no-intro.org/index.php?page=download&s={sys_id}&op=dat"
            driver.get(url)
            
            # Wait for form to load
            try:
                # Wait for the "Prepare" button
                wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='submit' and @value='Prepare']")))
            except:
                print(f"  - Failed to load form for {sys_name}. Skipping.")
                continue

            # --- Apply Settings ---
            
            # 1. Aftermarket (Life span) -> lifespan_2
            try:
                am_box = driver.find_element(By.NAME, "lifespan_2")
                if not am_box.is_selected():
                    am_box.click()
                    print("  - Enabled Aftermarket")
            except Exception as e:
                print(f"  - Warning: Aftermarket checkbox not found or error: {e}")

            # 2. MIA ROMs -> inc_mia value="2" (tagged)
            try:
                mia_tagged = driver.find_element(By.XPATH, "//input[@name='inc_mia' and @value='2']")
                if not mia_tagged.is_selected():
                    mia_tagged.click()
                    print("  - Enabled MIA (Tagged)")
            except Exception as e:
                # Fallback: some forms might not have MIA options or different layout?
                print(f"  - Warning: MIA Tagged option not found: {e}")

            # 3. Format -> Headered (value="0") ONLY for NES
            # Note: For other systems, we generally want default (Headerless/No plugin) or whatever is standard.
            # Myrient standardizes on Headered for NES.
            if "Nintendo Entertainment System" in sys_name and "Super" not in sys_name:
                try:
                    headered = driver.find_element(By.XPATH, "//input[@name='format' and @value='0']")
                    if not headered.is_selected():
                        headered.click()
                        print("  - Set Format: Headered")
                except:
                    pass

            # --- Download ---
            
            # Click "Prepare"
            try:
                prepare_btn = driver.find_element(By.XPATH, "//input[@type='submit' and @value='Prepare']")
                prepare_btn.click()
                print("  - Request submitted...")
            except Exception as e:
                print(f"  - Failed to click download button: {e}")
                continue

            # Wait for the download button (sometimes it changes to a "Download" button after Prepare?)
            # Observe behavior: "Prepare" usually POSTs and triggers a download OR shows a "Download" button on next page.
            # Let's assume it might lead to a secondary page OR trigger download.
            # no-intro.py logic suggested a click, then wait.
            # In "Standard DAT" mode on the site: Clicking "Prepare" usually downloads the file directly or reloads page with "Download".
            # The HTML shows `action=""`, so it posts to self.
            # Let's wait and see if a file appears.
            
            # Better strategy: Wait for a new button "Download" if "Prepare" was just a generator.
            # But commonly on Dat-O-Matic, "Prepare" triggers the generation and serves the file.
            
            # Wait for file arrival
            found_new_file = False
            start_time = time.time()
            initial_files = set(os.listdir(dir_path))
            
            # If "Prepare" redirects to a "Download" button page:
            try:
                # Check if a "Download" button appeared (Value="Download")
                # wait.until(EC.presence_of_element_located((By.XPATH, "//input[@value='Download']")))
                # If so, click it.
                # But let's try just waiting for file first.
                pass
            except:
                pass

            while time.time() - start_time < 30: # 30s timeout
                current_files = set(os.listdir(dir_path))
                new_files = current_files - initial_files
                
                for f in new_files:
                    if f.endswith(".dat") or f.endswith(".zip") and not f.endswith(".part"):
                        # Found it!
                        print(f"  - Downloaded: {f}")
                        downloaded_files.append(f)
                        found_new_file = True
                        break
                if found_new_file:
                    break
                time.sleep(1)
            
            if not found_new_file:
                 # Check if we are on a "Download" page
                try:
                    download_btn = driver.find_element(By.XPATH, "//input[@value='Download']")
                    download_btn.click()
                    print("  - Clicked secondary Download button...")
                    # Wait again
                    start_time = time.time()
                    while time.time() - start_time < 30:
                        current_files = set(os.listdir(dir_path))
                        new_files = current_files - initial_files
                        for f in new_files:
                            if not f.endswith(".part") and (f.endswith(".dat") or f.endswith(".zip")):
                                print(f"  - Downloaded: {f}")
                                downloaded_files.append(f)
                                found_new_file = True
                                break
                        if found_new_file: break
                        time.sleep(1)
                except:
                    print("  - No file received.")

            time.sleep(2) # Cooldown

    except Exception as e:
        print(f"Global Error: {e}")
    finally:
        driver.quit()

    # Create the final archive: no-intro.zip
    print("\nPackage Creation...")
    archive_name = "no-intro.zip"
    archive_path = os.path.join(dir_path, archive_name)
    
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in downloaded_files:
            file_path = os.path.join(dir_path, f)
            # If it's a dat, add it. If it's a zip, extract valid dats?
            # Dat-O-Matic standard download usually gives a .zip containing the .dat
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
            
            # Cleanup source file
            # os.remove(file_path) # Optional: keep for debug? Action runner cleans up.

    print(f"\nFinal Archive Created: {archive_path}")

if __name__ == "__main__":
    main()
