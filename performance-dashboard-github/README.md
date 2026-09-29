# Performance dashboard

Deploy on Streamlit Community Cloud with main file `app.py` and Python 3.12.

In Advanced settings → Secrets, add `sheet_id` and `tab_id` as quoted TOML strings. Use your Google Sheet ID and the perf track tab ID. No sheet data or personal snapshot is included in this repository.

The sheet must allow the running app to read its CSV endpoint. This app uses the existing link-access method, not a Google service account. If access fails, it displays a connection error.

For personal performance data, use a private repository and confirm Streamlit Sharing is set to Only specific people can view this app. Edit the Google Sheet, then click Refresh data to update the dashboard.
