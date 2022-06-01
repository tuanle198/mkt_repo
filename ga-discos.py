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
# Setup dashboard layout
st.title("Real-Time DISCOS App Listing Dashboard")
# Date filter
st.markdown("## Choose start date and end date")

date_col_start, date_col_end = st.columns(2)
with date_col_start: 
 sd = st.date_input(
    "Start date",
    datetime.date(2022, 5, 5),
    min_value = datetime.date(2022, 5, 5))
with date_col_end:
    ed = st.date_input(
    "End date",
    date.today(),
    min_value = sd)


# df = run_report(body, KEY_FILE_LOCATION)
df.columns = ['Landing Page', 'Date', 'Source','Country','Device', 'Users', 'New Users',
              'Sessions', 'Bounce Rate', 'Pages/Session', 'Avg. Session Duration','Total Events']
df['Users'] = df['Users'].astype('int')
df['New Users'] = df['New Users'].astype('int')
df['Sessions'] = df['Sessions'].astype('int')
# Total Events convert to integer
df['Total Events'] = df['Total Events'].astype('int')
# Avg. Session Duration convert to timedelta
# df['Avg. Session Duration'] = pd.to_timedelta(df['Avg. Session Duration'])
# df['Avg. Session Duration'] = df['Avg. Session Duration'].dt.total_seconds()

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

# Filter by date df
mask = (df['Date'] >= pd.Timestamp(sd)) & (df['Date'] <= pd.Timestamp(ed))
df = df[mask]

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
# kpi1, kpi2, kpi3 = st.columns(3)

# fill in those three columns with respective metrics or KPIs
# mask = temp_df['Date'] < temp_df['Date'].max()

# kpi1.metric(
#     label="Users by source",
#     value=sum(temp_df['Users']),
#     delta=sum(temp_df['Users']) - sum(temp_df[mask]['Users'])
# )

# kpi2.metric(
#     label="New users by source",
#     value=sum(temp_df['New Users']),
#     delta=sum(temp_df['New Users']) - sum(temp_df[mask]['New Users'])
# )

# kpi3.metric(
#     label="Sessions by source",
#     value=sum(temp_df['Sessions']),
#     delta=sum(temp_df['Sessions']) - sum(temp_df[mask]['Sessions'])
# )


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
# Create dataframe for fig_col2 and fig_col3 and fig_col6
keyword_group = df[df['keyword'] != 'Others'].groupby('keyword').agg(
    {'Users': 'sum', 
    'Pages/Session': 'mean',
    'Avg. Session Duration': 'mean',
     'Total Events':'sum'}).reset_index()
keyword_group['Target Priority'] = 'None'
keyword_group.loc[keyword_group['keyword'].apply(
    lambda x: x in desc), 'Target Priority'] = 'Include in desc.'
keyword_group.loc[keyword_group['keyword'].apply(
    lambda x: x in main), 'Target Priority'] = 'Main'
top_keyword_group = keyword_group.sort_values(
    'Users', ascending=False).head(10)

# Create dataframe for fig_col1
agg_filtered = df.groupby('Date')['Users'].sum().to_frame().reset_index()
agg_filtered['Date'] = agg_filtered['Date'].apply(lambda x: x.date())

# Create dataframe for fig_col4
countries = df.groupby('Country')['Users'].sum().reset_index().sort_values('Users', ascending = False).reset_index()
countries.loc[countries['Users'] < countries['Users'][4],'Country'] = 'Others'
countries = countries.groupby('Country')['Users'].sum().sort_values(ascending = False).reset_index()

# Create dataframe for fig_col5
devices = df.groupby('Device')['Users'].sum().sort_values(ascending = False).reset_index()

fig_col1, fig_col2 = st.columns(2)
with fig_col1:
    st.markdown("### Traffic by days")
    fig1 = px.line(data_frame=agg_filtered, x="Date", y="Users")
    st.write(fig1)
with fig_col2:
    st.markdown("### Top 10 keywords by traffic")
    fig2 = px.bar(data_frame=top_keyword_group, x="keyword",
                  y="Users", color='Target Priority')
    st.write(fig2)

fig_col3,fig_col4 = st.columns(2)
with fig_col3:
    st.markdown(
        "### Average session duration of top 10 highest traffic keywords")
    fig3 = px.bar(data_frame=top_keyword_group, x="keyword",
                  y="Avg. Session Duration", color='Target Priority',
                                   labels=
                                   {
                     "Avg. Session Duration": "Avg. Session Duration (seconds)"
                                   }
                  )
    st.write(fig3)
with fig_col4:
    st.markdown("### Top 5 countries with highest traffic")
    fig4 = px.pie(data_frame=countries, names="Country", values = 'Users')
    st.write(fig4)

fig_col5,fig_col6 = st.columns(2)
with fig_col5:
    st.markdown("### User distribution by device")
    fig5 = px.pie(data_frame=devices, names="Device", values = 'Users')
    st.write(fig5)
with fig_col6:
    st.markdown("### Click add app by keyword")
    fig6 = px.bar(data_frame=top_keyword_group, x="keyword",
                  y="Total Events", color='Target Priority')
    st.write(fig6)
# Showing and downloading raw data
st.markdown("### Raw data from GA analytics")
number = st.number_input(label='Number of rows to be shown',
                         min_value=5,
                         max_value=len(df)
                         )
raw = df.sort_values('Date', ascending=False)
st.dataframe(raw.head(number))

csv = df.to_csv()
st.download_button("Download raw data", data=csv, mime = "text/csv", key='download-csv')