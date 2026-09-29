from pathlib import Path
from io import StringIO
import json
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

ROOT = Path(__file__).parent
try:
    SHEET_ID = st.secrets["sheet_id"]
except (KeyError, FileNotFoundError):
    st.info('Add sheet_id in Streamlit app settings → Secrets to connect your Google Sheet.')
    st.stop()
TAB_ID = st.secrets.get("tab_id", "1156235585")
SHEET = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid={TAB_ID}'
CSV = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&gid={TAB_ID}'
CATEGORIES = ['tell', 'show', 'chat', 'push', 'remind', 'missed deadline']
CURRENT, FINAL = 'Current Overall Score', 'Final Overall Score'
st.set_page_config(page_title='Performance tracker', page_icon='◈', layout='wide')
st.markdown('''<style>
.stApp{background:#f5f7fb;color:#172337}
.block-container{padding-top:2.5rem;max-width:1450px}
[data-testid="stMetric"]{background:white;border:1px solid #e3e8ef;border-radius:16px;padding:20px}
[data-testid="stMetricLabel"]{color:#607088}
h1,h2,h3{letter-spacing:-.035em}
div[data-testid="stSidebar"]{background:#eaf0f5}
</style>''', unsafe_allow_html=True)

def clean(frame):
    frame.columns = [str(c).strip() for c in frame.columns]
    required = ['Task', *CATEGORIES, CURRENT, FINAL]
    missing = [c for c in required if c not in frame.columns]
    if missing:
        raise ValueError('Missing columns: ' + ', '.join(missing))
    frame = frame.loc[frame['Task'].notna()].copy()
    frame['Task'] = frame['Task'].astype(str).str.strip()
    frame = frame.loc[frame['Task'] != '']
    for col in CATEGORIES + [CURRENT, FINAL]:
        original = frame[col]
        frame[col] = pd.to_numeric(original, errors='coerce')
        invalid = original.notna() & original.astype(str).str.strip().ne('') & frame[col].isna()
        if invalid.any():
            raise ValueError(f'Non-numeric values in {col}; please check the Sheet.')
    frame['Deductions'] = frame[CATEGORIES].fillna(0).sum(axis=1)
    frame['Expected score'] = 100 - frame['Deductions']
    if 'Prize' not in frame:
        frame['Prize'] = ''
    frame['Prize'] = frame['Prize'].fillna('').astype(str)
    return frame

@st.cache_data(ttl=60, show_spinner=False)
def live_data():
    response = requests.get(CSV, timeout=15)
    response.raise_for_status()
    if '<html' in response.text[:500].lower() or '<!doctype' in response.text[:500].lower():
        raise ValueError('Google returned a sign-in page instead of sheet data.')
    return clean(pd.read_csv(StringIO(response.text))), pd.Timestamp.now(tz='Europe/London')

def snapshot():
    data = json.loads((ROOT / 'data.json').read_text())
    rows = data['values']
    return clean(pd.DataFrame([r + [None] * (len(rows[0])-len(r)) for r in rows[1:]], columns=rows[0])), pd.Timestamp(data['retrieved_at']).tz_convert('Europe/London')

with st.sidebar:
    st.markdown('### ◈ Performance tracker')
    st.caption('TASKS & SUPPORT')
    mode = 'Google Sheet'
    if st.button('Refresh data', use_container_width=True):
        live_data.clear()
    st.link_button('Open perf track ↗', SHEET, use_container_width=True)
    st.divider()
    st.caption('Read-only dashboard. Make changes in your Sheet, then refresh here.')

live = False
if mode == 'Google Sheet':
    try:
        df, updated = live_data()
        live = True
    except Exception:
        st.error('Could not read Google Sheets. Check the connection and sharing settings, then click Refresh data.')
        st.stop()
else:
    df, updated = snapshot()

st.caption('PERSONAL DASHBOARD / PERFORMANCE')
st.title('Every task, a clearer picture.')
st.write('See task scores and where points are deducted, using your existing scoring rules.')
st.caption(f'{"● Connected to Google Sheets" if live else "Saved snapshot"} · Read {updated.strftime("%d %b %Y · %H:%M %Z")} · perf track')

with st.sidebar:
    search = st.text_input('Find a task', placeholder='Search task names…')
    order = st.selectbox('Task order', ['Sheet order', 'Lowest score first', 'Highest score first'])
    chosen = st.multiselect('Focus on tasks', df['Task'].tolist())
filtered = df.copy()
if search:
    filtered = filtered[filtered.Task.str.contains(search, case=False, regex=False)]
if chosen:
    filtered = filtered[filtered.Task.isin(chosen)]
if order != 'Sheet order':
    filtered = filtered.sort_values(CURRENT, ascending=order == 'Lowest score first')
if filtered.empty:
    st.info('No matching tasks. Clear the filters to see your tasks again.')
    st.stop()

cols = st.columns(4)
cols[0].metric('Tasks shown', len(filtered))
avg = filtered[CURRENT].mean()
cols[1].metric('Average current score', '—' if pd.isna(avg) else f'{avg:.1f} / 100')
cols[2].metric('Total deductions', f'{filtered.Deductions.sum():g}')
cols[3].metric('Missed-deadline deductions', f'{filtered["missed deadline"].fillna(0).sum():g}')
st.caption('Deductions are the numbers entered in your Sheet, not verified counts of events. No completion status or dates are recorded.')

overview, detail, table = st.tabs(['Overview', 'Task detail', 'Source data & scoring'])
with overview:
    left, right = st.columns([1.5, 1])
    with left:
        st.subheader('Current score by task')
        fig = px.bar(filtered, x=CURRENT, y='Task', orientation='h', text=CURRENT,
                     color_discrete_sequence=['#157f87'])
        fig.update_layout(yaxis={'autorange':'reversed','title':None}, xaxis_title='Points',
                          height=430, margin=dict(l=0,r=25,t=10,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        fig.update_xaxes(range=[min(0, filtered[CURRENT].min()-5), max(100, filtered[CURRENT].max()+5)])
        fig.update_traces(textposition='outside', cliponaxis=False)
        st.plotly_chart(fig, use_container_width=True)
    with right:
        st.subheader('Where points are deducted')
        totals = filtered[CATEGORIES].fillna(0).sum().sort_values(ascending=False).rename_axis('Category').reset_index(name='Points')
        fig = px.bar(totals, x='Points', y='Category', orientation='h', text='Points', color_discrete_sequence=['#7182bc'])
        fig.update_layout(yaxis={'autorange':'reversed','title':None}, height=430,
                          margin=dict(l=0,r=25,t=10,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)
    st.subheader('Task breakdown')
    melted = filtered.melt(id_vars='Task', value_vars=CATEGORIES, var_name='Category', value_name='Points')
    fig = px.bar(melted, x='Task', y='Points', color='Category', color_discrete_sequence=['#157f87','#67b4ae','#7182bc','#bca2ce','#d7b36a','#dd8675'])
    fig.update_layout(height=380, xaxis_title=None, yaxis_title='Deduction points', legend_title=None, margin=dict(t=15,b=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)

with detail:
    idx = st.selectbox('Choose a task', list(filtered.index), format_func=lambda i: filtered.loc[i, 'Task'])
    row = filtered.loc[idx]
    st.subheader(row['Task'])
    a,b,c = st.columns(3)
    a.metric('Current score', '—' if pd.isna(row[CURRENT]) else f'{row[CURRENT]:g} / 100')
    b.metric('Final score in Sheet', '—' if pd.isna(row[FINAL]) else f'{row[FINAL]:g} / 100')
    c.metric('Total deductions', f'{row.Deductions:g}')
    st.caption('“Final” currently mirrors the current score; it does not indicate the task is complete.')
    st.dataframe(pd.DataFrame({'Category':CATEGORIES,'Deduction points':[row[c] for c in CATEGORIES]}), hide_index=True, use_container_width=True)
    st.write('**Prize:** ' + (row.Prize if row.Prize else 'Not recorded'))

with table:
    st.subheader('The scoring in your Sheet')
    st.code('Current score = 100 − (tell + show + chat + push + remind + missed deadline)\nFinal score = Current score', language=None)
    st.write('Initial start is excluded from the deduction formula. Blank deduction cells contribute zero, matching SUM in Google Sheets. Scores displayed above are the values returned by your Sheet.')
    mismatch = filtered[filtered[CURRENT].notna() & ((filtered[CURRENT]-filtered['Expected score']).abs() > .001)]
    if not mismatch.empty:
        st.warning('Some recorded scores differ from the formula above. Check those rows in Google Sheets.')
    st.dataframe(filtered[['Task', *CATEGORIES, CURRENT, FINAL, 'Prize']], hide_index=True, use_container_width=True)
    st.download_button('Download displayed rows (CSV)', filtered[['Task', *CATEGORIES, CURRENT, FINAL, 'Prize']].to_csv(index=False), 'performance.csv', 'text/csv')
    st.caption('Google data is cached for up to 60 seconds. Use Refresh data after editing the Sheet. No changes are written back.')
