"""Tests for backend/drive.py -- Drive link resolution and file export."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from drive import (
    extract_drive_id,
    resolve_drive_link,
    list_folder_files,
    export_file,
    classify_file,
    SUPPORTED_MIME_TYPES,
    SKIP_REASONS,
    EXPORT_MIME_MAP,
)


# --- extract_drive_id ---


class TestExtractDriveId:
    def test_folder_url(self):
        url = "https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz"
        assert extract_drive_id(url) == "1AbCdEfGhIjKlMnOpQrStUvWxYz"

    def test_file_url(self):
        url = "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUvWxYz/view"
        assert extract_drive_id(url) == "1AbCdEfGhIjKlMnOpQrStUvWxYz"

    def test_open_url(self):
        url = "https://drive.google.com/open?id=1AbCdEfGhIjKlMnOpQrStUvWxYz"
        assert extract_drive_id(url) == "1AbCdEfGhIjKlMnOpQrStUvWxYz"

    def test_invalid_url_returns_none(self):
        assert extract_drive_id("https://example.com") is None

    def test_short_string_returns_none(self):
        assert extract_drive_id("abc") is None

    def test_empty_string_returns_none(self):
        assert extract_drive_id("") is None


# --- resolve_drive_link ---


class TestResolveDriveLink:
    @pytest.mark.asyncio
    async def test_returns_file_metadata(self):
        mock_data = {"id": "abc123", "name": "doc.pdf", "mimeType": "application/pdf", "size": "1024"}
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_data)
        mock_resp.raise_for_status = MagicMock()
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("drive.drive_session", return_value=mock_session):
            result = await resolve_drive_link("fake-token", "abc123")
            assert result == mock_data

    @pytest.mark.asyncio
    async def test_raises_value_error_on_404(self):
        mock_resp = AsyncMock()
        mock_resp.status = 404
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("drive.drive_session", return_value=mock_session):
            with pytest.raises(ValueError, match="not found"):
                await resolve_drive_link("fake-token", "bad-id")

    @pytest.mark.asyncio
    async def test_raises_permission_error_on_403(self):
        mock_resp = AsyncMock()
        mock_resp.status = 403
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("drive.drive_session", return_value=mock_session):
            with pytest.raises(PermissionError, match="No access"):
                await resolve_drive_link("fake-token", "no-access-id")


# --- list_folder_files ---


class TestListFolderFiles:
    @pytest.mark.asyncio
    async def test_returns_files_with_pagination(self):
        """Test that pagination works -- 2 pages of results."""
        page1 = {
            "files": [{"id": "f1", "name": "a.pdf", "mimeType": "application/pdf", "size": "100"}],
            "nextPageToken": "token2",
        }
        page2 = {
            "files": [{"id": "f2", "name": "b.txt", "mimeType": "text/plain", "size": "50"}],
        }

        call_count = 0

        async def mock_json():
            nonlocal call_count
            call_count += 1
            return page1 if call_count == 1 else page2

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = mock_json
        mock_resp.raise_for_status = MagicMock()
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("drive.drive_session", return_value=mock_session):
            result = await list_folder_files("fake-token", "folder-id")
            assert len(result) == 2
            assert result[0]["id"] == "f1"
            assert result[1]["id"] == "f2"


# --- export_file ---


class TestExportFile:
    @pytest.mark.asyncio
    async def test_export_google_doc_uses_export_endpoint(self):
        """Google Workspace types use /export endpoint."""
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.read = AsyncMock(return_value=b"doc content")
        mock_resp.raise_for_status = MagicMock()
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("drive.drive_session", return_value=mock_session):
            result = await export_file("fake-token", "doc-id", "application/vnd.google-apps.document")
            assert result == b"doc content"
            # Verify the URL used /export
            call_args = mock_session.get.call_args
            assert "/export" in call_args[0][0]
            assert call_args[1]["params"]["mimeType"] == "text/plain"

    @pytest.mark.asyncio
    async def test_export_pdf_uses_alt_media(self):
        """Binary types use ?alt=media."""
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.read = AsyncMock(return_value=b"%PDF-1.4 content")
        mock_resp.raise_for_status = MagicMock()
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("drive.drive_session", return_value=mock_session):
            result = await export_file("fake-token", "pdf-id", "application/pdf")
            assert result == b"%PDF-1.4 content"
            call_args = mock_session.get.call_args
            assert "/export" not in call_args[0][0]
            assert call_args[1]["params"]["alt"] == "media"


# --- SUPPORTED_MIME_TYPES ---


class TestSupportedMimeTypes:
    def test_contains_all_six_types(self):
        expected = {
            "application/vnd.google-apps.document",
            "application/vnd.google-apps.spreadsheet",
            "application/vnd.google-apps.presentation",
            "application/pdf",
            "text/plain",
            "text/markdown",
        }
        assert SUPPORTED_MIME_TYPES == expected


# --- classify_file / is_supported ---


class TestClassifyFile:
    def test_supported_type_returns_supported(self):
        result = classify_file("application/pdf")
        assert result["supported"] is True
        assert result["reason"] is None

    def test_image_returns_unsupported_with_reason(self):
        result = classify_file("image/png")
        assert result["supported"] is False
        assert "Image" in result["reason"]

    def test_video_returns_unsupported_with_reason(self):
        result = classify_file("video/mp4")
        assert result["supported"] is False
        assert "Video" in result["reason"]

    def test_zip_returns_unsupported_with_reason(self):
        result = classify_file("application/zip")
        assert result["supported"] is False
        assert "ZIP" in result["reason"]

    def test_unknown_type_returns_unsupported(self):
        result = classify_file("application/octet-stream")
        assert result["supported"] is False
        assert result["reason"] is not None
