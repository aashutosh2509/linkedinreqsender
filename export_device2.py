import os
import shutil
import re

def export_device2_zip():
    print("====================================================")
    print(" CREATING DEVICE 2 WORKER ZIP FILE (NO GIT REQUIRED)")
    print("====================================================")
    
    source_dir = os.path.dirname(os.path.abspath(__file__))
    desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
    target_dir = os.path.join(desktop_dir, "Device2_Bot")
    
    print(f"[INFO] Exporting to: {target_dir}")
    
    # 1. Clean existing target if it exists
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
        
    # 2. Copy the entire directory
    def ignore_patterns(d, files):
        # Ignore heavy browser cache, git files, and databases
        return [f for f in files if f in ['.git', '__pycache__', 'node_modules', 'venv', 'pw-browsers', 'linkedin_user_data', 'accounts_db', 'uploads', 'Default']]
        
    shutil.copytree(source_dir, target_dir, ignore=ignore_patterns)
    
    # 3. Strip out the Leads CRM
    public_dir = os.path.join(target_dir, "public")
    for f in ["leads.html", "leads.js"]:
        f_path = os.path.join(public_dir, f)
        if os.path.exists(f_path): os.remove(f_path)
    
    # 4. Hide all Outbound Features in index.html
    index_html_path = os.path.join(public_dir, "index.html")
    if os.path.exists(index_html_path):
        with open(index_html_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        content = re.sub(r'<button class="account-item" id="btn-open-leads-crm".*?</button>', '', content, flags=re.DOTALL)
        content = content.replace('id="excel-upload-card"', 'id="excel-upload-card" style="display:none !important;"')
        content = content.replace('id="quick-add-card"', 'id="quick-add-card" style="display:none !important;"')
        content = content.replace('id="scheduler-card"', 'id="scheduler-card" style="display:none !important;"')
        content = content.replace('id="template-card"', 'id="template-card" style="display:none !important;"')
        content = content.replace('id="btn-start"', 'id="btn-start" style="display:none !important;"')
        content = content.replace('id="btn-start-messaging"', 'id="btn-start-messaging" style="display:none !important;"')
        content = content.replace('class="selective-send-container margin-bottom-12"', 'class="selective-send-container margin-bottom-12" style="display:none !important;"')
        
        with open(index_html_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
    # 5. Create a ZIP file for easy transfer
    zip_path = os.path.join(desktop_dir, "Device2_Bot")
    shutil.make_archive(zip_path, 'zip', target_dir)
    
    # Clean up the unzipped folder to keep Desktop clean
    shutil.rmtree(target_dir)
    
    print("====================================================")
    print(" SUCCESS! DEVICE 2 BOT HAS BEEN ZIPPED! ")
    print("====================================================")
    print(f"File located at: {zip_path}.zip")
    print("You can now email this ZIP to yourself, or upload it to Google Drive!")
    print("====================================================")

if __name__ == "__main__":
    export_device2_zip()
