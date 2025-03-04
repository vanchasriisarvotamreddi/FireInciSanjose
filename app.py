import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import folium
from streamlit_folium import folium_static
import os
import googlemaps
from google.cloud import bigquery
from google.oauth2 import service_account

# -----------------------------------------------------------------------------
# ✅ Load BigQuery Credentials from Streamlit Secrets
# -----------------------------------------------------------------------------
try:
    # Make sure your secrets.toml has [gcp_service_account] ...
    service_account_info = st.secrets["gcp_service_account"]
    credentials = service_account.Credentials.from_service_account_info(service_account_info)
    client = bigquery.Client(
        credentials=credentials,
        project=service_account_info["project_id"]
    )
except Exception as e:
    st.error(f"❌ Error loading Google Cloud credentials: {e}")
    st.stop()  # Stop execution if authentication fails

# -----------------------------------------------------------------------------
# ✅ Load BigQuery Data
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    query = """
    SELECT * FROM san_jose_fire_incidents.fire_incidents_2024
    """
    df = client.query(query).to_dataframe()
    df['Date_Time_Of_Event'] = pd.to_datetime(df['Date_Time_Of_Event'])
    df['Month'] = df['Date_Time_Of_Event'].dt.to_period("M")
    return df

df = load_data()

# -----------------------------------------------------------------------------
# ✅ Sidebar Filters
# -----------------------------------------------------------------------------
st.sidebar.header("Filters")
category_filter = st.sidebar.multiselect(
    "Select Incident Categories",
    df['Final_Incident_Category'].unique(),
    default=df['Final_Incident_Category'].unique()
)
month_filter = st.sidebar.multiselect(
    "Select Months",
    df['Month'].astype(str).unique(),
    default=df['Month'].astype(str).unique()
)

df_filtered = df[
    df['Final_Incident_Category'].isin(category_filter) &
    df['Month'].astype(str).isin(month_filter)
]

# -----------------------------------------------------------------------------
# ✅ Main Title
# -----------------------------------------------------------------------------
st.title("San Jose Fire Incidents (2024)")

# -----------------------------------------------------------------------------
# ✅ Bar Chart: Incident Categories
# -----------------------------------------------------------------------------
st.subheader("Most Common Fire Incident Categories")
plt.figure(figsize=(12, 6))
sns.countplot(
    y=df_filtered['Final_Incident_Category'],
    order=df_filtered['Final_Incident_Category'].value_counts().index
)
plt.xlabel("Number of Incidents")
st.pyplot(plt)

# -----------------------------------------------------------------------------
# ✅ Line Chart: Incidents Over Time
# -----------------------------------------------------------------------------
st.subheader("Fire Incidents Over Time")
plt.figure(figsize=(12, 6))
df_filtered.groupby('Month').size().plot(kind='line', marker='o')
plt.xlabel("Month")
plt.xticks(rotation=45)
st.pyplot(plt)

# -----------------------------------------------------------------------------
# ✅ Geolocation Mapping of Top 5 Streets
# -----------------------------------------------------------------------------
st.subheader("Top Streets with Most Incidents")
top_streets = df_filtered['Street_Name'].value_counts().head(5).index.tolist()

# Load Google Maps API Key from secrets
try:
    GOOGLE_MAPS_API_KEY = st.secrets["google_maps"]["api_key"]
except KeyError:
    st.error("❌ Google Maps API Key not found in secrets! Make sure [google_maps].api_key is set.")
    st.stop()

gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

def get_lat_lon(street_name, city="San Jose", state="CA"):
    try:
        geocode_result = gmaps.geocode(f"{street_name}, {city}, {state}")
        if geocode_result:
            location = geocode_result[0]['geometry']['location']
            return location['lat'], location['lng']
        return None, None
    except Exception as e:
        print(f"Error geocoding {street_name}: {e}")
        return None, None

df_top_streets = pd.DataFrame({
    "Street_Name": top_streets,
    "Incident_Count": df_filtered['Street_Name'].value_counts().head(5).values
})
df_top_streets[['Latitude', 'Longitude']] = df_top_streets['Street_Name'].apply(
    lambda x: pd.Series(get_lat_lon(x))
)
df_top_streets.dropna(inplace=True)

# Display map
st.subheader("Incident Locations on Map")
city_map = folium.Map(location=[37.3382, -121.8863], zoom_start=12)
for _, row in df_top_streets.iterrows():
    folium.Marker(
        location=[row['Latitude'], row['Longitude']],
        popup=f"Street: {row['Street_Name']} - {row['Incident_Count']} Incidents",
        icon=folium.Icon(color="red")
    ).add_to(city_map)
folium_static(city_map)

# -----------------------------------------------------------------------------
# ✅ Looker Studio Visualizations
# -----------------------------------------------------------------------------
st.subheader("Looker Studio Visualizations")

looker_reports = {
    "Most Common Fire Incident Categories": "https://lookerstudio.google.com/embed/reporting/df0ea516-d86d-4e9d-a762-dc37703c2a70/page/Dqv4E",
    "Fire Incidents Over Time": "https://lookerstudio.google.com/embed/reporting/e6348672-9e65-4ceb-ac35-01ebe375dc3d/page/BBx4E",
    "Street Areas with High Incidents": "https://lookerstudio.google.com/embed/reporting/64bb961b-b8dd-4006-bba7-374c60612e97/page/2by4E",
    "Incidents Locations on Map": "https://lookerstudio.google.com/embed/reporting/c7a8737e-7b0f-4b03-818c-7e1b3319bbe6/page/Qpx4E"
}

for title, report in looker_reports.items():
    st.markdown(f"### {title}")
    st.components.v1.iframe(report, width=800, height=600)
