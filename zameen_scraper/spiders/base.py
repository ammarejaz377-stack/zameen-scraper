import json
import logging
from datetime import datetime, timezone

import scrapy
from scrapy.exceptions import CloseSpider

from zameen_scraper.config import (
    BASE_URL, CATEGORIES, CITIES, HITS_PER_PAGE, MAX_BLOCKED_RESPONSES,
)
from zameen_scraper.items import ListingItem

logger = logging.getLogger(__name__)


def _extract_balanced_json(html: str, key: str):
    """
    Pull out the JSON value for `"key":` in a big blob of HTML/JS, by
    bracket-matching from the opening [ or { instead of relying on a regex
    to find the end. The embedded page state is minified JSON, but it's far
    too large (and structurally variable release to release) to match with
    a single regex reliably -- this is the same approach used during
    research to pull the `hits` array out by hand.
    """
    marker = f'"{key}":'
    idx = html.find(marker)
    if idx == -1:
        return None
    start = idx + len(marker)
    while start < len(html) and html[start] not in "[{":
        # skip whitespace, shouldn't normally trigger on minified output
        start += 1
    if start >= len(html):
        return None
    open_ch = html[start]
    close_ch = "]" if open_ch == "[" else "}"
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(html)):
        c = html[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == open_ch:
                depth += 1
            elif c == close_ch:
                depth -= 1
                if depth == 0:
                    return json.loads(html[start : i + 1])
    return None


def _epoch_to_iso(value):
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
    except (ValueError, OSError, OverflowError):
        return None


def _location_parts(location):
    """location is a list of {level, name, ...} dicts, level 0 = country up."""
    if not location:
        return None, None, None, None
    by_level = sorted(location, key=lambda x: x.get("level", 0))
    country = by_level[0]["name"] if len(by_level) > 0 else None
    province = by_level[1]["name"] if len(by_level) > 1 else None
    city = by_level[2]["name"] if len(by_level) > 2 else None
    area_name = " > ".join(p["name"] for p in by_level[3:]) or None
    return country, province, city, area_name


def _category_path(category):
    if not category:
        return None
    by_level = sorted(category, key=lambda x: x.get("level", 0))
    return " > ".join(c["name"] for c in by_level)


class BaseZameenSpider(scrapy.Spider):
    """
    Shared crawl logic for the sale and rent spiders. Subclasses only need
    to set `purpose` ("for-sale" / "for-rent") and `slug_key`
    ("sale_slug" / "rent_slug") -- everything else (URL generation,
    embedded-JSON parsing, pagination, validation) is identical.
    """

    purpose = None
    slug_key = None
    custom_settings = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.error_count = 0
        self.blocked_count = 0

    def _iter_start_requests(self):
        for city in CITIES:
            for category in CATEGORIES:
                slug = category.get(self.slug_key)
                if not slug:
                    continue  # this category doesn't exist for this purpose
                url = f"{BASE_URL}/{slug}/{city['slug']}-{city['id']}-1.html"
                yield scrapy.Request(
                    url,
                    callback=self.parse_page,
                    meta={
                        "city": city,
                        "category": category,
                        "slug": slug,
                        "page": 1,
                    },
                    errback=self.on_error,
                )

    async def start(self):
        # Scrapy >=2.13 entry point.
        for request in self._iter_start_requests():
            yield request

    def start_requests(self):
        # Kept for compatibility with Scrapy <2.13 / any tooling that still
        # calls this directly.
        yield from self._iter_start_requests()

    def parse_page(self, response):
        city = response.meta["city"]
        category = response.meta["category"]
        slug = response.meta["slug"]
        page = response.meta["page"]

        if "captchaChallenge" in response.url:
            self._register_block(f"redirected to CAPTCHA challenge from {response.url}")
            return

        hits = _extract_balanced_json(response.text, "hits")
        if hits is None:
            logger.warning(
                "No 'hits' payload found for %s (city=%s, category=%s, page=%s) -- "
                "page layout may have changed, skipping.",
                response.url, city["name"], category["name"], page,
            )
            return

        if page == 1:
            purpose_seen = self._extract_purpose(response.text)
            if purpose_seen != self.purpose:
                logger.warning(
                    "Skipping %s/%s: expected purpose=%s but page reports purpose=%s "
                    "(category likely doesn't exist for this city/purpose combo).",
                    city["name"], slug, self.purpose, purpose_seen,
                )
                return

        for hit in hits:
            yield self._build_item(hit, city, category)

        if page == 1:
            nb_hits = self._extract_nb_hits(response.text)
            logger.info(
                "%s / %s in %s: %s hits reported (paginating one page at a time; "
                "Zameen enforces an undocumented result-window cap below the "
                "reported total for large categories, so the real crawled count "
                "may come in lower)",
                self.purpose, category["name"], city["name"], nb_hits,
            )

        # Follow one page at a time rather than pre-computing every page from
        # nbHits: Zameen's reported nbHits can meaningfully exceed the actual
        # crawlable depth (an undocumented result-window cap), so generating
        # every page up front produces a long, predictable tail of wasted
        # 404s. A short page (fewer than a full batch) is the natural
        # end-of-results signal; a failed request (e.g. hitting the cap)
        # simply isn't followed further, at the cost of at most one wasted
        # request per category instead of hundreds.
        if len(hits) >= HITS_PER_PAGE:
            next_page = page + 1
            url = f"{BASE_URL}/{slug}/{city['slug']}-{city['id']}-{next_page}.html"
            yield scrapy.Request(
                url,
                callback=self.parse_page,
                meta={
                    "city": city,
                    "category": category,
                    "slug": slug,
                    "page": next_page,
                },
                errback=self.on_error,
            )

    def on_error(self, failure):
        self.error_count += 1
        response = getattr(failure.value, "response", None)
        if response is not None and response.status in (403, 429):
            self._register_block(f"HTTP {response.status} on {failure.request.url}")
        else:
            logger.error("Request failed: %s", failure.request.url)

    def _register_block(self, reason: str):
        self.blocked_count += 1
        logger.warning(
            "Blocked/CAPTCHA response (%d/%d so far): %s",
            self.blocked_count, MAX_BLOCKED_RESPONSES, reason,
        )
        if self.blocked_count >= MAX_BLOCKED_RESPONSES:
            raise CloseSpider(
                f"Aborting: hit {self.blocked_count} blocked/CAPTCHA responses -- "
                "the site appears to have flagged this IP. Stopping now instead of "
                "continuing to hammer it and risking a longer/harder ban."
            )

    @staticmethod
    def _extract_purpose(html: str):
        marker = '"purpose":{"type":"exact","attribute":"purpose","value":"'
        idx = html.find(marker)
        if idx == -1:
            return None
        start = idx + len(marker)
        end = html.find('"', start)
        return html[start:end]

    @staticmethod
    def _extract_nb_hits(html: str):
        marker = '"nbHits":'
        idx = html.find(marker)
        if idx == -1:
            return None
        start = idx + len(marker)
        end = start
        while end < len(html) and html[end].isdigit():
            end += 1
        return int(html[start:end]) if end > start else None

    def _build_item(self, hit: dict, city: dict, category: dict) -> ListingItem:
        country, province, hit_city, area_name = _location_parts(hit.get("location"))
        installments = hit.get("installments") or {}
        agency = hit.get("agency") or {}
        phone_numbers = hit.get("phoneNumber") or {}
        geography = hit.get("geography") or {}
        cover_photo = hit.get("coverPhoto") or {}
        cover_video = hit.get("coverVideo") or {}
        project = hit.get("project") or {}
        payment_details = hit.get("paymentDetails") or {}

        slug = hit.get("slug")
        item = ListingItem(
            listing_id=hit.get("externalID"),
            internal_id=hit.get("id"),
            listing_url=f"{BASE_URL}/Property/{slug}.html" if slug else None,
            purpose=hit.get("purpose"),
            crawl_city=city["name"],
            crawl_category=category["name"],
            title=hit.get("title"),
            title_urdu=hit.get("title_l1"),
            short_description=hit.get("shortDescription"),
            short_description_urdu=hit.get("shortDescription_l1"),
            price=hit.get("price"),
            rent_frequency=hit.get("rentFrequency"),
            installment_advance_amount=installments.get("advanceAmount"),
            installment_monthly_amount=installments.get("monthlyAmount"),
            installment_remaining_count=installments.get("remainingInstallments"),
            payment_development_charges=payment_details.get("developmentCharges"),
            payment_total_balloon_amount=payment_details.get("totalBalloonPayment"),
            payment_balloon_amount=payment_details.get("balloonPaymentAmount"),
            payment_possession_fee=payment_details.get("possessionFee"),
            payment_balloting_fee=payment_details.get("ballotingFee"),
            payment_balloon_payments_count=payment_details.get("balloonPaymentsCount"),
            area_sqm=hit.get("area"),
            rooms=hit.get("rooms"),
            baths=hit.get("baths"),
            country=country,
            province=province,
            city=hit_city,
            area_name=area_name,
            latitude=geography.get("lat"),
            longitude=geography.get("lng"),
            has_exact_geography=hit.get("hasExactGeography"),
            category_path=_category_path(hit.get("category")),
            agency_id=agency.get("externalID"),
            agency_name=agency.get("name"),
            agency_tier=agency.get("product"),
            contact_name=hit.get("contactName"),
            phone=phone_numbers.get("phone"),
            whatsapp=phone_numbers.get("whatsapp"),
            photo_count=hit.get("photoCount"),
            video_count=hit.get("videoCount"),
            cover_photo_url=cover_photo.get("url"),
            cover_video_host=cover_video.get("host"),
            cover_video_url=cover_video.get("url"),
            product=hit.get("product"),
            is_verified=hit.get("isVerified"),
            property_tour=hit.get("propertyTour"),
            state=hit.get("state"),
            permit_number=hit.get("permitNumber"),
            reference_number=hit.get("referenceNumber"),
            project_id=project.get("externalID"),
            project_slug=project.get("slug"),
            created_at=_epoch_to_iso(hit.get("createdAt")),
            updated_at=_epoch_to_iso(hit.get("updatedAt")),
            scraped_at=datetime.now(timezone.utc).isoformat(),
        )
        return item
