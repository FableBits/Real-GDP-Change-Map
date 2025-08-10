# Real GDP Change Visualization

This project visualizes the biggest annual real GDP changes per country (2000-2024) using data from a MySQL database and Natural Earth shapefiles.

## Requirements
- Python 3.8+
- See `requirements.txt` for Python dependencies
- MySQL database with a table named `biggest_gdp_changes`

## Setup
1. Clone this repository.
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Set your MySQL credentials as environment variables in your terminal **before running the script**:
   
   **On Windows PowerShell:**
   ```powershell
   $env:MYSQL_USER="your_username"
   $env:MYSQL_DATABASE="your_db_name"
   ```
   The script will prompt you for your MySQL password securely.
4. Ensure you have access to the required MySQL database and that the table `biggest_gdp_changes` exists.
5. Run the script:
   ```
   python real_gdp_change.py
   ```

## Data Sources
- [Natural Earth shapefiles](https://www.naturalearthdata.com/downloads/10m-cultural-vectors/)
- IMF or your own GDP data in MySQL

## Notes
- No sensitive information is included in this repository.
- External data is referenced by URL; no large files are stored here.

## License
MIT
