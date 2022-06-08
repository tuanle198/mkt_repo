import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
import datetime
from datetime import date
from apiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
import base64

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

def int_converter(column):
    df[column] = df[column].astype('int')

body = {'reportRequests': [{'viewId': '266420819',
                            'dateRanges': [{'startDate': '2022-05-01', 'endDate': 'today'}],
                            'metrics': [{'expression': 'ga:pageviews'},
                                        {'expression': 'ga:users'},
                                        {'expression': 'ga:newUsers'},
                                        {'expression': 'ga:sessions'},
                                        {'expression': 'ga:bounceRate'},
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

df.to_csv('ga-data.csv')