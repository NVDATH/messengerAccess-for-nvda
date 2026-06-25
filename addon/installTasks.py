import os
import subprocess
import threading
import gui
import wx

_TM_FIREFOX_URL = "https://addons.mozilla.org/firefox/addon/tampermonkey/"
_TM_CHROME_URL  = "https://chromewebstore.google.com/detail/tampermonkey/dhdgffkkebhmkfjojejmpbldmpobfkfo"
_SCRIPT_URL     = "http://localhost:48320/universal.user.js"


class _GetExtensionDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Messenger Accessibility — Get Tampermonkey")
        sizer = wx.BoxSizer(wx.VERTICAL)

        desc = wx.StaticText(
            self, wx.ID_ANY,
            "You'll need Tampermonkey (or a compatible userscript manager) "
            "installed in your browser before the UserScript can be added.\n\n"
            "Choose your browser below:"
        )
        desc.Wrap(420)
        sizer.Add(desc, 0, wx.ALL, 12)

        btnSizer = wx.BoxSizer(wx.VERTICAL)

        self.btnFirefox = wx.Button(self, wx.ID_ANY, "Open Tampermonkey for Firefox")
        btnSizer.Add(self.btnFirefox, 0, wx.EXPAND | wx.BOTTOM, 6)

        # Chrome/Edge/อื่นๆ ใช้ store เดียวกัน — copy URL แล้วเปิดในบราวเซอร์เป้าหมายเอง
        self.btnChromeOther = wx.Button(self, wx.ID_ANY, "Copy Tampermonkey URL for Chrome / Edge / Other")
        chromeDesc = wx.StaticText(
            self, wx.ID_ANY,
            "(Copy this URL, then paste and open it in your target browser)"
        )
        chromeDesc.SetForegroundColour(wx.Colour(120, 120, 120))
        btnSizer.Add(self.btnChromeOther, 0, wx.EXPAND | wx.BOTTOM, 2)
        btnSizer.Add(chromeDesc, 0, wx.LEFT | wx.BOTTOM, 4)

        self.btnHaveIt = wx.Button(self, wx.ID_ANY, "I already have it — Continue")
        btnSizer.Add(self.btnHaveIt, 0, wx.EXPAND | wx.TOP, 6)

        sizer.Add(btnSizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        self.SetSizerAndFit(sizer)
        self.CentreOnScreen()

        self.btnFirefox.Bind(wx.EVT_BUTTON,    self._on_firefox)
        self.btnChromeOther.Bind(wx.EVT_BUTTON, self._on_chrome_copy)
        self.btnHaveIt.Bind(wx.EVT_BUTTON,      lambda e: self.EndModal(wx.ID_OK))
        self.Bind(wx.EVT_CLOSE, lambda e: self.EndModal(wx.ID_CANCEL))
        self.btnFirefox.SetFocus()

    def _on_firefox(self, event):
        try:
            subprocess.Popen(f'start firefox "{_TM_FIREFOX_URL}"', shell=True)
        except Exception:
            pass

    def _on_chrome_copy(self, event):
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(_TM_CHROME_URL))
            wx.TheClipboard.Close()
        wx.MessageBox(
            "Tampermonkey URL copied!\n\n"
            "Paste it into the address bar of your browser (Chrome, Edge, or other) to open the extension store.",
            "URL Copied",
            wx.OK | wx.ICON_INFORMATION
        )


def _run_on_main(fn):
    done = threading.Event()
    result = [None]
    def _wrapper():
        result[0] = fn()
        done.set()
    wx.CallAfter(_wrapper)
    done.wait()
    return result[0]


def _get_addon_folder_name():
    # Add-on folder name matches the addon name in manifest (e.g. "messengerAccess")
    # installTasks.py lives at: <addons_dir>/<addonName>.pendingInstall/installTasks.py
    # The existing installed copy (if any) is at: <addons_dir>/<addonName>/
    this_dir   = os.path.dirname(os.path.abspath(__file__))   # ...pendingInstall/
    addons_dir = os.path.dirname(this_dir)                     # addons/
    addon_name = os.path.basename(this_dir).replace(".pendingInstall", "")
    existing   = os.path.join(addons_dir, addon_name)
    return existing


def _is_upgrade():
    return os.path.isdir(_get_addon_folder_name())


def onInstall() -> None:
    if _is_upgrade():
        _run_on_main(_show_upgrade_dialog)
        return

    # Fresh install flow
    has_tm = _run_on_main(lambda: gui.messageBox(
        "Do you already have Tampermonkey (or a compatible userscript manager) "
        "installed in your browser?",
        "Messenger Accessibility — Setup",
        wx.YES_NO | wx.ICON_QUESTION
    ))

    if has_tm == wx.NO:
        def _show_ext_dlg():
            dlg = _GetExtensionDialog(gui.mainFrame)
            dlg.ShowModal()
            dlg.Destroy()
        _run_on_main(_show_ext_dlg)

    response = _run_on_main(lambda: gui.messageBox(
        "After NVDA restarts, open NVDA Settings → Messenger Accessibility\n"
        "to install the UserScript for your browser.\n\n"
        "Would you like the setup panel to open automatically after restart?",
        "Messenger Accessibility — Setup",
        wx.YES_NO | wx.ICON_INFORMATION
    ))
    if response == wx.YES:
        _write_wizard_flag()


def _show_upgrade_dialog():
    dlg = _UpdateScriptDialog(gui.mainFrame)
    dlg.ShowModal()
    dlg.Destroy()


def _write_wizard_flag():
    try:
        addon_dir = os.path.dirname(__file__)
        flag_path = os.path.join(addon_dir, "show_wizard.flag")
        with open(flag_path, "w") as f:
            f.write("1")
    except Exception:
        pass


class _UpdateScriptDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Messenger Access — UserScript Update Required")
        sizer = wx.BoxSizer(wx.VERTICAL)

        desc = wx.StaticText(
            self, wx.ID_ANY,
            "Messenger Access has been updated.\n\n"
            "The UserScript in your browser also needs to be updated to work correctly.\n\n"
            "Click \"Copy Script URL\" below, then paste it into your browser's address bar.\n"
            "Tampermonkey will prompt you to update the script."
        )
        desc.Wrap(440)
        sizer.Add(desc, 0, wx.ALL, 12)

        self.btnCopy  = wx.Button(self, wx.ID_ANY, "Copy Script URL")
        self.btnClose = wx.Button(self, wx.ID_CANCEL, "Close")

        btnSizer = wx.BoxSizer(wx.HORIZONTAL)
        btnSizer.Add(self.btnCopy,  0, wx.RIGHT, 8)
        btnSizer.Add(self.btnClose, 0)
        sizer.Add(btnSizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        self.SetSizerAndFit(sizer)
        self.CentreOnScreen()

        self.btnCopy.Bind(wx.EVT_BUTTON, self._on_copy)
        self.btnClose.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL))
        self.Bind(wx.EVT_CLOSE, lambda e: self.EndModal(wx.ID_CANCEL))
        self.btnCopy.SetFocus()

    def _on_copy(self, event):
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(_SCRIPT_URL))
            wx.TheClipboard.Close()
        wx.MessageBox(
            "Script URL copied!\n\n"
            "Paste it into your browser's address bar.\n"
            "Tampermonkey will show an update prompt — click Install to update.",
            "URL Copied",
            wx.OK | wx.ICON_INFORMATION
        )
