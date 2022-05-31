import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
import datetime
from datetime import date
from apiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
import base64
import io

st.set_page_config(
    page_title="Real-Time DISCOS App Listing Dashboard",
    page_icon="✅",
    layout="wide",
)
# We will use API to read from google analytics in this step
SCOPES = ['https://www.googleapis.com/auth/analytics.readonly']
KEY_FILE_LOCATION = 'ga-key.json'
VIEW_ID = '266420819'


def format_summary(response):
    try:
        # create row index
        try:
            row_index_names = response['reports'][0]['columnHeader']['dimensions']
            row_index = [element['dimensions']
                         for element in response['reports'][0]['data']['rows']]
            row_index_named = pd.MultiIndex.from_arrays(np.transpose(np.array(row_index)),
                                                        names=np.array(row_index_names))
        except:
            row_index_named = None

        # extract column names
        summary_column_names = [item['name'] for item in response['reports'][0]
                                ['columnHeader']['metricHeader']['metricHeaderEntries']]

        # extract table values
        summary_values = [element['metrics'][0]['values']
                          for element in response['reports'][0]['data']['rows']]

        # combine. I used type 'float' because default is object, and as far as I know, all values are numeric
        df = pd.DataFrame(data=np.array(summary_values),
                          index=row_index_named,
                          columns=summary_column_names).astype('float')

    except:
        df = pd.DataFrame()

    return df


def format_pivot(response):
    try:
        # extract table values
        pivot_values = [item['metrics'][0]['pivotValueRegions'][0]['values'] for item in response['reports'][0]
                        ['data']['rows']]

        # create column index
        top_header = [item['dimensionValues'] for item in response['reports'][0]
                      ['columnHeader']['metricHeader']['pivotHeaders'][0]['pivotHeaderEntries']]
        column_metrics = [item['metric']['name'] for item in response['reports'][0]
                          ['columnHeader']['metricHeader']['pivotHeaders'][0]['pivotHeaderEntries']]
        array = np.concatenate((np.array(top_header),
                                np.array(column_metrics).reshape((len(column_metrics), 1))),
                               axis=1)
        column_index = pd.MultiIndex.from_arrays(np.transpose(array))

        # create row index
        try:
            row_index_names = response['reports'][0]['columnHeader']['dimensions']
            row_index = [element['dimensions']
                         for element in response['reports'][0]['data']['rows']]
            row_index_named = pd.MultiIndex.from_arrays(np.transpose(np.array(row_index)),
                                                        names=np.array(row_index_names))
        except:
            row_index_named = None
        # combine into a dataframe
        df = pd.DataFrame(data=np.array(pivot_values),
                          index=row_index_named,
                          columns=column_index).astype('float')
    except:
        df = pd.DataFrame()
    return df


def format_report(response):
    summary = format_summary(response)
    pivot = format_pivot(response)
    if pivot.columns.nlevels == 2:
        summary.columns = [['']*len(summary.columns), summary.columns]

    return(pd.concat([summary, pivot], axis=1))


def run_report(body, credentials_file):
    # Create service credentials
    credentials = ServiceAccountCredentials.from_json_keyfile_name(credentials_file,
                                                                   scopes=['https://www.googleapis.com/auth/analytics.readonly'])
    # Create a service object
    service = build('analyticsreporting', 'v4', credentials=credentials)

    # Get GA data
    response = service.reports().batchGet(body=body).execute()
    return(format_report(response).reset_index())


body = {'reportRequests': [{'viewId': '266420819',
                            'dateRanges': [{'startDate': '2022-05-01', 'endDate': 'today'}],
                            'metrics': [{'expression': 'ga:users'},
                                        {'expression': 'ga:newUsers'},
                                        {'expression': 'ga:sessions'},
                                        {'expression': 'ga:bounceRate'},
                                        {'expression': 'ga:pageviewsPerSession'},
                                        {'expression': 'ga:avgSessionDuration'},
                                        {'expression':'ga:totalEvents'}],
                            'dimensions': [{'name': 'ga:landingPagePath'},
                                           {'name': 'ga:date'},
                                           {'name':'ga:source'},
                                           {'name':'ga:country'},
                                           {'name':'ga:deviceCategory'}]}]}

# Generate df and clean
# @st.experimental_memo
# def get_data() -> pd.DataFrame:
#     return run_report(body, KEY_FILE_LOCATION)

df = run_report(body, KEY_FILE_LOCATION)

# df = run_report(body, KEY_FILE_LOCATION)
df.columns = ['Landing Page', 'Date', 'Source','Country','Device', 'Users', 'New Users',
              'Sessions', 'Bounce Rate', 'Pages/Session', 'Avg. Session Duration','Total Events']
df['Users'] = df['Users'].astype('int')
df['New Users'] = df['New Users'].astype('int')
df['Sessions'] = df['Sessions'].astype('int')
# Total Events convert to integer
df['Total Events'] = df['Total Events'].astype('int')
# Avg. Session Duration convert to timedelta
df['Avg. Session Duration'] = pd.to_timedelta(df['Avg. Session Duration'])
df['Avg. Session Duration'] = df['Avg. Session Duration'].dt.total_seconds()

# Date converter
df['Date'] = df['Date'].astype('str')
df['Date'] = df['Date'].apply(lambda x: x[:4] + '-' + x[4:6] + '-' + x[-2:])
df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m-%d')

# Extract type of surface
df['type'] = df['Landing Page'].apply(lambda x: x.split(
    'surface_type')[1].split('=')[1] if 'surface_type' in x else 'Others')

# Extract keyword
df['keyword'] = df['Landing Page'].apply(lambda x: x.split('surface_detail=')[1].split(
    '&')[0] if 'surface_detail' and 'surface_type=search' in x else 'Others')
df['keyword'] = df['keyword'].apply(lambda x: x.replace('+', ' '))


# Setup dashboard layout
st.title("Real-Time DISCOS App Listing Dashboard")

job_filter = st.selectbox("Select users source", pd.unique(df["type"]))
temp_df = df[df["type"] == job_filter]

# create three columns to store all source
all_kpi1, all_kpi2, all_kpi3 = st.columns(3)

# fill in those three columns with respective metrics or KPIs
mask = df['Date'] < df['Date'].max()

all_kpi1.metric(
    label="All users",
    value=sum(df['Users']),
    delta=sum(df['Users']) - sum(df[mask]['Users'])
)

all_kpi2.metric(
    label="All new users",
    value=sum(df['New Users']),
    delta=sum(df['New Users']) - sum(df[mask]['New Users'])
)

all_kpi3.metric(
    label="All sessions",
    value=sum(df['Sessions']),
    delta=sum(df['Sessions']) - sum(df[mask]['Sessions'])
)

# create three columns to store filtered source
kpi1, kpi2, kpi3 = st.columns(3)

# fill in those three columns with respective metrics or KPIs
mask = temp_df['Date'] < temp_df['Date'].max()

kpi1.metric(
    label="Users by source",
    value=sum(temp_df['Users']),
    delta=sum(temp_df['Users']) - sum(temp_df[mask]['Users'])
)

kpi2.metric(
    label="New users by source",
    value=sum(temp_df['New Users']),
    delta=sum(temp_df['New Users']) - sum(temp_df[mask]['New Users'])
)

kpi3.metric(
    label="Sessions by source",
    value=sum(temp_df['Sessions']),
    delta=sum(temp_df['Sessions']) - sum(temp_df[mask]['Sessions'])
)


# create two columns for charts

# Create dataframe for fig_col1
main = ['upsell cross sell', 'bogo', 'cart upsell']
desc = ['increase sales',
        'promotional campaign',
        'buy one get one',
        'buy x get y',
        'in cart upsell',
        'one click upsell',
        'upsell']
# keyword_group = df[df['keyword'] != 'Others'].groupby('keyword')['Users'].sum().to_frame().reset_index()
keyword_group = df[df['keyword'] != 'Others'].groupby('keyword').agg(
    {'Users': 'sum', 'Pages/Session': 'mean', 'Avg. Session Duration': 'mean'}).reset_index()
keyword_group['Target Priority'] = 'None'
keyword_group.loc[keyword_group['keyword'].apply(
    lambda x: x in desc), 'Target Priority'] = 'Include in desc.'
keyword_group.loc[keyword_group['keyword'].apply(
    lambda x: x in main), 'Target Priority'] = 'Main'
top_keyword_group = keyword_group.sort_values(
    'Users', ascending=False).head(10)

# Create dataframe for fig_col2
today = date.today()
seven_days_ago = today - datetime.timedelta(days=7)
mask = (df['Date'].dt.date <= today) & (df['Date'].dt.date >= seven_days_ago)
filtered = df[mask]
agg_filtered = filtered.groupby('Date')['Users'].sum().to_frame().reset_index()
agg_filtered['Date'] = agg_filtered['Date'].apply(lambda x: x.date())

fig_col1, fig_col2 = st.columns(2)

with fig_col1:
    st.markdown("### Traffic by keywords (all time, top 10 keywords)")
    fig = px.bar(top_keyword_group, x="Users",
                 y="keyword", color='Target Priority')
    st.write(fig)

with fig_col2:
    st.markdown("### Average page per session (all time, top 10 keywords)")
    fig = px.bar(top_keyword_group, y="Pages/Session",
                 x="keyword", color='Target Priority')
    st.write(fig)

fig_col3, fig_col4 = st.columns(2)

with fig_col3:
    st.markdown(
        "### Average session duration in seconds (all time, top 10 keywords)")
    fig2 = px.bar(data_frame=top_keyword_group, x="keyword",
                  y="Avg. Session Duration", color='Target Priority')
    st.write(fig2)

with fig_col4:
    st.markdown("### All traffics last 7 days")
    fig2 = px.line(data_frame=agg_filtered, x="Date", y="Users")
    st.write(fig2)


# Showing and downloading raw data
st.markdown("### Raw data from GA analytics")
number = st.number_input(label='Number of rows to be shown',
                         min_value=5,
                         max_value=len(df)
                         )
raw = df.sort_values('Date', ascending=False)
st.dataframe(raw.head(number))

s_buf = io.StringIO()
df.to_csv(s_buf)
st.download_button(label = 'Download Data', data = s_buf)