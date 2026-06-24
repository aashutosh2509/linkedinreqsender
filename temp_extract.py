import time
import os
import csv
import threading
import random
from automation import launch_browser, get_account_state, scrape_contact_info, load_db, save_db

def extract_connections_worker(account_id):
    acc_state = get_account_state(account_id)
    acc_state.add_log(f"Starting temporary connection extraction for {account_id}...", "info")
    
    playwright = None
    context = None
    try:
        # Check if already running something?
        if acc_state.is_running:
            acc_state.add_log("Account is already running a task. Stop it first.", "warning")
            return
            
        acc_state.start_running()
        acc_state.update_status(action="Extracting Connections", progress=0)
        
        playwright, context = launch_browser(account_id, headed=True)
        page = context.new_page()
        
        # Navigate to connections
        acc_state.add_log("Navigating to LinkedIn connections page...", "info")
        page.goto("https://www.linkedin.com/mynetwork/invite-connect/connections/", timeout=45000)
        
        # Wait a bit for the page to load
        time.sleep(8)
        
        # Save entire page content for debugging
        html_content = page.content()
        debug_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_page.html")
        with open(debug_file_path, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        acc_state.add_log("DEBUG: Saved page HTML to debug_page.html. AI agent is analyzing it now.", "info")
        
        prospects_db = load_db(account_id, "prospects")
        existing_usernames = set()
        for p in prospects_db:
            p_url = p.get("profile_url", "").strip()
            if "linkedin.com/in/" in p_url:
                uname = p_url.strip("/").split("/")[-1]
                if uname: existing_usernames.add(uname)

        acc_state.add_log("Scrolling to find 15 new organic connections...", "info")
        
        # We will collect connections inside the loop to handle virtualized lists
        all_extracted_connections = {}
        no_change_count = 0
        last_count = 0
        
        for _ in range(50):  # max 50 scrolls
            if acc_state.stop_requested:
                break
            
            # Extract currently visible connections
            current_batch = page.evaluate("""() => {
                const resultsMap = new Map();
                const links = document.querySelectorAll('a');
                for (const linkEl of links) {
                    if (!linkEl.href || !linkEl.href.includes('/in/')) continue;
                    
                    let href = linkEl.href.split('?')[0];
                    if (href.endsWith('/')) href = href.slice(0, -1);
                    const username = href.split('/').pop();
                    
                    if (!username || username === 'in' || username === 'linkedin') continue;
                    
                    const inNav = linkEl.closest('nav') || linkEl.closest('.global-nav') || linkEl.closest('footer');
                    if (inNav) continue;
                    
                    let text = linkEl.innerText.trim();
                    if (text && !text.toLowerCase().includes('view ')) {
                        let lines = text.split('\\n').map(l => l.trim()).filter(l => l);
                        let name = lines.length > 0 ? lines[0] : text;
                        let company = lines.length > 1 ? lines[1] : '';
                        
                        if (!resultsMap.has(username)) {
                            resultsMap.set(username, { username, name, company });
                        } else {
                            let existing = resultsMap.get(username);
                            if (!existing.name || existing.name === username) existing.name = name;
                            if (!existing.company) existing.company = company;
                        }
                    }
                }
                return Array.from(resultsMap.values());
            }""")
            
            for conn in current_batch:
                u = conn['username']
                # ONLY ADD IF THEY ARE NOT IN OUR EXISTING DATABASE (ORGANIC CONNECTION)
                if u not in existing_usernames:
                    if u not in all_extracted_connections:
                        all_extracted_connections[u] = conn
                    else:
                        if conn['name'] and not (all_extracted_connections[u]['name'] and all_extracted_connections[u]['name'] != u):
                            all_extracted_connections[u]['name'] = conn['name']
                        if conn['company']:
                            all_extracted_connections[u]['company'] = conn['company']

            # Check if we have found our 15 limit
            if len(all_extracted_connections) >= 15:
                break

            # Click "Show more results" button if it exists
            try:
                more_btn = page.query_selector("button.scaffold-finite-scroll__load-button")
                if more_btn and more_btn.is_visible():
                    more_btn.click()
                    time.sleep(2)
            except:
                pass
                
            page.evaluate("""() => {
                const cards = document.querySelectorAll('.mn-connection-card, li.mn-connection-card');
                if (cards && cards.length > 0) {
                    cards[cards.length - 1].scrollIntoView();
                } else {
                    const links = document.querySelectorAll('a[href*="/in/"]');
                    if (links && links.length > 0) {
                        links[links.length - 1].scrollIntoView();
                    } else {
                        window.scrollTo(0, document.body.scrollHeight);
                        window.scrollBy(0, 2000);
                    }
                }
            }""")
            time.sleep(3) # Wait for network
            
            current_count = len(all_extracted_connections)
            acc_state.add_log(f"Scrolled down. Found {current_count}/15 target organic connections so far...", "info")
            if current_count == last_count:
                no_change_count += 1
                if no_change_count >= 5: # wait for a few scrolls to be sure it's the bottom
                    break
            else:
                no_change_count = 0
                last_count = current_count
            
        connections = list(all_extracted_connections.values())[:15] # Strictly cap to 15
        acc_state.add_log(f"Found {len(connections)} new organic connections to extract today.", "success")
        # Output CSV path
        public_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
        os.makedirs(public_dir, exist_ok=True)
        csv_path = os.path.join(public_dir, f"connections_extract_{account_id}.csv")
        
        # We will now iterate through each extracted profile, visit it, and fetch contact info
        total = len(connections)
        acc_state.add_log(f"Found {total} connections. Starting deep extraction of Contact Info. This will take a long time to avoid bans...", "info")
        
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Username", "Name", "Company", "Email", "Phone", "Profile URL"])
            
            prospects_db = load_db(account_id, "prospects")
            
            for i, conn in enumerate(connections):
                if acc_state.stop_requested:
                    acc_state.add_log("Extraction stopped by user.", "warning")
                    break
                
                username = conn['username']
                name = conn['name']
                company = conn['company']
                profile_url = f"https://www.linkedin.com/in/{username}/"
                
                already_exists = False
                for c in prospects_db:
                    if c.get("profile_url", "").strip() == profile_url:
                        already_exists = True
                        break
                        
                if already_exists:
                    acc_state.add_log(f"[{i+1}/{total}] Skipping {name} - already exists in Lead Database.", "info")
                    continue
                
                acc_state.add_log(f"[{i+1}/{total}] Fetching contact info for {name}...", "info")
                
                try:
                    # scrape_contact_info returns (email, phone, conn_date, dob)
                    from automation import scrape_contact_info
                    email, phone, conn_date, dob = scrape_contact_info(page, username, account_id)
                except Exception as e:
                    acc_state.add_log(f"Failed to scrape {username}: {str(e)}", "error")
                    email, phone, conn_date, dob = "", "", None, None
                    
                email = email if email else ""
                phone = phone if phone else ""
                
                writer.writerow([username, name, company, email, phone, profile_url])
                f.flush() # Flush to disk so we don't lose data
                
                # Add to prospects database
                try:
                    prospects_db = load_db(account_id, "prospects")
                    exists = False
                    for c in prospects_db:
                        if c.get("profile_url", "").strip() == profile_url:
                            exists = True
                            updated = False
                            if conn_date:
                                c["date_accepted"] = conn_date
                                updated = True
                            if email and email != "Not Shared":
                                c["email"] = email
                                updated = True
                            if phone and phone != "Not Shared":
                                c["phone"] = phone
                                updated = True
                            if dob:
                                c["dob"] = dob
                                updated = True
                            if updated:
                                save_db(prospects_db, account_id, "prospects")
                            break
                    if not exists:
                        first_name = ""
                        last_name = ""
                        parts = name.split()
                        if parts:
                            first_name = parts[0]
                            if len(parts) > 1:
                                last_name = " ".join(parts[1:])
                        import datetime
                        new_contact = {
                            "name": name,
                            "first_name": first_name,
                            "last_name": last_name,
                            "profile_url": profile_url,
                            "company": company,
                            "title": "",
                            "status": "Extracted",
                            "date_sent": None,
                            "date_accepted": conn_date if conn_date else datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "email": email if email else "Not Shared",
                            "phone": phone if phone else "Not Shared",
                            "dob": dob if dob else None,
                            "logs": "Extracted via Connections Sync"
                        }
                        prospects_db.append(new_contact)
                        save_db(prospects_db, account_id, "prospects")
                except Exception as db_e:
                    acc_state.add_log(f"Failed to add to Prospects DB: {db_e}", "error")
                
                # Sleep to avoid getting banned
                time.sleep(random.uniform(3, 6))
                
        acc_state.add_log(f"Extraction complete! File saved to CSV and all contacts have been added to your Lead Database.", "success")

    except Exception as e:
        acc_state.add_log(f"Error during extraction: {e}", "error")
    finally:
        acc_state.stop_running()
        acc_state.update_status(action="Idle", progress=0)
        if context:
            try: context.close()
            except: pass
        if playwright:
            try: playwright.stop()
            except: pass

def start_temp_extraction(account_id):
    threading.Thread(target=extract_connections_worker, args=(account_id,), daemon=True).start()
