# -*- coding: UTF-8 -*-
# buildVars.py - variables used by SCons when building the addon.

def _(x):
    return x

# Add-on information variables
addon_info = {
    "addon_name": "messengerAccess",
    "addon_version": "2026.6.1",
# Translators: Summary for this add-on
    "addon_summary": _("messengerAccess"),
    # Translators: Long description to be shown for this add-on on add-on information from add-ons manager
    "addon_description": _("""Provides accessibility features for Messenger chat onFirefox and Chrome and Microsoft Edge."""),
    "addon_author": "NVDA_TH <nvdainth@gmail.com>, assisted by A.I.",
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