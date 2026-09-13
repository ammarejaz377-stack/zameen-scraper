BOT_NAME = "zameen_scraper"

SPIDER_MODULES = ["zameen_scraper.spiders"]
NEWSPIDER_MODULE = "zameen_scraper.spiders"

# Respect robots.txt as a safety net: our target paths (/Houses_Property/,
# /Flats_Apartments/, /Rentals_*/, etc.) are confirmed NOT disallowed today,
# but if that ever changes on Zameen's end, this makes the crawler back off
# automatically instead of needing a code change to notice.
ROBOTSTXT_OBEY = True

# Conservative concurrency -- these are search-result pages, not an API
# meant for bulk traffic. Tune down further if you see 429s in the logs.
CONCURRENT_REQUESTS = 8
CONCURRENT_REQUESTS_PER_DOMAIN = 4
DOWNLOAD_DELAY = 0.5
RANDOMIZE_DOWNLOAD_DELAY = True

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 30.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 4.0

RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [429, 500, 502, 503, 504, 522, 524, 408]

DOWNLOADER_MIDDLEWARES = {
    "zameen_scraper.middlewares.RotateBrowserProfileMiddleware": 400,
}

ITEM_PIPELINES = {
    "zameen_scraper.pipelines.CsvParquetExportPipeline": 300,
}

LOG_LEVEL = "INFO"

REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
