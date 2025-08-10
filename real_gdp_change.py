# %%
"""
Visualize the biggest annual real GDP changes per country (2000-2024)
- Connects to a MySQL database for GDP data
- Uses Natural Earth shapefiles for world map
- Handles disputed territories and country name mismatches
- Plots a choropleth map with custom legend and annotations
"""
import mysql.connector
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy import create_engine, text
from mysql.connector import Error
from getpass import getpass
import pandas as pd
import matplotlib.pyplot as plt
import geopandas as gpd
import numpy as np
from shapely.ops import unary_union
from matplotlib.patches import Patch
import os

# %%
# --- Database connection setup ---

user = os.getenv("MYSQL_USER")
password = getpass("MySQL password: ")
database = os.getenv("MYSQL_DATABASE")

# Create SQLAlchemy engine for MySQL connection
engine = create_engine(f"mysql+pymysql://{user}:{password}@localhost/{database}")

# Test database connection
try:
    with engine.connect() as conn:
        # Wrap query in text() function
        result = conn.execute(text("SELECT '✅ Connection successful' AS status"))
        print(result.scalar())  # Fetch the first column of first row
except Exception as e:
    print(f"❌ Connection failed: {e}")

# %%
# Load GDP change data from database into DataFrame
df = pd.read_sql(text(query), engine)

# %%
world_10m = gpd.read_file(
    "https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_admin_0_countries.zip"
)

# %%
# Map country names in your data to match Natural Earth names for merging
name_mapping = {
    'Antigua and Barbuda': 'Antigua and Barb.',
    'Bosnia and Herzegovina': 'Bosnia and Herz.',
    'Cape Verde': 'Cabo Verde',
    'Central African Republic': 'Central African Rep.',
    'Dominican Republic': 'Dominican Rep.',
    'DR Congo': 'Dem. Rep. Congo',
    'East Timor': 'Timor-Leste',
    'Equatorial Guinea': 'Eq. Guinea',
    'Eswatini': 'eSwatini',
    'Ivory Coast': "Côte d'Ivoire",
    'Marshall Islands': 'Marshall Is.',
    'Saint Kitts and Nevis': 'St. Kitts and Nevis',
    'Saint Vincent and the Grenadines': 'St. Vin. and Gren.',
    'Sao Tome and Principe': 'São Tomé and Principe',
    'Solomon Islands': 'Solomon Is.',
    'South Sudan': 'S. Sudan',
    'United States': 'United States of America'
}

# %%
# Standardize country names for merging with shapefile
df['country_standardized'] = df['country'].replace(name_mapping)

# %%
# --- Handle disputed territories and special cases ---

# Load disputed areas shapefile (Natural Earth)
disputed = gpd.read_file(
    "https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_admin_0_disputed_areas.zip"
) 

# Merge Cyprus and Northern Cyprus geometries for unified display
south_cy = world_10m.loc[world_10m['NAME']=='Cyprus', 'geometry']
north_cy = disputed.loc[disputed['NAME']=='N. Cyprus', 'geometry']
north_cy = north_cy.to_crs(world_10m.crs)
full_cy = unary_union(list(south_cy) + list(north_cy))
raw_union = unary_union(list(south_cy) + list(north_cy))
closed = raw_union.buffer(0.05, join_style=1)
full_cy = closed.buffer(-0.05, join_style=1)
world_10m.loc[world_10m['NAME']=='Cyprus', 'geometry'] = full_cy

# %%
# Merge Somalia and Somaliland geometries for unified display
somalia = world_10m.loc[world_10m['NAME']=='Somalia', 'geometry']
somaliland = disputed.loc[disputed['NAME']=='Somaliland', 'geometry']
somaliland = somaliland.to_crs(world_10m.crs)
full_somalia = unary_union(list(somalia) + list(somaliland))
world_10m.loc[world_10m['NAME']=='Somalia', 'geometry'] = full_somalia

# Remove Somaliland as a separate entity (already merged above)
world_10m = world_10m[world_10m['NAME'] != 'Somaliland']

# %%
# --- Merge GDP data with world geometries ---

# Merge world geometries with GDP data using standardized country names
merged = world_10m.merge(
    df,
    left_on='NAME',
    right_on='country_standardized',
    how='left'  # Now safe to use right since we've standardized
)

# %%
# Remove Antarctica (not relevant for GDP analysis)
merged = merged[merged['NAME'] != 'Antarctica']

# %%
# --- Handle Crimea: assign to Ukraine, remove from Russia ---

# Load admin-1 (states/provinces) shapefile to extract Crimea geometry

admin1 = gpd.read_file(
    "https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_admin_1_states_provinces.zip"
)

mask = admin1['name_en'].str.contains('Crimea', case=False, na=False)
crimea_raw = admin1.loc[mask, 'geometry'].union_all()
crimea = (
    gpd.GeoSeries([crimea_raw], crs=admin1.crs)
       .to_crs(merged.crs)  # match the CRS of your merged GeoDataFrame
       .iloc[0]             # extract the geometry back out
       .buffer(0)           # clean up any tiny topology errors
)

# Remove Crimea from Russia's geometry
merged.loc[merged['NAME']=='Russia', 'geometry'] = (
    merged.loc[merged['NAME']=='Russia', 'geometry']
          .apply(lambda g: g.difference(crimea).buffer(0))
)

# Add Crimea to Ukraine's geometry
merged.loc[merged['NAME']=='Ukraine', 'geometry'] = (
    merged.loc[merged['NAME']=='Ukraine', 'geometry']
          .apply(lambda g: g.union(crimea))
)

# Clean up Russia's geometry (remove small islands, etc.)
russia_parts = merged.loc[merged['NAME']=='Russia', 'geometry'].explode(index_parts=False)
# Keep only parts larger than a minimum area threshold (tweak as needed)
min_area = 0.10  # Minimum area threshold for Russia's parts
large_parts = [part for part in russia_parts if part.area > min_area]
clean_russia = unary_union(large_parts)
merged.loc[merged['NAME']=='Russia', 'geometry'] = clean_russia

# (Re‑)union Crimea into Ukraine if needed
merged.loc[merged['NAME']=='Ukraine', 'geometry'] = (
    merged.loc[merged['NAME']=='Ukraine', 'geometry']
          .union(crimea)
)

# %%
# --- Categorize GDP changes for visualization ---

# Define bins and category labels for GDP change
categories = ["<-20", "-20-(-10)", "-10-0", "0-5", "5-10", "10-20", ">20"]      
bin_edges = [-float('inf'), -20, -10, 0, 5, 10, 20, float('inf')]

# Assign each country to a change category based on its biggest_change value
merged['change_category'] = pd.cut(
    merged['biggest_change'],
    bins=bin_edges,
    labels=categories,
    right=False
)
# Define bins explicitly
bin_edges = [-20, -10, 0, 5, 10, 20]
  
# %%
# Choose color map: diverging if negatives present, sequential otherwise
cmap = plt.cm.get_cmap('RdYlGn' if any(merged['biggest_change'] < 0) else 'YlGnBu', len(categories))

# %%
fig, ax = plt.subplots(figsize=(15, 10))

# Plot the choropleth map
merged.plot(
    column='biggest_change',
    scheme='UserDefined',
    classification_kwds={'bins': bin_edges},
    cmap=cmap,
    legend=False,
    linewidth=0.4,
    edgecolor='gray',
    missing_kwds={'color': 'lightgrey', 'hatch': '///', 'edgecolor': 'grey'},
    ax=ax
)

# Build custom legend
cmap_reversed = cmap.reversed()
legend_handles = [
    Patch(facecolor=cmap_reversed(i), edgecolor='gray', label=f"{cat}%") 
    for i, cat in enumerate(reversed(categories))
]
legend_handles.append(
    Patch(facecolor='lightgrey', edgecolor='gray', hatch='///', label='No data')
)

ax.legend(
    handles=legend_handles,
    title='Biggest Annual \nGDP Change',
    title_fontsize=16,
    loc='lower left',
    bbox_to_anchor=(0.00, 0.37),
    frameon=False,
    fontsize=14
)

# Add annotation blocks for highlights and notes
fig.text(
    0.00, 0.12,
    r'$\bf{\it{Greatest\ leaps}}$' '\n' 
    r'$\bf{Equatorial\ Guinea:}$' ' 110,5%, 2000 (oil boom)\n' 
    r'$\bf{Libya:}$' ' 86,8%, 2012 (post civil war rebound)\n' 
    r'$\bf{Guyana:}$' ' 63,3%, 2022 (oil boom)\n'
    r'$\bf{\it{Steepest\ drops}}$' '\n'
    r'$\bf{South\ Sudan:}$' ' -50,3%, 2012 (shutdown of oil wells)\n' 
    r'$\bf{Central\ Afican\ Republic:}$' ' -36,4%, 2013 (coup and civil war)\n' 
    r'$\bf{Venezuela:}$' ' -30%, 2020 (sanctions, oil collapse and COVID)\n'
    r'$\bf{\it{Moderation\ award}}$' '\n' 
    r'$\bf{Norway:}$' ' 4%, 2004',
    ha='left', va='bottom',
    fontsize=13,
    usetex=False, 
    linespacing = 1.5
)

fig.text(
    0.45, 0.12,
    '\U0001F30D 146 countries had a positive peak year; 46 had a negative one\n'
    '\U0001F4C5 38 countries made their greatest leap in 2021 (post-COVID rebound)\n'
    '\U0001F4C5 27 saw their sharpest drop in 2020, and 7 in 2009\n'
    '\U0001F4C8 Guyana, Equatorial Guinea, Ethiopia, and China had the highest cumulative growth\n'
    '\U0001F4C9 Three countries had a negative sum: South Sudan, Venezuela, and Yemen\n'
    '\u26A0 Europe\'s steepest drop occurred in Ukraine (2022, Russian invasion)',
    ha='left', va='bottom',
    fontsize=15,
    usetex=False, 
    linespacing = 1.8,
    fontname='Segoe UI Emoji'
)

# Add source box
x, y = 0.37, 0.1  # position of text (figure coords)
text_str = "Source: IMF"
bbox_props = dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor="lightgray", linewidth=1)
fig.text(x, y, text_str, ha='center', va='center', fontsize=14, bbox=bbox_props)

# Set map extent and title
ax.set_xlim(-180, 180)
ax.set_ylim(-90, 90) 
ax.set_title('Biggest Annual Real GDP Change per Country (2000-2024)', fontsize=22)
ax.set_axis_off()
plt.tight_layout()

# Save and show figure
plt.savefig(
    'gdp_change',
    dpi=300,
    bbox_inches='tight',
    pad_inches=0.1,
    facecolor='white'  # ensures background is not transparent
)

# plt.savefig('gdp_change_map.png', dpi=300, bbox_inches='tight')
plt.show()










