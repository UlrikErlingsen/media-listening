"""Weekly brand pulse export: XLSX workbook + one-page HTML summary."""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from listensignal import build_pulse, pulse_html, pulse_xlsx
from pages._ui import data_banner, empty_state, header, view

header(
    "Export",
    "Weekly brand pulse",
    "A one-page HTML summary to share and an XLSX workbook with every table behind it. Both state the period, "
    "the data source, the sentiment scorer and the spike rule.",
)
v = view()
data_banner(v)
if empty_state(v):
    st.stop()

all_dates = sorted(set(v.ws.mentions["date"]))
end = st.date_input("Week ending", value=v.end, min_value=all_dates[0], max_value=all_dates[-1])
report = build_pulse(v.ws, end)
stem = f"listensignal-pulse-{report.window.this_end:%Y-%m-%d}{'-demo' if v.ws.is_demo else ''}"
html = pulse_html(report)
c1, c2 = st.columns(2)
c1.download_button("Download one-page HTML", html.encode("utf-8"), f"{stem}.html", "text/html", type="primary",
                   width="stretch")
c2.download_button("Download XLSX workbook", pulse_xlsx(report), f"{stem}.xlsx",
                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
st.caption("Workbook sheets: About · What changed · Week vs week · Share of voice · Sentiment mix · Spikes · "
           "Daily counts · Top sources · Rising terms · Mentions. Cells are protected against formula injection.")
st.markdown("#### Preview")
components.html(html, height=1050, scrolling=True)
st.caption("Command line: `python -m listensignal.pulse` (add `--demo` for the fictional demo).")
