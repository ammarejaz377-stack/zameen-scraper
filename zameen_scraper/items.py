import scrapy


class ListingItem(scrapy.Item):
    # identity
    listing_id = scrapy.Field()      # Zameen's externalID -- the dedup key
    internal_id = scrapy.Field()     # Zameen's internal/Algolia object id
    listing_url = scrapy.Field()

    # crawl context (which config combo produced this row)
    purpose = scrapy.Field()         # for-sale / for-rent
    crawl_city = scrapy.Field()
    crawl_category = scrapy.Field()

    # core fields
    title = scrapy.Field()
    title_urdu = scrapy.Field()
    short_description = scrapy.Field()
    short_description_urdu = scrapy.Field()
    price = scrapy.Field()
    rent_frequency = scrapy.Field()

    installment_advance_amount = scrapy.Field()
    installment_monthly_amount = scrapy.Field()
    installment_remaining_count = scrapy.Field()

    # richer balloon-payment plan details, present on some installment listings
    # (e.g. big developer schemes) in addition to the simpler installment fields above
    payment_development_charges = scrapy.Field()
    payment_total_balloon_amount = scrapy.Field()
    payment_balloon_amount = scrapy.Field()
    payment_possession_fee = scrapy.Field()
    payment_balloting_fee = scrapy.Field()
    payment_balloon_payments_count = scrapy.Field()

    area_sqm = scrapy.Field()        # Zameen normalizes area to square meters internally
    rooms = scrapy.Field()           # bedrooms
    baths = scrapy.Field()

    # location (flattened from the hit's own location hierarchy)
    country = scrapy.Field()
    province = scrapy.Field()
    city = scrapy.Field()
    area_name = scrapy.Field()       # locality / housing scheme, deepest level(s) joined
    latitude = scrapy.Field()
    longitude = scrapy.Field()
    has_exact_geography = scrapy.Field()

    # category (flattened from the hit's own category hierarchy)
    category_path = scrapy.Field()

    # agency / agent
    agency_id = scrapy.Field()
    agency_name = scrapy.Field()
    agency_tier = scrapy.Field()
    contact_name = scrapy.Field()
    phone = scrapy.Field()
    whatsapp = scrapy.Field()

    # media / ad metadata
    photo_count = scrapy.Field()
    video_count = scrapy.Field()
    cover_photo_url = scrapy.Field()
    cover_video_host = scrapy.Field()
    cover_video_url = scrapy.Field()
    product = scrapy.Field()         # ad boost tier: superhot/hot/premium/free
    is_verified = scrapy.Field()
    property_tour = scrapy.Field()
    state = scrapy.Field()           # active/inactive
    permit_number = scrapy.Field()
    reference_number = scrapy.Field()

    # set only for listings tied to a builder/developer project (e.g. new
    # apartment schemes) -- not present on individual resale listings
    project_id = scrapy.Field()
    project_slug = scrapy.Field()
    created_at = scrapy.Field()      # ISO datetime
    updated_at = scrapy.Field()

    scraped_at = scrapy.Field()
