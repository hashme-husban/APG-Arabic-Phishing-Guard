import unittest
from unittest.mock import MagicMock, patch

from app.services.image_ocr_service import (
    _call_paddle_microservice,
    _clean,
    _clean_url,
    _parse_paddle_result,
    _remove_garbage_lines,
    extract_text_from_image_bytes,
    extract_urls,
    is_paddle_microservice_available,
    is_tesseract_available,
    repair_ocr_urls,
)


class RepairOcrUrlsTests(unittest.TestCase):
    def test_fixes_spaced_http_protocol(self):
        result = repair_ocr_urls("visit http : // example.com now")
        self.assertIn("http://example.com", result)

    def test_fixes_spaced_https_protocol(self):
        result = repair_ocr_urls("open https : // example.com/login")
        self.assertIn("https://example.com/login", result)

    def test_fixes_www_with_spaces(self):
        result = repair_ocr_urls("go to www . example . com")
        self.assertIn("www.example", result)

    def test_no_change_on_clean_url(self):
        result = repair_ocr_urls("https://example.com/path?q=1")
        self.assertEqual(result, "https://example.com/path?q=1")

    def test_arabic_sentence_kept_with_repaired_url(self):
        """Full Arabic sentence containing a spaced-out URL must both survive intact."""
        text = "تحقق من حسابك على http : // phishing.example.com / login الآن"
        result = repair_ocr_urls(text)
        self.assertIn("http://phishing.example.com/login", result)
        self.assertIn("تحقق", result)
        self.assertIn("حسابك", result)


class GarbageLineRemovalTests(unittest.TestCase):
    def test_arabic_lines_never_removed(self):
        text = "مرحبا بك\n|\nفي النظام"
        cleaned = _remove_garbage_lines(text)
        self.assertIn("مرحبا بك", cleaned)
        self.assertIn("في النظام", cleaned)

    def test_isolated_vertical_bar_removed(self):
        text = "مرحبا\n|\nالنص"
        cleaned = _remove_garbage_lines(text)
        self.assertNotIn("\n|\n", cleaned)

    def test_url_line_kept(self):
        text = "|\nhttps://example.com/login\n|"
        cleaned = _remove_garbage_lines(text)
        self.assertIn("https://example.com/login", cleaned)

    def test_meaningful_latin_word_kept(self):
        text = "click here\n|\nدخول"
        cleaned = _remove_garbage_lines(text)
        self.assertIn("click here", cleaned)

    def test_single_latin_char_removed(self):
        text = "نص عربي\nI\nمزيد"
        cleaned = _remove_garbage_lines(text)
        lines = [l for l in cleaned.split("\n") if l.strip() == "I"]
        self.assertEqual(lines, [])

    def test_does_not_remove_digit_sequences(self):
        text = "المبلغ\n0533123456\nللتواصل"
        cleaned = _remove_garbage_lines(text)
        self.assertIn("0533123456", cleaned)


class CleanPipelineTests(unittest.TestCase):
    def test_arabic_text_and_url_both_preserved(self):
        text = "كلمة المرور الخاصة بك  تحتاج إلى تحديث\nانتقل إلى https : // bank.example.com / reset"
        result = _clean(text)
        self.assertIn("كلمة المرور", result)
        self.assertIn("https://bank.example.com/reset", result)

    def test_excess_whitespace_collapsed(self):
        result = _clean("نص   بمسافات   زائدة")
        self.assertNotIn("   ", result)

    def test_excess_newlines_collapsed(self):
        result = _clean("سطر\n\n\n\nآخر")
        self.assertNotIn("\n\n\n", result)


class NormalizeArabicPreservationTests(unittest.TestCase):
    def test_noise_cleanup_does_not_delete_arabic_words(self):
        text = "مرحباً بك في نظام التصيد\n|\n|\nيرجى تسجيل الدخول"
        result = _clean(text)
        self.assertIn("مرحباً بك", result)
        self.assertIn("يرجى تسجيل الدخول", result)

    def test_arabic_with_url_both_survive_full_pipeline(self):
        text = "|\nاضغط هنا للدخول: https://evil.example.com/phish\n|\n|\n"
        result = _clean(text)
        self.assertIn("اضغط هنا للدخول", result)
        self.assertIn("https://evil.example.com/phish", result)


class ExtractUrlsTests(unittest.TestCase):
    def test_extracts_https_url(self):
        urls = extract_urls("click https://phishing.example.com/login to proceed")
        self.assertIn("https://phishing.example.com/login", urls)

    def test_extracts_www_url(self):
        urls = extract_urls("visit www.example.com for details")
        self.assertTrue(any("example.com" in u for u in urls))

    def test_deduplicates_identical_urls(self):
        urls = extract_urls("https://example.com https://example.com")
        self.assertEqual(urls.count("https://example.com"), 1)

    def test_no_urls_returns_empty_list(self):
        urls = extract_urls("هذا نص عربي بدون روابط")
        self.assertEqual(urls, [])


class CleanUrlTests(unittest.TestCase):
    def test_strips_trailing_period(self):
        self.assertEqual(_clean_url("https://example.com."), "https://example.com")

    def test_strips_trailing_comma(self):
        self.assertEqual(_clean_url("https://example.com,"), "https://example.com")

    def test_strips_trailing_arabic_punctuation(self):
        self.assertEqual(_clean_url("https://example.com؟"), "https://example.com")

    def test_strips_leading_bracket(self):
        self.assertEqual(_clean_url("(https://example.com"), "https://example.com")


def _make_valid_png_bytes() -> bytes:
    """Return bytes of a minimal valid 10x10 PNG using PIL."""
    import io as _io
    from PIL import Image as _Image
    buf = _io.BytesIO()
    _Image.new("RGB", (10, 10)).save(buf, format="PNG")
    return buf.getvalue()


class ExtractTextFromImageBytesTests(unittest.TestCase):
    def test_unsupported_content_type_returns_failure(self):
        result = extract_text_from_image_bytes(b"data", content_type="application/pdf")
        self.assertFalse(result.success)
        self.assertIn("Unsupported", result.error)

    def test_oversized_image_returns_failure(self):
        big = b"x" * (6 * 1024 * 1024)
        result = extract_text_from_image_bytes(big, content_type="image/jpeg", max_mb=5)
        self.assertFalse(result.success)
        self.assertIn("too large", result.error)

    def test_invalid_image_bytes_returns_failure_not_crash(self):
        result = extract_text_from_image_bytes(b"not-an-image", content_type="image/jpeg")
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    def test_empty_content_type_returns_failure(self):
        result = extract_text_from_image_bytes(b"data", content_type="")
        self.assertFalse(result.success)

    def test_result_fields_present_on_failure(self):
        result = extract_text_from_image_bytes(b"data", content_type="text/plain")
        self.assertEqual(result.extracted_text, "")
        self.assertEqual(result.normalized_text, "")
        self.assertEqual(result.extracted_urls, [])

    def test_text_plain_rejected_with_unsupported_error(self):
        result = extract_text_from_image_bytes(b"hello world", content_type="text/plain")
        self.assertFalse(result.success)
        self.assertIn("Unsupported", result.error)

    def test_octet_stream_invalid_bytes_returns_failure(self):
        result = extract_text_from_image_bytes(b"not-an-image", content_type="application/octet-stream")
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    def test_octet_stream_valid_png_not_rejected_as_unsupported(self):
        """octet-stream with real PNG bytes must not be rejected with 'Unsupported'."""
        try:
            valid_png = _make_valid_png_bytes()
        except Exception:
            self.skipTest("PIL not available for generating test image")
        result = extract_text_from_image_bytes(valid_png, content_type="application/octet-stream")
        # May fail due to missing Tesseract, but NOT because of unsupported type
        if not result.success:
            self.assertNotIn("Unsupported", result.error or "")

    def test_image_jpeg_content_type_accepted(self):
        result = extract_text_from_image_bytes(b"fake", content_type="image/jpeg")
        self.assertFalse(result.success)
        self.assertNotIn("Unsupported", result.error or "")

    def test_image_jpg_alias_accepted(self):
        result = extract_text_from_image_bytes(b"fake", content_type="image/jpg")
        self.assertFalse(result.success)
        self.assertNotIn("Unsupported", result.error or "")

    def test_image_png_content_type_accepted(self):
        result = extract_text_from_image_bytes(b"fake", content_type="image/png")
        self.assertFalse(result.success)
        self.assertNotIn("Unsupported", result.error or "")


class TesseractAvailabilityTests(unittest.TestCase):
    def test_is_tesseract_available_returns_bool(self):
        result = is_tesseract_available()
        self.assertIsInstance(result, bool)

    def test_is_tesseract_available_does_not_raise(self):
        try:
            is_tesseract_available()
        except Exception as exc:
            self.fail(f"is_tesseract_available() raised unexpectedly: {exc}")


class PaddleOcrParserTests(unittest.TestCase):
    """Tests for _parse_paddle_result — uses mock data, no real PaddleOCR needed."""

    def _make_result(self, lines):
        return [lines]

    def test_empty_result_returns_empty_string(self):
        self.assertEqual(_parse_paddle_result([]), "")
        self.assertEqual(_parse_paddle_result(None), "")

    def test_none_page_returns_empty_string(self):
        self.assertEqual(_parse_paddle_result([None]), "")

    def test_arabic_text_preserved(self):
        result = self._make_result([
            [[[0, 0], [100, 0], [100, 20], [0, 20]], ("مرحبا بكم", 0.99)],
        ])
        text = _parse_paddle_result(result)
        self.assertIn("مرحبا بكم", text)

    def test_multiple_lines_joined(self):
        result = self._make_result([
            [[[0, 0], [100, 0], [100, 20], [0, 20]], ("السطر الأول", 0.99)],
            [[[0, 25], [100, 25], [100, 45], [0, 45]], ("السطر الثاني", 0.95)],
        ])
        text = _parse_paddle_result(result)
        self.assertIn("السطر الأول", text)
        self.assertIn("السطر الثاني", text)

    def test_lines_sorted_top_to_bottom(self):
        """Line at lower y-coordinate (top) must appear first in output."""
        result = self._make_result([
            [[[0, 80], [100, 80], [100, 100], [0, 100]], ("الثانية", 0.99)],
            [[[0, 10], [100, 10], [100, 30], [0, 30]], ("الأولى", 0.99)],
        ])
        text = _parse_paddle_result(result)
        lines = [ln for ln in text.split("\n") if ln.strip()]
        self.assertEqual(lines[0], "الأولى")
        self.assertEqual(lines[1], "الثانية")

    def test_blank_lines_skipped(self):
        result = self._make_result([
            [[[0, 0], [100, 0], [100, 20], [0, 20]], ("   ", 0.10)],
            [[[0, 25], [100, 25], [100, 45], [0, 45]], ("نص", 0.95)],
        ])
        text = _parse_paddle_result(result)
        lines = [ln for ln in text.split("\n") if ln.strip()]
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], "نص")

    def test_url_line_preserved(self):
        result = self._make_result([
            [[[0, 0], [200, 0], [200, 20], [0, 20]], ("https://example.com/login", 0.98)],
        ])
        text = _parse_paddle_result(result)
        self.assertIn("https://example.com/login", text)

    def test_mixed_arabic_and_url(self):
        result = self._make_result([
            [[[0, 0], [200, 0], [200, 20], [0, 20]], ("انقر على الرابط:", 0.97)],
            [[[0, 25], [200, 25], [200, 45], [0, 45]], ("https://phish.example.com", 0.96)],
        ])
        text = _parse_paddle_result(result)
        self.assertIn("انقر على الرابط", text)
        self.assertIn("https://phish.example.com", text)


# ── Microservice availability tests ──────────────────────────────────────────

class MicroserviceAvailabilityTests(unittest.TestCase):
    def test_empty_url_returns_false(self):
        self.assertFalse(is_paddle_microservice_available(""))

    def test_available_when_health_returns_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("httpx.Client") as mc:
            mc.return_value.__enter__.return_value.get.return_value = mock_resp
            self.assertTrue(is_paddle_microservice_available("http://ocr_service:9000/ocr"))

    def test_unavailable_when_connection_refused(self):
        with patch("httpx.Client") as mc:
            mc.return_value.__enter__.return_value.get.side_effect = Exception("Connection refused")
            self.assertFalse(is_paddle_microservice_available("http://ocr_service:9000/ocr"))

    def test_unavailable_when_health_returns_non_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        with patch("httpx.Client") as mc:
            mc.return_value.__enter__.return_value.get.return_value = mock_resp
            self.assertFalse(is_paddle_microservice_available("http://ocr_service:9000/ocr"))

    def test_does_not_raise_on_any_exception(self):
        with patch("httpx.Client") as mc:
            mc.return_value.__enter__.side_effect = RuntimeError("unexpected")
            try:
                result = is_paddle_microservice_available("http://ocr_service:9000/ocr")
                self.assertFalse(result)
            except Exception as exc:
                self.fail(f"is_paddle_microservice_available raised: {exc}")


# ── Microservice call tests ───────────────────────────────────────────────────

_SVC_URL = "http://ocr_service:9000/ocr"


class MicroserviceCallTests(unittest.TestCase):
    def _mock_200(self, text="مرحبا\nhttps://example.com", success=True):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "success": success,
            "engine": "paddleocr",
            "text": text,
            "lines": text.split("\n") if text else [],
            "error": None if success else "OCR failed",
        }
        return resp

    def test_successful_response_returns_success(self):
        with patch("httpx.Client") as mc:
            mc.return_value.__enter__.return_value.post.return_value = self._mock_200()
            result = _call_paddle_microservice(b"fake", "image/jpeg", _SVC_URL, 20, "ara+eng")
        self.assertTrue(result.success)
        self.assertEqual(result.engine, "paddle")
        self.assertIn("مرحبا", result.extracted_text)

    def test_urls_extracted_from_microservice_text(self):
        with patch("httpx.Client") as mc:
            mc.return_value.__enter__.return_value.post.return_value = self._mock_200(
                text="تحقق من https://phishing.example.com/login"
            )
            result = _call_paddle_microservice(b"fake", "image/jpeg", _SVC_URL, 20, "ara+eng")
        self.assertTrue(result.success)
        self.assertIn("https://phishing.example.com/login", result.extracted_urls)

    def test_connection_error_returns_failure(self):
        with patch("httpx.Client") as mc:
            mc.return_value.__enter__.return_value.post.side_effect = Exception("Connection refused")
            result = _call_paddle_microservice(b"fake", "image/jpeg", _SVC_URL, 20, "ara+eng")
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.engine, "paddle")

    def test_http_500_returns_failure(self):
        resp = MagicMock()
        resp.status_code = 500
        with patch("httpx.Client") as mc:
            mc.return_value.__enter__.return_value.post.return_value = resp
            result = _call_paddle_microservice(b"fake", "image/jpeg", _SVC_URL, 20, "ara+eng")
        self.assertFalse(result.success)
        self.assertIn("500", result.error or "")

    def test_service_returns_success_false_propagates(self):
        with patch("httpx.Client") as mc:
            mc.return_value.__enter__.return_value.post.return_value = self._mock_200(success=False)
            result = _call_paddle_microservice(b"fake", "image/jpeg", _SVC_URL, 20, "ara+eng")
        self.assertFalse(result.success)

    def test_text_cleaning_applied_to_microservice_output(self):
        """URL repair and garbage removal run on the microservice text."""
        with patch("httpx.Client") as mc:
            mc.return_value.__enter__.return_value.post.return_value = self._mock_200(
                text="زيارة http : // bank.example.com / verify"
            )
            result = _call_paddle_microservice(b"fake", "image/jpeg", _SVC_URL, 20, "ara+eng")
        self.assertTrue(result.success)
        self.assertIn("http://bank.example.com/verify", result.normalized_text)


# ── Engine routing tests (with microservice) ──────────────────────────────────

class EngineRoutingTests(unittest.TestCase):
    def _mock_svc_success(self, text="نص عربي"):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"success": True, "engine": "paddleocr", "text": text, "lines": [text], "error": None}
        return resp

    def test_auto_no_url_no_tesseract_returns_no_engine(self):
        """auto with no microservice URL and no Tesseract → 'No OCR engine' error."""
        with patch("app.services.image_ocr_service._TESSERACT_AVAILABLE", False):
            result = extract_text_from_image_bytes(
                b"x", content_type="image/jpeg", engine="auto", paddle_service_url=""
            )
        self.assertFalse(result.success)
        self.assertIn("No OCR engine", result.error or "")

    def test_auto_with_url_calls_microservice_on_success(self):
        with patch("httpx.Client") as mc:
            mc.return_value.__enter__.return_value.post.return_value = self._mock_svc_success()
            result = extract_text_from_image_bytes(
                b"x", content_type="image/jpeg", engine="auto", paddle_service_url=_SVC_URL
            )
        self.assertTrue(result.success)
        self.assertEqual(result.engine, "paddle")

    def test_auto_microservice_failure_falls_back_to_tesseract(self):
        """auto: microservice timeout → falls back to Tesseract (fails on bad bytes, not engine)."""
        with patch("httpx.Client") as mc, \
             patch("app.services.image_ocr_service._TESSERACT_AVAILABLE", True):
            mc.return_value.__enter__.return_value.post.side_effect = Exception("timeout")
            result = extract_text_from_image_bytes(
                b"not-an-image", content_type="image/jpeg", engine="auto",
                paddle_service_url=_SVC_URL
            )
        self.assertFalse(result.success)
        # Must NOT say "No OCR engine" — Tesseract path was entered (failed on bad bytes)
        self.assertNotIn("No OCR engine", result.error or "")
        self.assertEqual(result.engine, "tesseract")

    def test_auto_result_engine_is_paddle_when_microservice_succeeds(self):
        with patch("httpx.Client") as mc:
            mc.return_value.__enter__.return_value.post.return_value = self._mock_svc_success()
            result = extract_text_from_image_bytes(
                b"x", content_type="image/jpeg", engine="auto", paddle_service_url=_SVC_URL
            )
        self.assertEqual(result.engine, "paddle")

    def test_explicit_paddle_no_url_returns_configuration_error(self):
        result = extract_text_from_image_bytes(
            b"x", content_type="image/jpeg", engine="paddle", paddle_service_url=""
        )
        self.assertFalse(result.success)
        self.assertIn("not configured", result.error or "")

    def test_explicit_paddle_microservice_no_url_returns_configuration_error(self):
        result = extract_text_from_image_bytes(
            b"x", content_type="image/jpeg", engine="paddle_microservice", paddle_service_url=""
        )
        self.assertFalse(result.success)
        self.assertIn("not configured", result.error or "")

    def test_explicit_tesseract_no_tesseract_returns_failure(self):
        with patch("app.services.image_ocr_service._TESSERACT_AVAILABLE", False):
            result = extract_text_from_image_bytes(
                b"x", content_type="image/jpeg", engine="tesseract"
            )
        self.assertFalse(result.success)
        self.assertNotIn("PaddleOCR", result.error or "")

    def test_explicit_tesseract_uses_tesseract_not_microservice(self):
        """engine=tesseract must NOT call the microservice even if URL is set."""
        with patch("app.services.image_ocr_service._TESSERACT_AVAILABLE", True), \
             patch("app.services.image_ocr_service._run_tesseract_ocr") as mock_tess:
            mock_tess.return_value = MagicMock(success=True, engine="tesseract",
                                               extracted_text="", normalized_text="",
                                               extracted_urls=[], error=None)
            extract_text_from_image_bytes(
                b"x", content_type="image/jpeg", engine="tesseract", paddle_service_url=_SVC_URL
            )
            mock_tess.assert_called_once()


if __name__ == "__main__":
    unittest.main()
