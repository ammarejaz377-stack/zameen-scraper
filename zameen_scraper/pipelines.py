import csv
import json
import logging
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from zameen_scraper.config import MAX_BLOCKED_RESPONSES

logger = logging.getLogger(__name__)

FIELD_ORDER = [
    "listing_id", "internal_id", "listing_url",
    "purpose", "crawl_city", "crawl_category",
    "title", "title_urdu", "short_description", "short_description_urdu",
    "price", "rent_frequency",
    "installment_advance_amount", "installment_monthly_amount", "installment_remaining_count",
    "payment_development_charges", "payment_total_balloon_amount", "payment_balloon_amount",
    "payment_possession_fee", "payment_balloting_fee", "payment_balloon_payments_count",
    "area_sqm", "rooms", "baths",
    "country", "province", "city", "area_name",
    "latitude", "longitude", "has_exact_geography",
    "category_path",
    "agency_id", "agency_name", "agency_tier",
    "contact_name", "phone", "whatsapp",
    "photo_count", "video_count", "cover_photo_url", "cover_video_host", "cover_video_url",
    "product", "is_verified", "property_tour", "state",
    "permit_number", "reference_number", "project_id", "project_slug",
    "created_at", "updated_at", "scraped_at",
]

PARQUET_ROW_GROUP_SIZE = 5000  # rows buffered per row group, not per file -- output is one file


class CsvParquetExportPipeline:
    """
    Writes every item to one CSV and one Parquet file per run, both sharing
    the same name (just the run timestamp) inside a single per-spider
    folder that persists across runs:

        output/zameen_sale/12-09-2026_21-53.csv
        output/zameen_sale/12-09-2026_21-53.parquet
        output/zameen_sale/12-09-2026_22-40.csv     <- next run
        output/zameen_sale/12-09-2026_22-40.parquet

    CSV is written row-by-row as items arrive (a crash only costs the
    in-flight row). Parquet stays a single file by buffering rows into row
    groups (PARQUET_ROW_GROUP_SIZE each) and writing each group to the same
    open pyarrow.parquet.ParquetWriter -- multiple row groups, one file.

    A separate load-to-db script is expected to read these files
    afterwards -- scraping and storing are deliberately decoupled.
    """

    def open_spider(self, spider):
        self.started_at = datetime.now(timezone.utc)
        self.run_stamp = self.started_at.strftime("%d-%m-%Y_%H-%M")

        self.out_dir = Path("output") / spider.name
        self.out_dir.mkdir(parents=True, exist_ok=True)

        self.csv_path = self.out_dir / f"{self.run_stamp}.csv"
        self.parquet_path = self.out_dir / f"{self.run_stamp}.parquet"
        self.summary_path = self.out_dir / f"{self.run_stamp}_summary.txt"
        self.summary_json_path = self.out_dir / f"{self.run_stamp}_summary.json"

        self.csv_file = open(self.csv_path, "w", newline="", encoding="utf-8")
        self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=FIELD_ORDER, extrasaction="ignore")
        self.csv_writer.writeheader()

        self.schema = self._schema()
        self.parquet_writer = pq.ParquetWriter(self.parquet_path, self.schema)

        self.buffer = []
        self.total_written = 0
        self.category_counts = Counter()
        logger.info("Writing output to %s and %s", self.csv_path, self.parquet_path)

    def process_item(self, item, spider):
        row = dict(item)
        row = {k: row.get(k) for k in FIELD_ORDER}

        self.csv_writer.writerow(row)
        self.buffer.append(row)
        self.total_written += 1
        self.category_counts[(row.get("crawl_city"), row.get("crawl_category"))] += 1

        if len(self.buffer) >= PARQUET_ROW_GROUP_SIZE:
            self._flush_parquet_row_group()

        return item

    def close_spider(self, spider):
        if self.buffer:
            self._flush_parquet_row_group()
        self.parquet_writer.close()
        self.csv_file.close()

        stats = self._build_stats(spider)
        summary = self._render_summary_text(stats)
        # Printed directly (not via logger) so it's guaranteed to show in the
        # terminal even when running with --logfile, which redirects the
        # logging handler to a file. Also logged, and written to its own
        # file so a deployment step can pick it up (e.g. to email it)
        # without having to scrape it out of the main log.
        print(summary)
        logger.info(summary)
        self.summary_path.write_text(summary, encoding="utf-8")
        # Structured twin of the same data, for anything that wants to parse
        # it programmatically (e.g. a dashboard) instead of the text block.
        self.summary_json_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    def _flush_parquet_row_group(self):
        table = pa.Table.from_pylist(self.buffer, schema=self.schema)
        self.parquet_writer.write_table(table)
        self.buffer = []

    def _build_stats(self, spider) -> dict:
        finished_at = datetime.now(timezone.utc)
        duration_seconds = int((finished_at - self.started_at).total_seconds())

        error_count = getattr(spider, "error_count", 0)
        blocked_count = getattr(spider, "blocked_count", 0)
        status = "aborted_blocked" if blocked_count >= MAX_BLOCKED_RESPONSES else "ok"

        return {
            "spider": spider.name,
            "purpose": getattr(spider, "purpose", None),
            "status": status,
            "started_at": self.started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": duration_seconds,
            "total_listings": self.total_written,
            "error_count": error_count,
            "blocked_count": blocked_count,
            "csv_path": str(self.csv_path),
            "csv_size_bytes": os.path.getsize(self.csv_path),
            "parquet_path": str(self.parquet_path),
            "parquet_size_bytes": os.path.getsize(self.parquet_path),
            "category_counts": [
                {"city": city, "category": category, "count": count}
                for (city, category), count in sorted(
                    self.category_counts.items(), key=lambda x: -x[1]
                )
            ],
        }

    @staticmethod
    def _render_summary_text(stats: dict) -> str:
        minutes, seconds = divmod(stats["duration_seconds"], 60)
        started = datetime.fromisoformat(stats["started_at"]).strftime("%d-%m-%Y %H:%M:%S")
        finished = datetime.fromisoformat(stats["finished_at"]).strftime("%d-%m-%Y %H:%M:%S")
        status_label = (
            "ABORTED (blocked/CAPTCHA threshold hit)" if stats["status"] == "aborted_blocked" else "OK"
        )

        lines = [
            "=" * 70,
            "ZAMEEN SCRAPER RUN SUMMARY",
            "=" * 70,
            f"Spider:          {stats['spider']} ({stats['purpose']})",
            f"Status:          {status_label}",
            f"Started:         {started} UTC",
            f"Finished:        {finished} UTC",
            f"Duration:        {minutes}m {seconds}s",
            f"Total listings:  {stats['total_listings']:,}",
            f"Failed requests: {stats['error_count']}  (of which blocked/CAPTCHA: {stats['blocked_count']})",
            "",
            f"CSV:     {stats['csv_path']}  ({stats['csv_size_bytes'] / (1024 * 1024):.1f} MB)",
            f"Parquet: {stats['parquet_path']}  ({stats['parquet_size_bytes'] / (1024 * 1024):.1f} MB)",
            "",
            "Breakdown by city / category:",
        ]
        for row in stats["category_counts"]:
            lines.append(f"  {row['city'] or '?':<15} {row['category'] or '?':<20} {row['count']:>8,}")
        lines.append("=" * 70)
        return "\n".join(lines)

    @staticmethod
    def _schema():
        # Explicit schema keeps every row group consistent even when a given
        # batch happens to contain only None for a nullable column.
        string_fields = {
            "listing_id", "listing_url", "purpose", "crawl_city", "crawl_category",
            "title", "title_urdu", "short_description", "short_description_urdu",
            "rent_frequency", "country", "province", "city", "area_name",
            "category_path", "agency_id", "agency_name", "agency_tier",
            "contact_name", "phone", "whatsapp", "cover_photo_url", "product",
            "cover_video_host", "cover_video_url", "project_id", "project_slug",
            "state", "permit_number", "reference_number", "created_at",
            "updated_at", "scraped_at",
        }
        int_fields = {
            "internal_id", "installment_advance_amount", "installment_monthly_amount",
            "installment_remaining_count", "rooms", "baths", "photo_count", "video_count",
            "payment_balloon_payments_count",
        }
        float_fields = {
            "price", "area_sqm", "latitude", "longitude",
            "payment_development_charges", "payment_total_balloon_amount",
            "payment_balloon_amount", "payment_possession_fee", "payment_balloting_fee",
        }
        bool_fields = {"has_exact_geography", "is_verified", "property_tour"}

        fields = []
        for name in FIELD_ORDER:
            if name in string_fields:
                fields.append(pa.field(name, pa.string()))
            elif name in int_fields:
                fields.append(pa.field(name, pa.int64()))
            elif name in float_fields:
                fields.append(pa.field(name, pa.float64()))
            elif name in bool_fields:
                fields.append(pa.field(name, pa.bool_()))
            else:
                fields.append(pa.field(name, pa.string()))
        return pa.schema(fields)
