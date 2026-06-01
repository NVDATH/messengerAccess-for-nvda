# coding: utf-8
import wx
import subprocess
import threading
import json
import socket
import time
import globalPluginHandler
import os
import gui
import ui
import tones
from collections import deque
from http.server import BaseHTTPRequestHandler, HTTPServer
from gui import NVDASettingsDialog
from gui.settingsDialogs import SettingsPanel
from logHandler import log
from scriptHandler import script

CHAT_DATA     = {}
CHAT_TITLES   = []
CURRENT_CHAT  = [None]
CURRENT_INDEX = [0]
_SERVER_INSTANCE = None
_UNIFIED_PORT    = 48320
_last_sync_time  = 0.0

# config keys
_CONF_BEEP     = "messengerBeepEnabled"
_CONF_AUTOJUMP = "messengerAutoJump"


class _ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True

class _BridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Requested-With')
        self.end_headers()

    def do_GET(self):
        valid = ['/universal.user.js', '/chrome.user.js', '/firefox.user.js', '/edge.user.js']
        if self.path in valid:
            addon_dir = os.path.dirname(os.path.dirname(__file__))
            filepath = os.path.join(addon_dir, self.path.lstrip('/'))
            if os.path.exists(filepath):
                self.send_response(200)
                self.send_header('Content-Type', 'text/javascript; charset=utf-8')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
                return
        self.send_error(404, "Not Found")

    def do_POST(self):
        if self.path != '/push':
            self.send_error(404)
            return
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        try:
            data     = json.loads(post_data.decode('utf-8'))
            browser  = data.get('browser', 'unknown')
            title    = data.get('title', 'Unknown Chat')
            messages = data.get('messages', [])
            key      = f"{browser}::{title}"

            if key not in CHAT_DATA:
                CHAT_DATA[key] = deque(maxlen=100)
                CHAT_TITLES.append(key)

            old_messages = list(CHAT_DATA[key])
            if old_messages != messages:
                CHAT_DATA[key].clear()
                for msg in messages:
                    CHAT_DATA[key].append(msg)

            old_chat = CURRENT_CHAT[0]
            CURRENT_CHAT[0] = key

            if old_chat != key or old_messages != messages:
                if import_config().get(_CONF_AUTOJUMP, False):
                    CURRENT_INDEX[0] = max(0, len(CHAT_DATA[key]) - 1)
                if old_chat != key:
                    log.debug(f"[Messenger Bridge] Snapped to: '{key}'")
                else:
                    log.debug(f"[Messenger Bridge] New message in: '{key}'")

            global _last_sync_time
            _last_sync_time = time.time()

        except Exception as e:
            log.error(f"[Messenger Bridge] JSON parse failure: {e}")

        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

def _start_server():
    global _SERVER_INSTANCE
    if _SERVER_INSTANCE is not None:
        return
    try:
        _SERVER_INSTANCE = _ReusableHTTPServer(('127.0.0.1', _UNIFIED_PORT), _BridgeHandler)
        t = threading.Thread(target=_SERVER_INSTANCE.serve_forever)
        t.daemon = True
        t.start()
        log.info(f"[Messenger Bridge] Server started on port {_UNIFIED_PORT}")
        _start_watchdog()
    except Exception as e:
        log.error(f"[Messenger Bridge] Server failed to start: {e}")

def _stop_server():
    global _SERVER_INSTANCE
    if _SERVER_INSTANCE:
        _SERVER_INSTANCE.shutdown()
        _SERVER_INSTANCE = None

def _start_watchdog():
    def _watchdog():
        while True:
            time.sleep(30)
            if _SERVER_INSTANCE is None:
                break
            try:
                s = socket.create_connection(('127.0.0.1', _UNIFIED_PORT), timeout=2)
                s.close()
            except OSError:
                log.warning("[Messenger Bridge] Server unresponsive, restarting...")
                _stop_server()
                _start_server()
                break
    threading.Thread(target=_watchdog, daemon=True).start()

def import_config():
    """อ่าน config จาก NVDA config store — fallback เป็น default ถ้ายังไม่มีค่า"""
    try:
        import config
        return config.conf.get("messengerAccess", {})
    except Exception:
        return {}

def save_config(key, value):
    try:
        import config
        if "messengerAccess" not in config.conf:
            config.conf["messengerAccess"] = {}
        config.conf["messengerAccess"][key] = value
    except Exception as e:
        log.error(f"[Messenger Bridge] config save error: {e}")

# ── Settings Panel ────────────────────────────────────────────────────────────

_SCRIPT_URL = f"http://localhost:{_UNIFIED_PORT}/universal.user.js"
_TM_FIREFOX_URL = "https://addons.mozilla.org/firefox/addon/tampermonkey/"
_TM_CHROME_URL  = "https://chromewebstore.google.com/detail/tampermonkey/dhdgffkkebhmkfjojejmpbldmpobfkfo"

class MessengerAccessPanel(SettingsPanel):
    title = "Messenger Accessibility"

    def makeSettings(self, sizer):
        cfg = import_config()

        # UserScript section
        scriptBox = wx.StaticBoxSizer(wx.VERTICAL, self, "Install UserScript")
        desc = wx.StaticText(
            self, wx.ID_ANY,
            "Click \"Install UserScript\" to open the script in your default browser.\n"
            "If you want to install it in a different browser, use \"Copy Script URL\" "
            "and paste it into that browser's address bar manually."
        )
        desc.Wrap(440)
        scriptBox.Add(desc, 0, wx.ALL, 6)
        btnRow = wx.BoxSizer(wx.HORIZONTAL)
        self.btnScript = wx.Button(self, wx.ID_ANY, "Install UserScript")
        self.btnCopy   = wx.Button(self, wx.ID_ANY, "Copy Script URL")
        btnRow.Add(self.btnScript, 0, wx.RIGHT, 8)
        btnRow.Add(self.btnCopy, 0)
        scriptBox.Add(btnRow, 0, wx.ALL, 6)
        sizer.Add(scriptBox, 0, wx.ALL | wx.EXPAND, 8)

        self.btnScript.Bind(wx.EVT_BUTTON, self.onInstallScript)
        self.btnCopy.Bind(wx.EVT_BUTTON, self.onCopyLink)

        # Behavior section
        behaviorBox = wx.StaticBoxSizer(wx.VERTICAL, self, "Behavior")
        self.chkBeep = wx.CheckBox(
            self, wx.ID_ANY,
            "Play beep sound at the end of message list"
        )
        self.chkBeep.SetValue(cfg.get(_CONF_BEEP, False))
        behaviorBox.Add(self.chkBeep, 0, wx.ALL, 6)

        self.chkAutoJump = wx.CheckBox(
            self, wx.ID_ANY,
            "Always move to latest message when new message arrives"
        )
        self.chkAutoJump.SetValue(cfg.get(_CONF_AUTOJUMP, False))
        behaviorBox.Add(self.chkAutoJump, 0, wx.ALL, 6)

        sizer.Add(behaviorBox, 0, wx.ALL | wx.EXPAND, 8)

    def onInstallScript(self, event):
        try:
            subprocess.Popen(f'start "" "{_SCRIPT_URL}"', shell=True)
        except Exception:
            pass

    def onCopyLink(self, event):
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(_SCRIPT_URL))
            wx.TheClipboard.Close()

    def onSave(self):
        save_config(_CONF_BEEP,     self.chkBeep.GetValue())
        save_config(_CONF_AUTOJUMP, self.chkAutoJump.GetValue())

    def onDiscard(self): pass

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    scriptCategory = "messengerAccess"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        NVDASettingsDialog.categoryClasses.append(MessengerAccessPanel)
        _start_server()

        addon_dir = os.path.dirname(os.path.dirname(__file__))
        flag_path = os.path.join(addon_dir, "show_wizard.flag")
        
        if os.path.exists(flag_path):
            try:
                os.remove(flag_path)
            except Exception:
                pass
            wx.CallLater(2000, gui.mainFrame.popupSettingsDialog,
                gui.settingsDialogs.NVDASettingsDialog,
                MessengerAccessPanel)

    def terminate(self):
        _stop_server()
        try:
            NVDASettingsDialog.categoryClasses.remove(MessengerAccessPanel)
        except Exception:
            pass
        super().terminate()

    @script(
        description=_("read previous message"),
        category="messengerAccess")
    def script_prevMessage(self, gesture):
        if _last_sync_time > 0 and (time.time() - _last_sync_time) > 60:
            ui.message("Messenger not connected. Please check if your browser is open.")
            return
        key = CURRENT_CHAT[0]
        if not key or key not in CHAT_DATA or len(CHAT_DATA[key]) == 0:
            ui.message("No chat messages")
            return
        if CURRENT_INDEX[0] > 0:
            CURRENT_INDEX[0] -= 1
            ui.message(CHAT_DATA[key][CURRENT_INDEX[0]])
        else:
            if import_config().get(_CONF_BEEP, False):
                tones.beep(360, 70)
            ui.message(CHAT_DATA[key][CURRENT_INDEX[0]])

    @script(
        description=_("read next message"),
        category="messengerAccess")
    def script_nextMessage(self, gesture):
        if _last_sync_time > 0 and (time.time() - _last_sync_time) > 60:
            ui.message("Messenger not connected. Please check if your browser is open.")
            return
        key = CURRENT_CHAT[0]
        if not key or key not in CHAT_DATA or len(CHAT_DATA[key]) == 0:
            ui.message("No chat messages")
            return
        if CURRENT_INDEX[0] < len(CHAT_DATA[key]) - 1:
            CURRENT_INDEX[0] += 1
            ui.message(CHAT_DATA[key][CURRENT_INDEX[0]])
        else:
            if import_config().get(_CONF_BEEP, False):
                tones.beep(720, 70)
            ui.message(CHAT_DATA[key][CURRENT_INDEX[0]])

    @script(  
        # Translators: Message to be announced during Keyboard Help  
        description=_("move to read previous convasation"),
        # Translators: Name of the section in "Input gestures" dialog.  
        category="messengerAccess")
    def script_prevChat(self, gesture):
        if not CHAT_TITLES:
            ui.message("No active chats")
            return
        try:
            idx = CHAT_TITLES.index(CURRENT_CHAT[0])
            idx = (idx - 1) % len(CHAT_TITLES)
        except ValueError:
            idx = 0
        CURRENT_CHAT[0] = CHAT_TITLES[idx]
        CURRENT_INDEX[0] = max(0, len(CHAT_DATA[CURRENT_CHAT[0]]) - 1)
        display = CURRENT_CHAT[0].split('::', 1)[-1]
        ui.message(f"active chat: {display}")

    @script(  
        # Translators: Message to be announced during Keyboard Help  
        description=_("move to read next conversation"),
        # Translators: Name of the section in "Input gestures" dialog.  
        category="messengerAccess")
    def script_nextChat(self, gesture):
        if not CHAT_TITLES:
            ui.message("No active chats")
            return
        try:
            idx = CHAT_TITLES.index(CURRENT_CHAT[0])
            idx = (idx + 1) % len(CHAT_TITLES)
        except ValueError:
            idx = 0
        CURRENT_CHAT[0] = CHAT_TITLES[idx]
        CURRENT_INDEX[0] = max(0, len(CHAT_DATA[CURRENT_CHAT[0]]) - 1)
        display = CURRENT_CHAT[0].split('::', 1)[-1]
        ui.message(f"active chat: {display}")

    __gestures = {
        "kb:control+[":       "prevMessage",
        "kb:control+]":       "nextMessage",
        "kb:control+shift+[": "prevChat",
        "kb:control+shift+]": "nextChat",
    }
