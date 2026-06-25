// ==UserScript==
// @name         Messenger Bridge for NVDA (Universal)
// @namespace    http://tampermonkey.net/
// @version      3.7.2
// @author        Claud.ai, Gemini
// @description  Universal Messenger Bridge — works with Chrome, Edge, Firefox. Single port 48320. Renders a clean accessible English mirror on the page.
// @updateURL   http://localhost:48320/universal.user.js
// @downloadURL http://localhost:48320/universal.user.js
// @match        https://www.messenger.com/*
// @match        https://www.facebook.com/messages/*
// @grant        GM_xmlhttpRequest
// @run-at       document-end
// ==/UserScript==

(function() {
    'use strict';

    function detectBrowser() {
        const ua = navigator.userAgent;
        if (ua.includes('Edg/'))     return 'edge';
        if (ua.includes('Firefox/')) return 'firefox';
        if (ua.includes('Chrome/'))  return 'chrome';
        return 'unknown';
    }

    const BROWSER = detectBrowser();
    const PORT    = 48320;

    let isUpdating = false;
    let isFetching = false;
    let lastSuccessfulFingerprint = "";
    let lastSyncTime = 0;
    let isNavigating = false;
    let lastCommandId = "";

    function getChatId() {
        // Pattern: /t/<chat_id> or /messages/t/<chat_id>
        const match = location.pathname.match(/\/t\/([^/?#]+)/);
        return match ? match[1] : null;
    }

    function navigateToChat(chatId) {
        if (isNavigating) return;
        const target = `https://www.messenger.com/t/${chatId}`;
        if (location.href === target) return;
        isNavigating = true;
        // Messenger is a SPA — location.href may not trigger full reload.
        // Use location.assign to force a real navigation, then reset the guard
        // via a fallback timeout in case the page does NOT fully reload (rare).
        location.assign(target);
        // If SPA intercepts the navigation and doesn't reload, reset guard after 4s
        // so polling can resume normally.
        setTimeout(() => { isNavigating = false; }, 4000);
    }

    function pollCommand() {
        if (isNavigating) return;
        GM_xmlhttpRequest({
            method:  "GET",
            url:     `http://127.0.0.1:${PORT}/command`,
            timeout: 3000,
            onload: function(response) {
                if (response.status === 200) {
                    try {
                        const data = JSON.parse(response.responseText);
                        // Only act if it's a new command we haven't processed yet
                        if (data.command === "navigate" && data.chat_id && data.id !== lastCommandId) {
                            lastCommandId = data.id;
                            navigateToChat(data.chat_id);
                        } else if (data.command === "open_update" && data.id !== lastCommandId) {
                            lastCommandId = data.id;
                            window.open(`http://127.0.0.1:${PORT}/universal.user.js`, '_blank');
                        }
                    } catch (e) {}
                }
            },
            onerror:   function() {},
            ontimeout: function() {}
        });
    }

    function pushToNVDA(chatTitle, messagesArray, currentFingerprint) {
        if (isFetching) return;
        isFetching = true;

        const payload = {
            browser:  BROWSER,
            version:  "3.7.2",
            title:    chatTitle,
            chat_id:  getChatId(),
            messages: messagesArray
        };

        GM_xmlhttpRequest({
            method:  "POST",
            url:     `http://127.0.0.1:${PORT}/push`,
            headers: { "Content-Type": "application/json" },
            data:    JSON.stringify(payload),
            timeout: 2000,
            onload: function(response) {
                if (response.status >= 200 && response.status < 300) {
                    lastSuccessfulFingerprint = currentFingerprint;
                    lastSyncTime = Date.now();
                } else {
                    lastSuccessfulFingerprint = "";
                }
                isFetching = false;
            },
            onerror: function() {
                lastSuccessfulFingerprint = "";
                isFetching = false;
            },
            ontimeout: function() {
                lastSuccessfulFingerprint = "";
                isFetching = false;
            }
        });
    }

    function processChatMirror() {
        if (isUpdating || isNavigating) return;
        isUpdating = true;

        // ── ลอจิก Tab Mutex: ป้องกันการแย่งพอร์ตในกรณีเปิดหลายแท็บพร้อมกัน ──
        if (document.hidden) {
            const lastActiveTime = parseInt(localStorage.getItem('nvda_bridge_active_time') || '0', 10);
            if (Date.now() - lastActiveTime < 4000) { 
                isUpdating = false; 
                return; 
            }
        } else {
            localStorage.setItem('nvda_bridge_active_time', Date.now().toString());
        }

        // ── 1. ค้นหา Chat Title ──
        const allHeadings = Array.from(document.querySelectorAll('h2, h3'));
        let chatTitle = "Unknown Chat";

        let convHeading = allHeadings.find(h => h.textContent.includes('Conversation with'));
        if (convHeading) {
            chatTitle = convHeading.textContent.replace(/Conversation with/i, '').trim();
        } else {
            const systemLabels = ["Chats", "Messages", "Active now", "Communities",
                                  "Marketplace", "Requests", "Archive", "Preferences", "More"];
            const groupTitleHeading = allHeadings.find(h => {
                const text = h.textContent.trim();
                return text.length > 0 && !systemLabels.includes(text) && h.id !== 'mirror-heading' && !text.includes('You replied');
            });
            if (groupTitleHeading) chatTitle = groupTitleHeading.textContent.trim();
        }

        // ── 2. ค้นหาขอบเขตข้อความหลัก (Messages -> Compose) ──
        const h3Elements = Array.from(document.querySelectorAll('h3'));
        let messagesHeading = null;
        let composeHeading = null;

        for (let i = 0; i < h3Elements.length; i++) {
            if (h3Elements[i].textContent.trim() === 'Messages') {
                for (let j = i + 1; j < h3Elements.length; j++) {
                    if (h3Elements[j].textContent.trim() === 'Compose') {
                        messagesHeading = h3Elements[i];
                        composeHeading = h3Elements[j];
                        break;
                    }
                }
            }
            if (messagesHeading && composeHeading) break;
        }

        if (!messagesHeading || !composeHeading) {
            isUpdating = false;
            return;
        }

        const potentialItems = document.querySelectorAll('button, div[role="button"], div[role="row"]');
        const cleanedMessages = [];

        potentialItems.forEach(item => {
            const isAfterMessages = messagesHeading.compareDocumentPosition(item) & Node.DOCUMENT_POSITION_FOLLOWING;
            const isBeforeCompose = item.compareDocumentPosition(composeHeading) & Node.DOCUMENT_POSITION_FOLLOWING;

            if (isAfterMessages && isBeforeCompose) {
                let ariaLabel = (item.getAttribute('aria-label') || '').trim();
                let rawText = (item.innerText || item.textContent || '').replace(/\s+/g, ' ').trim();

                if (ariaLabel.startsWith("Enter, ")) {
                    ariaLabel = ariaLabel.substring(7).trim();
                }

                const textToProcess = ariaLabel || rawText;

                // [FIXED] เติม flag 's' (dotAll) เพื่อรองรับข้อความยาวที่มีการขึ้นบรรทัดใหม่ (\n)
                const msgRegex = /Message sent\s+(.+?)\s+by\s+([^:]+)(?:\:\s*(.+))?$/is;
                const match = textToProcess.match(msgRegex);

                if (match) {
                    const time   = match[1].trim();
                    const author = match[2].trim();
                    let msg      = match[3] ? match[3].trim() : "[Attachment]"; 
                    
                    if (msg.toLowerCase().endsWith(' button')) {
                        msg = msg.substring(0, msg.length - 7).trim();
                    }
                    const formatted = `${author}: ${msg} sent at ${time}`;
                    if (!cleanedMessages.includes(formatted)) {
                        cleanedMessages.push(formatted);
                    }
                }
                // ตรวจจับการตอบกลับ (Reply Context)
                else if (ariaLabel === "Go to replied message" || rawText.includes("Original message:")) {
                    let original = rawText.replace("Original message:", "").trim();
                    const replyText = `[Reply to: "${original}"]`;
                    if (original && !cleanedMessages.includes(replyText)) {
                        cleanedMessages.push(replyText);
                    }
                }
                // ตรวจจับปุ่มรีแอคชั่น (Reaction Counter)
                else if (ariaLabel.includes("reaction with")) {
                    const reactMatch = ariaLabel.match(/(.+ reaction with [^;]+)/i);
                    if (reactMatch) {
                        const reactText = `[Reaction: ${reactMatch[1]}]`;
                        if (!cleanedMessages.includes(reactText)) {
                            cleanedMessages.push(reactText);
                        }
                    }
                }
                // ตรวจจับไฟล์แนบย้อนหลัง
                else if (ariaLabel.includes("Open GIF") || ariaLabel.includes("Play Video") || ariaLabel.includes("Expand video")) {
                    let type = ariaLabel.includes("GIF") ? "GIF" : "Video";
                    for (let k = cleanedMessages.length - 1; k >= 0; k--) {
                        if (cleanedMessages[k].includes("[Attachment]")) {
                            cleanedMessages[k] = cleanedMessages[k].replace("[Attachment]", `[${type}]`);
                            break; 
                        }
                    }
                }
            }
        });

        const currentFingerprint = JSON.stringify({ title: chatTitle, msgs: cleanedMessages });
        const timeSinceLastSync  = Date.now() - lastSyncTime;

        if (currentFingerprint === lastSuccessfulFingerprint && timeSinceLastSync < 10000) {
            isUpdating = false;
            return;
        }

        // ── 3. อัปเดต Mirror บนหน้าเว็บ ──
        let mirrorContainer = document.getElementById('nvda-clean-messages-mirror');
        if (!mirrorContainer) {
            mirrorContainer = document.createElement('div');
            mirrorContainer.id = 'nvda-clean-messages-mirror';
            mirrorContainer.setAttribute('role', 'region');
            mirrorContainer.setAttribute('aria-label', 'Messenger Bridge — Clean Message View');
            mirrorContainer.style.cssText = [
                'position: fixed',
                'bottom: 0',
                'right: 0',
                'width: 340px',
                'max-height: 220px',
                'overflow-y: auto',
                'background: rgba(0,0,0,0.82)',
                'color: #fff',
                'font-size: 13px',
                'font-family: sans-serif',
                'padding: 8px 12px',
                'z-index: 99999',
                'border-top-left-radius: 8px',
                'box-sizing: border-box',
                'white-space: pre-wrap' // [ADDED] ช่วยให้หน้าจอดีบั๊กแสดงผลการขึ้นบรรทัดใหม่ได้อย่างถูกต้อง
            ].join(';');
            document.body.appendChild(mirrorContainer);
        }

        if (cleanedMessages.length > 0) {
            let html = `<h2><strong id="mirror-heading" style="display:block;margin-bottom:6px;font-size:12px;opacity:.7">`
                     + `Chat: ${chatTitle}</strong></h2><ul style="margin:0;padding:0;list-style:none" aria-labelledby="mirror-heading">`;
            cleanedMessages.forEach(msg => {
                html += `<li style="border-bottom:1px solid rgba(255,255,255,.1);padding:4px 0">${msg}</li>`;
            });
            html += '</ul>';
            mirrorContainer.innerHTML = html;

            pushToNVDA(chatTitle, cleanedMessages, currentFingerprint);
        } else {
            mirrorContainer.innerHTML = '';
        }

        isUpdating = false;
    }

    // ── MutationObserver ──
    const observer = new MutationObserver((mutations) => {
        for (let mutation of mutations) {
            const mirror = document.getElementById('nvda-clean-messages-mirror');
            if (mirror && mirror.contains(mutation.target)) continue;
            processChatMirror();
            break;
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });

    setInterval(processChatMirror, 3000);
    setInterval(pollCommand, 2000);
    processChatMirror();

})();