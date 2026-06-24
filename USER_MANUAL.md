# LKDConnect Dashboard: One-Page Operating Manual

Welcome to the LKDConnect Multi-Account Automator! This guide covers everything you need to know to operate the system on a daily basis.

---

## 1. Starting the System
1. **Open your terminal or command prompt** in the project folder (`c:\linkedineq\linkedinreqsender`).
2. **Start the server** by running the following command:
   ```bash
   python app.py
   ```
3. **Open your web browser** and go to [http://localhost:5000](http://localhost:5000).

---

## 2. The Admin Dashboard (Overview)
When you first open the dashboard, you are greeted with the **Admin Dashboard**.
- **Metrics Grid**: Shows total system-wide stats (Total Profiles, Requests Sent, Pending, Connected, etc.).
- **Filtering**: Use the top-right dropdowns to filter statistics by **Status** (e.g., Pending, Connected) or **Date** (e.g., Today, Yesterday). *Note: Filtering to "Today" will instantly update the metrics above to only show today's activity.*
- **Run Selected Sequentially**: You can select multiple accounts using the checkboxes in the table and click this button to run them one after another automatically.

---

## 3. Adding a New LinkedIn Account
1. Look at the **Left Sidebar** and click the `+ Add New Account` button at the bottom.
2. Enter a **Display Name** (e.g., "John Doe - Sales").
3. Click **Add Account**. The new account will now appear in your left sidebar list.

---

## 4. Operating an Individual Account
Click on any account in the **Left Sidebar** to open its specific workspace.

### A. Uploading Profiles (The Excel List)
1. In the account workspace, locate the **Upload Excel List** section.
2. Click **Browse** to select your `.xlsx` file containing LinkedIn Profile URLs.
3. Click **Upload & Process**. The profiles will be added to the database with a "Not Started" status.

### B. Starting the Automator
1. Make sure your browser is logged into the correct LinkedIn account (you can click **Open LinkedIn for Login** to verify).
2. Click the **Start Automator** button.
3. **Important Rules to Remember:**
   - The system will safely visit profiles, check their connection degree (1st, 2nd, 3rd), and send connection requests.
   - It respects daily limits and uses randomized human-like delays. **These safety settings are locked and should not be changed** to protect your accounts.
   - The status of profiles will automatically update from *Not Started* → *Pending* → *Connected*.

### C. Viewing Live Progress
- **Live Logs**: Watch the black terminal window on the dashboard to see exactly what the bot is doing in real-time.
- **Progress Bar**: The progress bar at the top of the account page shows how many profiles have been processed in the current run.
- **Account Stats**: The cards on the account page show the success rate and connection numbers specific to that single account.

---

## 5. Troubleshooting & Tips
- **Stuck Processes**: If the system seems unresponsive, close the terminal window where `python app.py` is running, open a new one, and start it again.
- **Empty Stats**: If your stats say "0", check if you have a date filter (like "Today") applied when no requests were sent today. Change it back to "All Time" to see everything.
- **Hidden Menu**: If you don't see the left sidebar, click the `Menu` button in the top header to toggle it.
