from zameen_scraper.spiders.base import BaseZameenSpider


class SaleSpider(BaseZameenSpider):
    name = "zameen_sale"
    purpose = "for-sale"
    slug_key = "sale_slug"
