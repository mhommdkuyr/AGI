from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_ibb_inventory.py"


class InventoryAuditCliTest(unittest.TestCase):
    def test_audit_counts_and_flags_template_and_generic_map_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            workbook_path = temp / "fixture.xlsx"
            report_path = temp / "audit.md"
            flags_path = temp / "flags.csv"

            wb = Workbook()
            ws = wb.active
            ws.title = "الجدول الشامل"
            ws.append([
                "اسم المنشأة أو المعلم", "التصنيف", "العنوان التفصيلي والشارع",
                "الهاتف", "خط العرض Lat", "خط الطول Lng",
                "رابط الموقع على خريطة جوجل", "التقييم", "الطوابق", "الارتفاع م",
            ])
            ws.append([
                "بقالة الورافي", "بقالة", "شارع عام", "0777123456",
                13.99, 44.17,
                "https://www.google.com/maps/search/?api=1&query=13.99,44.17",
                4.2, 1, 3,
            ])
            ws.append([
                "بقالة الورافي", "بقالة", "عنوان آخر", "",
                13.98, 44.16,
                "https://www.google.com/maps/place/example",
                4.0, 1, 3,
            ])
            ws.append([
                "متجر تجريبي #12", "متجر", "مبنى رقم 24، الشارع الفرعي 3", "",
                13.97, 44.15,
                "https://www.google.com/maps/search/?api=1&query=13.97,44.15",
                4.1, 2, 5,
            ])
            wb.save(workbook_path)

            proc = subprocess.run(
                [
                    sys.executable, str(SCRIPT), str(workbook_path),
                    "--report", str(report_path),
                    "--flagged-csv", str(flags_path),
                ],
                capture_output=True, text=True, check=False, timeout=60,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            summary = json.loads(proc.stdout)
            self.assertEqual(summary["rows"], 3)
            self.assertEqual(summary["unique_normalized_names"], 2)
            self.assertEqual(summary["repeated_name_rows"], 2)
            self.assertEqual(summary["numbered_template_names"], 1)
            self.assertEqual(summary["template_address_patterns"], 1)
            self.assertEqual(summary["generic_google_maps_coordinate_search_urls"], 2)
            self.assertTrue(report_path.exists())
            self.assertTrue(flags_path.exists())
            self.assertGreater(summary["flagged_rows"], 0)


if __name__ == "__main__":
    unittest.main()
