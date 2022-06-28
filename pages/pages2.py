import streamlit as st

# Showing and downloading raw data
st.markdown("### Raw data from GA analytics")
number = st.number_input(label='Number of rows to be shown',
                         min_value=5,
                         max_value=len(df)
                         )
raw = df.sort_values('Date', ascending=False)
st.dataframe(raw.head(number))

csv = df.to_csv()
st.download_button("Download raw data", data=csv,
                   mime="text/csv", key='download-csv')
