# Messenger Accessibility for NVDA

Makes Facebook Messenger easily readable with NVDA. 

Because Facebook's standard website can be difficult for screen readers to navigate, this tool uses a "bridge" system. It consists of two parts working together: an NVDA Add-on and a Browser Script (UserScript). 

## Requirements

* NVDA 2023.1 or later
* A Chromium-based browser (Google Chrome, Microsoft Edge, Brave) or Mozilla Firefox
* Tampermonkey browser extension

---

## Installation Guide

### Step 1: Install the NVDA Add-on
1. Download and open the `.nvda-addon` file to begin the installation.
2. During the setup, a dialog will ask: "Do you already have Tampermonkey (or a compatible userscript manager) installed in your browser?".
    * If you choose **No**, a new window will appear. You can click **"Open Tampermonkey for Firefox"** to open the download page directly, or click **"Copy Tampermonkey URL for Chrome / Edge / Other"** to copy the link and paste it into your target browser's address bar.
    * If you choose **Yes**, it will skip this step.
3. Next, it will ask: "Would you like the setup panel to open automatically after restart?". It is highly recommended to choose **Yes**.
4. Finish the installation and let NVDA restart.

### Step 2: Enable Browser Permissions (For Chrome / Edge / Chromium)
If you installed Tampermonkey in a Chromium-based browser, you need to configure a few settings before proceeding:
1. Go to your browser's extension manager page (e.g., `chrome://extensions` or `edge://extensions`).
2. Turn on **Developer mode** (usually a toggle in the top right corner).
3. Find Tampermonkey, click "Details" or "Manage", and ensure all permission switches (like site access) are turned ON so the script is allowed to run.

### Step 3: Install the Bridge Script
1. If you chose "Yes" during setup, the **Messenger Accessibility** settings panel will open automatically after NVDA restarts. *(If it didn't open, you can find it in the NVDA menu → Preferences → Settings → Messenger Accessibility).*
2. Click the **"Install UserScript"** button to open the script code in your browser. 
3. Finally, click the **"Install"** button on the Tampermonkey page.

### Step 4: First-Time Setup & Verification
1. Open or switch to your Messenger tab and **refresh the page by pressing F5**.
2. Tampermonkey may show a prompt asking for permission to access the local script. You must click **"Always allow"**.

To verify the script is working properly, navigate to the bottom of the Messenger web page. You will find a new Heading Level 2 (`h2`) displaying the active chat title. Directly below this heading, you will see a simplified, easy-to-read list of your chat messages.

---

## Usage & Gestures

The add-on reads new messages in the background automatically. You can use the following gestures from anywhere in the browser, in both browse mode and focus mode, without needing to leave the compose box.

* `Ctrl + [` : Read previous message
* `Ctrl + ]` : Read next message
* `Ctrl + Shift + [` : Switch to the previous active conversation
* `Ctrl + Shift + ]` : Switch to the next active conversation

If NVDA says "Messenger not connected", ensure your browser is open and the page is fully loaded. The connection restores automatically within a few seconds.

---

## Standalone Userscript Mode (Optional)

You do not strictly need to use the NVDA shortcut keys to benefit from this tool. The userscript automatically cleans up the complex web page and provides the simplified reading interface at the bottom of the screen. 

If you are satisfied with only using the new reading layout and prefer navigating the page manually, you can completely uninstall the NVDA add-on. The Tampermonkey userscript will continue to function on its own. However, please note that standalone userscripts will not receive automatic updates.

---

## Settings

You can customize how the add-on behaves by going to NVDA Settings, then Messenger Accessibility.

* **Play beep at end of message list:** Plays a tone when you reach the first or last message. Off by default.
* **Always move to latest message when new message arrives:** Automatically jumps your reading position to the newest message. Off by default.

---

## Supported Content & Updates

The userscript displays a clean overlay on the page and sends messages to NVDA. Supported message types include standard text messages, reply context (shown as original message), inline reactions, and media attachments (shown as labels like Video or GIF).

**Updates:** Script updates are bundled directly with the NVDA add-on. When you update the add-on through the NVDA Add-on Store, your local userscript file will be automatically updated as well.

---

## Known Limitations

* Works only with the web version of Messenger (messenger.com and facebook.com/messages). Does not support the Messenger desktop app.
* Message history is limited to the 100 most recent messages per conversation.
* If Facebook updates its page structure, the userscript may temporarily stop working until a new add-on version is released.