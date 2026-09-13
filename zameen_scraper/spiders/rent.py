from zameen_scraper.spiders.base import BaseZameenSpider


class RentSpider(BaseZameenSpider):
    name = "zameen_rent"
    purpose = "for-rent"
    slug_key = "rent_slug"
