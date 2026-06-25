# -*- coding: UTF-8 -*-
# buildVars.py - variables used by SCons when building the addon.

def _(x):
    return x

# Add-on information variables
addon_info = {
    "addon_name": "messengerAccess",
    "addon_version": "2026.6.25",
# Translators: Summary for this add-on
    "addon_summary": _("messengerAccess"),
    # Translators: Long description to be shown for this add-on on add-on information from add-ons manager
    "addon_description": _("""If you find reading chat messages in Facebook Messenger too difficult, this add-on might be able to help you.

Warning: User usage requires knowledge of userScript installation. 

For this add-on, we will use userScript installed on the browser to edit the display of chat messages and forward it to the add-on. You can use shortcut keys to read the message.
Users can focus in the text field and press the control+[/] keyboard shortcut to keep the conversation flowing. No need to move focus around often.
    """)
    "addon_author": "NVDATH <nvdainth@gmail.com> assis by A.I.",
    "addon_url": "https://github.com/NVDATH/messengerAccess-for-nvda",
    "addon_docFileName": "readme.html",
    "addon_minimumNVDAVersion": "2025.1",
    "addon_lastTestedNVDAVersion": "2026.1",
    "addon_updateChannel": "stable",
}

pythonSources = [
    "addon/globalPlugins",
]

i18nSources = [
    "buildVars.py",
    "addon/globalPlugins/MessengerAccess.py",
]

docFiles = ["readme.html"]

tests = []
excludedFiles = []
baseLanguage = "en"
markdownExtensions = []