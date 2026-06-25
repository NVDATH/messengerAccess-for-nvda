# coding: utf-8
import wx
import subprocess
import threading
import json
import socket
import time
import uuid
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
CHAT_IDS      = {}   # key -> chat_id
CURRENT_CHAT  = [None]
CURRENT_INDEX = [0]
_SERVER_INSTANCE  = None
_UNIFIED_PORT     = 48320
_last_sync_time   = 0.0
_pending_command  = [None]   # {"id": str, "command": "navigate", "chat_id": str} | None

# config keys
_CONF_BEEP       = "messengerBeepEnabled"
_CONF_AUTOJUMP   = "messengerAutoJump"
_CONF_NAVSWITCH  = "messengerNavSwitch"

# version check — อ่านจาก .js จริงเพื่อไม่ต้อง hardcode
def _read_script_version():
    try:
        js_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'universal.user.js')
        with open(js_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('// @version'):
                    return line.split('// @version', 1)[1].strip()
    except Exception as e:
        log.error(f"[Messenger Bridge] Could not read script version: {e}")
    return None

_REQUIRED_SCRIPT_VERSION = _read_script_version()
_script_version_warned   = [False]
_detected_script_version = [None]


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
                self.send_header('Content-Type', 'application/x-userscript; charset=utf-8')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
                return

        if self.path == '/command':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            cmd = _pending_command[0]
            if cmd:
                self.wfile.write(json.dumps(cmd).encode('utf-8'))
                _pending_command[0] = None   # consume-once: clear after serving
            else:
                self.wfile.write(b'{}')
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
            chat_id  = data.get('chat_id')
            messages = data.get('messages', [])
            script_version = data.get('version', None)
            log.debug(f"[Messenger Bridge] version received: {script_version!r}, required: {_REQUIRED_SCRIPT_VERSION!r}")
            key      = f"{browser}::{title}"

            # version check — แจ้งเตือนและสั่ง open update ครั้งเดียวต่อ session
            if script_version:
                _detected_script_version[0] = script_version
                if (not _script_version_warned[0]
                        and script_version != _REQUIRED_SCRIPT_VERSION):
                    _script_version_warned[0] = True
                    _pending_command[0] = {
                        "id":      str(uuid.uuid4()),
                        "command": "open_update"
                    }
                    wx.CallAfter(
                        ui.message,
                        f"UserScript is outdated. Opening update page in your browser."
                    )

            if key not in CHAT_DATA:
                CHAT_DATA[key] = deque(maxlen=100)
                CHAT_TITLES.append(key)

            if chat_id:
                CHAT_IDS[key] = chat_id

            old_messages = list(CHAT_DATA[key])
            if old_messages != messages:
                CHAT_DATA[key].clear()
                for msg in messages:
                    CHAT_DATA[key].append(msg)

            old_chat = CURRENT_CHAT[0]
            CURRENT_CHAT[0] = key

            if old_chat != key or old_messages != messages:
                if import_config().get(_CONF_AUTOJUMP, False):
                    CURRENT_INDEX[0] = min(
                        max(0, len(CHAT_DATA[key]) - 1),
                        len(CHAT_DATA[key]) - 1 if CHAT_DATA[key] else 0
                    )
                if old_chat != key:
                    CURRENT_INDEX[0] = max(0, len(CHAT_DATA[key]) - 1)
                    log.debug(f"[Messenger Bridge] Snapped to: '{key}'")
                else:
                    if import_config().get(_CONF_AUTOJUMP, False):
                        CURRENT_INDEX[0] = max(0, len(CHAT_DATA[key]) - 1)
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
    try:
        import config
        raw = config.conf.get("messengerAccess", {})
        result = {}
        for k, v in raw.items():
            if isinstance(v, str):
                result[k] = v.lower() == "true"
            else:
                result[k] = v
        return result
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
    title = "Messenger Access"

    def makeSettings(self, sizer):
        cfg = import_config()

        # ── 1. Behavior (ใช้บ่อย — ขึ้นก่อน) ──────────────────────────────
        behaviorBox = wx.StaticBoxSizer(wx.VERTICAL, self, "Behavior")

        self.chkBeep = wx.CheckBox(self, wx.ID_ANY,
            "Play beep sound at end of message list")
        self.chkBeep.SetValue(cfg.get(_CONF_BEEP, False))
        behaviorBox.Add(self.chkBeep, 0, wx.ALL, 6)

        self.chkAutoJump = wx.CheckBox(self, wx.ID_ANY,
            "Auto-jump to latest message when new message arrives")
        self.chkAutoJump.SetValue(cfg.get(_CONF_AUTOJUMP, False))
        behaviorBox.Add(self.chkAutoJump, 0, wx.ALL, 6)

        self.chkNavSwitch = wx.CheckBox(self, wx.ID_ANY,
            "Auto-switch chat: navigate browser when changing chats")
        self.chkNavSwitch.SetValue(cfg.get(_CONF_NAVSWITCH, False))
        behaviorBox.Add(self.chkNavSwitch, 0, wx.ALL, 6)

        sizer.Add(behaviorBox, 0, wx.ALL | wx.EXPAND, 8)

        # ── 2. UserScript — status + update ────────────────────────────────
        scriptBox = wx.StaticBoxSizer(wx.VERTICAL, self, "UserScript")

        detected  = _detected_script_version[0]
        if detected is None:
            status_text = "Status: not detected (open Messenger in your browser)"
        elif detected == _REQUIRED_SCRIPT_VERSION:
            status_text = f"Status: up to date (version {detected})"
        else:
            status_text = (f"Status: update available "
                           f"(installed {detected}, required {_REQUIRED_SCRIPT_VERSION})")

        self.lblStatus = wx.StaticText(self, wx.ID_ANY, status_text)
        scriptBox.Add(self.lblStatus, 0, wx.ALL, 6)

        updateRow = wx.BoxSizer(wx.HORIZONTAL)
        self.btnCheck = wx.Button(self, wx.ID_ANY, "Check for Update")
        self.btnCopy  = wx.Button(self, wx.ID_ANY, "Copy Script URL")
        updateRow.Add(self.btnCheck, 0, wx.RIGHT, 8)
        updateRow.Add(self.btnCopy, 0)
        scriptBox.Add(updateRow, 0, wx.ALL, 6)

        sizer.Add(scriptBox, 0, wx.ALL | wx.EXPAND, 8)

        self.btnCheck.Bind(wx.EVT_BUTTON, self.onCheckUpdate)
        self.btnCopy.Bind(wx.EVT_BUTTON,  self.onCopyLink)

        # ── 3. Advanced — ใช้ตอน setup ครั้งแรกเท่านั้น ───────────────────
        advBox = wx.StaticBoxSizer(wx.VERTICAL, self, "Advanced")

        advDesc = wx.StaticText(self, wx.ID_ANY,
            "Use \"Install UserScript\" only during initial setup.\n"
            "This opens the script URL in your default browser for Tampermonkey to install.")
        advDesc.Wrap(440)
        advBox.Add(advDesc, 0, wx.ALL, 6)

        self.btnScript = wx.Button(self, wx.ID_ANY, "Install UserScript")
        advBox.Add(self.btnScript, 0, wx.ALL, 6)

        sizer.Add(advBox, 0, wx.ALL | wx.EXPAND, 8)

        self.btnScript.Bind(wx.EVT_BUTTON, self.onInstallScript)

    def onCheckUpdate(self, event):
        detected = _detected_script_version[0]
        if detected is None:
            wx.MessageBox(
                "UserScript version not detected.\n"
                "Make sure Messenger is open in your browser and the script is running.",
                "Check for Update",
                wx.OK | wx.ICON_INFORMATION
            )
            return
        if detected == _REQUIRED_SCRIPT_VERSION:
            wx.MessageBox(
                f"UserScript is up to date (version {detected}).",
                "Check for Update",
                wx.OK | wx.ICON_INFORMATION
            )
        else:
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(wx.TextDataObject(_SCRIPT_URL))
                wx.TheClipboard.Close()
            wx.MessageBox(
                f"Update available: installed {detected}, required {_REQUIRED_SCRIPT_VERSION}.\n\n"
                "The update URL has been copied to your clipboard.\n"
                "Paste it into your browser's address bar to update the script via Tampermonkey.",
                "Update Available",
                wx.OK | wx.ICON_WARNING
            )
            # reset warned flag so user gets notified again next session if still outdated
            _script_version_warned[0] = False

    def onInstallScript(self, event):
        try:
            subprocess.Popen(f'start "" "{_SCRIPT_URL}"', shell=True)
        except Exception:
            pass

    def onCopyLink(self, event):
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(_SCRIPT_URL))
            wx.TheClipboard.Close()
        wx.MessageBox(
            "Script URL copied to clipboard.\n"
            "Paste it into your browser's address bar to install or update via Tampermonkey.",
            "URL Copied",
            wx.OK | wx.ICON_INFORMATION
        )

    def onSave(self):
        save_config(_CONF_BEEP,      self.chkBeep.GetValue())
        save_config(_CONF_AUTOJUMP,  self.chkAutoJump.GetValue())
        save_config(_CONF_NAVSWITCH, self.chkNavSwitch.GetValue())

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
        CURRENT_INDEX[0] = min(CURRENT_INDEX[0], len(CHAT_DATA[key]) - 1)
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
        CURRENT_INDEX[0] = min(CURRENT_INDEX[0], len(CHAT_DATA[key]) - 1)
        if CURRENT_INDEX[0] < len(CHAT_DATA[key]) - 1:
            CURRENT_INDEX[0] += 1
            ui.message(CHAT_DATA[key][CURRENT_INDEX[0]])
        else:
            if import_config().get(_CONF_BEEP, False):
                tones.beep(720, 70)
            ui.message(CHAT_DATA[key][CURRENT_INDEX[0]])

    def _switch_chat(self, idx):
        CURRENT_CHAT[0] = CHAT_TITLES[idx]
        CURRENT_INDEX[0] = max(0, len(CHAT_DATA[CURRENT_CHAT[0]]) - 1)
        display = CURRENT_CHAT[0].split('::', 1)[-1]
        ui.message(f"active chat: {display}")
        if import_config().get(_CONF_NAVSWITCH, False):
            chat_id = CHAT_IDS.get(CURRENT_CHAT[0])
            if chat_id:
                _pending_command[0] = {
                    "id":      str(uuid.uuid4()),
                    "command": "navigate",
                    "chat_id": chat_id
                }

    @script(
        description=_("move to read previous convasation"),
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
        self._switch_chat(idx)

    @script(
        description=_("move to read next conversation"),
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
        self._switch_chat(idx)

    __gestures = {
        "kb:control+[":       "prevMessage",
        "kb:control+]":       "nextMessage",
        "kb:control+shift+[": "prevChat",
        "kb:control+shift+]": "nextChat",
    }
