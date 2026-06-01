import os
import subprocess
import threading
import gui
import wx

_TM_FIREFOX_URL = "https://addons.mozilla.org/firefox/addon/tampermonkey/"
_TM_CHROME_URL  = "https://chromewebstore.google.com/detail/tampermonkey/dhdgffkkebhmkfjojejmpbldmpobfkfo"


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


def onInstall() -> None:
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


def _write_wizard_flag():
    try:
        addon_dir = os.path.dirname(__file__)
        flag_path = os.path.join(addon_dir, "show_wizard.flag")
        with open(flag_path, "w") as f:
            f.write("1")
    except Exception:
        pass
