"""
Crawl scope: which cities and property categories to hit.

Every (slug, id) pair below was resolved against the live site, not guessed:
- City ids came from the `popularCities` block embedded in zameen.com's homepage.
- Category slugs came from the category navigation embedded in real
  /Homes/ and /Rentals/ search-result pages (and cross-checked by requesting
  each one and confirming the response's own "purpose" filter matches).

City ids are load-bearing: Zameen's routing keys off the numeric id, not the
name (e.g. "/Homes/Faisalabad-1-1.html" 301-redirects to Lahore, since 1 is
Lahore's id). Getting one wrong sends the whole category to the wrong city
silently via redirect, so don't add a city here without confirming its id
the same way (fetch https://www.zameen.com/ and look for its slug inside the
"popularCities"/"impressionCities" blocks).
"""

CITIES = [
    {"name": "Lahore", "slug": "Lahore", "id": 1},
    {"name": "Karachi", "slug": "Karachi", "id": 2},
    {"name": "Islamabad", "slug": "Islamabad", "id": 3},
    {"name": "Rawalpindi", "slug": "Rawalpindi", "id": 41},
    {"name": "Faisalabad", "slug": "Faisalabad", "id": 16},
    {"name": "Multan", "slug": "Multan", "id": 15},
    {"name": "Peshawar", "slug": "Peshawar", "id": 17},
    {"name": "Quetta", "slug": "Quetta", "id": 18},
    {"name": "Gujranwala", "slug": "Gujranwala", "id": 327},
    {"name": "Sialkot", "slug": "Sialkot", "id": 480},
]

# Only leaf property-type categories are listed here -- never the "Homes"
# / "Rentals" aggregate umbrellas, since those just re-list everything below
# them and would duplicate every record already captured by its own category.
#
# sale_slug / rent_slug is None where that side genuinely doesn't exist on
# the site (e.g. "Rooms" is rent-only, plots/land have no rent listings).
CATEGORIES = [
    {"name": "Houses", "sale_slug": "Houses_Property", "rent_slug": "Rentals_Houses_Property"},
    {"name": "Flats/Apartments", "sale_slug": "Flats_Apartments", "rent_slug": "Rentals_Flats_Apartments"},
    {"name": "Upper Portions", "sale_slug": "Upper_Portions", "rent_slug": "Rentals_Upper_Portions"},
    {"name": "Lower Portions", "sale_slug": "Lower_Portions", "rent_slug": "Rentals_Lower_Portions"},
    {"name": "Farm Houses", "sale_slug": "Farm_Houses", "rent_slug": "Rentals_Farm_Houses"},
    {"name": "Penthouse", "sale_slug": "Penthouse", "rent_slug": "Rentals_Penthouse"},
    {"name": "Rooms", "sale_slug": None, "rent_slug": "Rentals_Rooms"},
    {"name": "Residential Plots", "sale_slug": "Residential_Plots", "rent_slug": None},
    {"name": "Commercial Plots", "sale_slug": "Commercial_Plots", "rent_slug": None},
    {"name": "Agricultural Land", "sale_slug": "Agricultural_Land", "rent_slug": None},
    {"name": "Plot Files", "sale_slug": "Plot_Files", "rent_slug": None},
    {"name": "Offices", "sale_slug": "Offices", "rent_slug": "Rentals_Offices"},
    {"name": "Retail Shops", "sale_slug": "Retail_Shops", "rent_slug": "Rentals_Retail_Shops"},
    {"name": "Buildings", "sale_slug": "Buildings", "rent_slug": "Rentals_Buildings"},
    {"name": "Factories", "sale_slug": "Factories", "rent_slug": "Rentals_Factories"},
    {"name": "Warehouses", "sale_slug": "Warehouses", "rent_slug": "Rentals_Warehouses"},
    {"name": "Other Commercial", "sale_slug": "Other_Commercial_Properties", "rent_slug": "Rentals_Other_Commercial_Properties"},
]

BASE_URL = "https://www.zameen.com"
HITS_PER_PAGE = 25  # confirmed from the live "hitsPerPage" search config

# If a run sees this many blocked/CAPTCHA responses, abort entirely rather
# than keep hammering a site that has already flagged this IP.
MAX_BLOCKED_RESPONSES = 15
