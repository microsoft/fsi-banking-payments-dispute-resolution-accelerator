from __future__ import annotations

from unittest.mock import MagicMock, patch

from triggers.pl_ingest_raw import (
    _handle_ingest_blob_event,
    _parse_network_file,
    _parse_records_from_payload,
    intake_dispute_record,
)


_STANDARD_RECORD = {
    "networkCode": "visa",
    "reasonCode": "13.1",
    "cardholderName": "Jane Doe",
    "cardLastFour": "4242",
    "transactionAmount": "99.99",
    "transactionDate": "2026-07-01T00:00:00Z",
    "merchantName": "Acme",
    "metadata": {"externalDisputeId": "visa-123"},
}


class TestIntakeDisputeRecord:
    def test_creates_case_compatible_dispute_and_starts_orchestration(self):
        with (
            patch("triggers.pl_ingest_raw.cosmos_client") as mock_cosmos,
            patch("triggers.pl_ingest_raw.start_dispute_orchestration", return_value="started") as mock_start,
        ):
            mock_cosmos.query_disputes.return_value = []
            mock_cosmos.create_dispute.side_effect = lambda dispute: dispute

            result = intake_dispute_record(_STANDARD_RECORD, source_system="processor_webhook")

        assert result["outcome"] == "created"
        created_doc = mock_cosmos.create_dispute.call_args[0][0]
        assert created_doc["status"] == "intake"
        assert created_doc["caseId"] == created_doc["disputeId"]
        assert created_doc["cardNetwork"] == "visa"
        assert created_doc["metadata"]["dedupeKey"]
        # 4 timeline events: case_created, ingest status_change,
        # triage score_generated, and orchestration start.
        assert mock_cosmos.create_timeline_event.call_count == 4
        mock_start.assert_called_once_with(created_doc["disputeId"])

    def test_duplicate_detection_skips_insert(self):
        existing = {"disputeId": "dup-1", "networkCode": "visa", "status": "intake"}
        with patch("triggers.pl_ingest_raw.cosmos_client") as mock_cosmos:
            mock_cosmos.query_disputes.return_value = [existing]

            result = intake_dispute_record(_STANDARD_RECORD, source_system="processor_webhook")

        assert result["outcome"] == "duplicate"
        assert result["disputeId"] == "dup-1"
        mock_cosmos.create_dispute.assert_not_called()

    def test_invalid_record_returns_missing_fields(self):
        with patch("triggers.pl_ingest_raw.cosmos_client") as mock_cosmos:
            result = intake_dispute_record({"networkCode": "visa"})

        assert result["outcome"] == "invalid"
        assert "reasonCode" in result["missing"]
        mock_cosmos.create_dispute.assert_not_called()


class TestWebhookAndFileParsing:
    def test_nested_webhook_payload_is_unwrapped(self):
        payload = {
            "eventId": "evt-1",
            "sourceSystem": "processor_webhook",
            "dispute": {
                "network": "mastercard",
                "chargebackReasonCode": "4837",
                "card": {"cardholderName": "Alex Doe", "last4": "5454"},
                "transaction": {
                    "amount": "12.50",
                    "currency": "USD",
                    "transactionDate": "2026-07-02T12:00:00Z",
                },
                "merchant": {"name": "Example Shop"},
            },
        }

        records = _parse_records_from_payload(payload)

        assert len(records) == 1
        assert records[0]["sourceSystem"] == "processor_webhook"
        assert records[0]["eventId"] == "evt-1"

    def test_parses_visa_json_network_file(self):
        body_text = """
        {
          "network": "visa",
          "records": [
            {
              "reasonCode": "13.1",
              "cardholderName": "Jane Doe",
              "cardLastFour": "4242",
              "transactionAmount": "99.99",
              "transactionDate": "2026-07-01T00:00:00Z",
              "merchantName": "Acme"
            }
          ]
        }
        """

        records = _parse_network_file("visa-tc40-20260701.json", body_text)

        assert len(records) == 1
        assert records[0]["sourceSystem"] == "visa_file"
        assert records[0]["sourceFile"] == "visa-tc40-20260701.json"

    def test_parses_mastercard_csv_network_file(self):
        body_text = (
            "chargebackReasonCode,cardholderName,panLast4,chargebackAmount,chargebackDate,merchantName\n"
            "4837,Alex Doe,5454,12.50,2026-07-02T12:00:00Z,Example Shop\n"
        )

        records = _parse_network_file("mastercard-gcms-20260702.csv", body_text)

        assert len(records) == 1
        assert records[0]["sourceSystem"] == "mastercard_file"
        assert records[0]["panLast4"] == "5454"


class TestEventGridTrigger:
    def test_blob_created_event_downloads_and_processes_file(self):
        event_data = {
            "url": "https://acct.blob.core.windows.net/ingest/visa-tc40-20260701.json"
        }

        with (
            patch("triggers.pl_ingest_raw._download_blob_text", return_value=("visa.json", "{}")) as mock_download,
            patch("triggers.pl_ingest_raw._parse_network_file", return_value=[_STANDARD_RECORD]) as mock_parse,
            patch("triggers.pl_ingest_raw._process_records", return_value={"ingested": 1, "duplicates": 0, "skipped": 0}) as mock_process,
        ):
            _handle_ingest_blob_event(event_data)

        mock_download.assert_called_once()
        mock_parse.assert_called_once_with("visa.json", "{}")
        mock_process.assert_called_once()
