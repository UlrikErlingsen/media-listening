"""Listen Signal user interface: the Signal Hub entry point.

The only package under ``listensignal`` that imports Streamlit. ``render()`` draws the whole app on the current page
and never calls ``st.set_page_config`` or ``st.navigation``; the standalone ``app.py`` or Signal Hub owns those.
With ``SIGNAL_HUB=1`` the app shows the bundled fictional demo only: no files, no database, no network.
"""

from listensignal import __version__
from listensignal.ui import signal_theme
from listensignal.ui.app import render

APP_INFO = {"product": "Listen Signal", "version": __version__, "repo": "media-listening", "slug": "listen"}

__all__ = ["APP_INFO", "render", "signal_theme"]
