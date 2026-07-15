"""Unit tests for helper module."""

import pytest
from unittest.mock import Mock, patch, mock_open
from datetime import datetime, date, timedelta
from pathlib import Path
import tempfile
import os
from freezegun import freeze_time

from quant_toolkit.helper import (
    data_batches,
    convert_symbol_to_ticker, 
    check_last_modified,
    file_mod_recently
)


class TestDataBatches:
    """Test cases for data_batches function."""

    def test_95_day_batch_splitting_default(self):
        """Test that date ranges are split into 95-day chunks by default."""
        start = date(2024, 1, 1)
        end = date(2024, 6, 1)  # ~150 days
        
        batches = data_batches(start, end)
        
        # Should create at least 2 batches for ~150 days
        assert len(batches) >= 2
        
        # Check that batches cover the full range
        assert batches[0]["start"] == "2024-01-01"
        assert batches[-1]["end"] == "2024-06-01"
        
        # Each batch should be roughly 95 days (except potentially the last)
        for i in range(len(batches) - 1):  # All but last batch
            start_dt = datetime.strptime(batches[i]["start"], "%Y-%m-%d").date()
            end_dt = datetime.strptime(batches[i]["end"], "%Y-%m-%d").date()
            batch_size = (end_dt - start_dt).days
            assert batch_size == 95

    def test_batch_custom_size(self):
        """Test custom batch size parameter."""
        start = date(2024, 1, 1)
        end = date(2024, 3, 1)
        custom_batch_size = 30
        
        batches = data_batches(start, end, batch_size=custom_batch_size)
        
        # Should create multiple batches with custom size
        assert len(batches) >= 2
        
        # Check first batch size
        start_dt = datetime.strptime(batches[0]["start"], "%Y-%m-%d").date()
        end_dt = datetime.strptime(batches[0]["end"], "%Y-%m-%d").date()
        batch_size = (end_dt - start_dt).days
        assert batch_size == custom_batch_size

    def test_small_date_range(self):
        """Test behavior with date ranges smaller than batch size."""
        start = date(2024, 1, 1)
        end = date(2024, 1, 30)  # 29 days, less than default 95
        
        batches = data_batches(start, end)
        
        # Should create exactly one batch
        assert len(batches) == 1
        assert batches[0]["start"] == "2024-01-01"
        assert batches[0]["end"] == "2024-01-30"

    def test_large_date_range(self):
        """Test behavior with large date ranges requiring multiple batches."""
        start = date(2023, 1, 1)
        end = date(2024, 1, 1)  # Full year, ~365 days
        
        batches = data_batches(start, end)
        
        # Should create multiple batches for full year
        assert len(batches) >= 3  # At least 3 batches for 365 days
        
        # Verify continuity - end of one batch should connect to start of next
        for i in range(len(batches) - 1):
            current_end = datetime.strptime(batches[i]["end"], "%Y-%m-%d").date()
            next_start = datetime.strptime(batches[i + 1]["start"], "%Y-%m-%d").date()
            # Next batch should start the day after current ends
            assert (next_start - current_end).days == 1

    def test_date_format_handling(self):
        """Test that output format is consistent YYYY-MM-DD."""
        start = date(2024, 1, 5)
        end = date(2024, 2, 10)
        
        batches = data_batches(start, end)
        
        # Verify all dates are in correct format
        for batch in batches:
            # Should be able to parse back to date
            start_parsed = datetime.strptime(batch["start"], "%Y-%m-%d").date()
            end_parsed = datetime.strptime(batch["end"], "%Y-%m-%d").date()
            assert isinstance(start_parsed, date)
            assert isinstance(end_parsed, date)
            assert start_parsed <= end_parsed

    def test_batch_boundary_edge_cases(self):
        """Test edge cases in batch boundary calculations."""
        # Test exact multiple of batch size
        start = date(2024, 1, 1)
        end = date(2024, 4, 5)  # Exactly 95 days from start
        
        batches = data_batches(start, end, batch_size=95)
        
        # Should create exactly one batch when range equals batch size
        assert len(batches) == 1
        assert batches[0]["start"] == "2024-01-01"
        assert batches[0]["end"] == "2024-04-05"

    def test_default_parameters(self):
        """Test function with default parameters."""
        # Test that default parameters work (they use current time when called)
        batches = data_batches()
        
        # Should use default start date (2017-01-01) 
        assert batches[0]["start"] == "2017-01-01"
        
        # End date should be recent (yesterday or today minus 1)
        end_date_str = batches[-1]["end"]
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        # Should be yesterday (the default)
        assert end_date == yesterday
        
        # Should have many batches for such a long range
        assert len(batches) > 20


class TestConvertSymbolToTicker:
    """Test cases for convert_symbol_to_ticker function."""

    @patch('quant_toolkit.helper.MarketContracts')
    def test_futures_symbol_current_month(self, mock_mc_class):
        """Test conversion of current month futures symbols."""
        mock_mc = Mock()
        mock_mc.future.return_value = "NSE:NIFTY24DECFUT"
        mock_mc_class.return_value = mock_mc
        
        result = convert_symbol_to_ticker("NIFTY_FUT", date(2024, 12, 1))
        
        mock_mc.future.assert_called_once_with("NSE", "NIFTY", "current_month", date(2024, 12, 1))
        assert result == "NSE:NIFTY24DECFUT"

    @patch('quant_toolkit.helper.MarketContracts')
    def test_futures_symbol_next_month(self, mock_mc_class):
        """Test conversion of next month futures symbols."""
        mock_mc = Mock()
        mock_mc.future.return_value = "NSE:NIFTY25JANFUT"
        mock_mc_class.return_value = mock_mc
        
        result = convert_symbol_to_ticker("NIFTY_FUT2", date(2024, 12, 1))
        
        mock_mc.future.assert_called_once_with("NSE", "NIFTY", "next_month", date(2024, 12, 1))
        assert result == "NSE:NIFTY25JANFUT"

    @patch('quant_toolkit.helper.MarketContracts')
    def test_custom_exchange(self, mock_mc_class):
        """Test conversion with custom exchange."""
        mock_mc = Mock()
        mock_mc.future.return_value = "BSE:SENSEX24DECFUT"
        mock_mc_class.return_value = mock_mc
        
        result = convert_symbol_to_ticker("SENSEX_FUT", date(2024, 12, 1), "BSE")
        
        mock_mc.future.assert_called_once_with("BSE", "SENSEX", "current_month", date(2024, 12, 1))
        assert result == "BSE:SENSEX24DECFUT"

    def test_non_futures_symbol_unchanged(self):
        """Test that non-futures symbols are returned unchanged."""
        result = convert_symbol_to_ticker("RELIANCE")
        assert result == "RELIANCE"
        
        result = convert_symbol_to_ticker("TCS")
        assert result == "TCS"

    def test_empty_symbol_assertion(self):
        """Test assertion error for empty symbol."""
        with pytest.raises(AssertionError):
            convert_symbol_to_ticker("")
            
        with pytest.raises(AssertionError):
            convert_symbol_to_ticker(None)

    @patch('quant_toolkit.helper.MarketContracts')
    def test_complex_symbol_parsing(self, mock_mc_class):
        """Test parsing of complex symbol names."""
        mock_mc = Mock()
        mock_mc.future.return_value = "NSE:BANKNIFTY24DECFUT"
        mock_mc_class.return_value = mock_mc
        
        # Test symbol with underscores and numbers
        result = convert_symbol_to_ticker("BANK_NIFTY_FUT", date(2024, 12, 1))
        
        mock_mc.future.assert_called_once_with("NSE", "BANK_NIFTY", "current_month", date(2024, 12, 1))


class TestCheckLastModified:
    """Test cases for check_last_modified function."""

    def test_file_older_than_days_int(self):
        """Test file older than specified number of days."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
            
        try:
            # Make file appear 10 days old
            old_time = datetime.now() - timedelta(days=10)
            os.utime(tmp_path, (old_time.timestamp(), old_time.timestamp()))
            
            # Should return True (file is older than 5 days)
            assert check_last_modified(tmp_path, 5) is True
            
            # Should return False (file is not older than 15 days)
            assert check_last_modified(tmp_path, 15) is False
            
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_file_newer_than_days_int(self):
        """Test file newer than specified number of days."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
            
        try:
            # File should be very recent (just created)
            assert check_last_modified(tmp_path, 1) is False
            
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_file_comparison_with_date(self):
        """Test file modification time comparison with date object."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
            
        try:
            # Set file modification time to a specific date
            specific_date = datetime(2024, 1, 15)
            os.utime(tmp_path, (specific_date.timestamp(), specific_date.timestamp()))
            
            # Test with date object
            compare_date = date(2024, 1, 20)  # 5 days later
            assert check_last_modified(tmp_path, compare_date) is True
            
            compare_date = date(2024, 1, 10)  # 5 days earlier
            assert check_last_modified(tmp_path, compare_date) is False
            
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_file_comparison_with_datetime(self):
        """Test file modification time comparison with datetime object."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
            
        try:
            # Set file modification time to a specific datetime
            specific_datetime = datetime(2024, 1, 15, 12, 0, 0)
            os.utime(tmp_path, (specific_datetime.timestamp(), specific_datetime.timestamp()))
            
            # Test with datetime object
            compare_datetime = datetime(2024, 1, 15, 18, 0, 0)  # 6 hours later
            assert check_last_modified(tmp_path, compare_datetime) is True
            
            compare_datetime = datetime(2024, 1, 15, 6, 0, 0)  # 6 hours earlier
            assert check_last_modified(tmp_path, compare_datetime) is False
            
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_nonexistent_file_raises_error(self):
        """Test that FileNotFoundError is raised for nonexistent files."""
        nonexistent_path = Path("/nonexistent/file.txt")
        
        with pytest.raises(FileNotFoundError, match="File not found"):
            check_last_modified(nonexistent_path, 5)

    def test_invalid_days_parameter_raises_error(self):
        """Test that TypeError is raised for invalid days parameter."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
            
        try:
            with pytest.raises(TypeError, match="days parameter must be either"):
                check_last_modified(tmp_path, "invalid")
                
            with pytest.raises(TypeError, match="days parameter must be either"):
                check_last_modified(tmp_path, [1, 2, 3])
                
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_string_path_handling(self):
        """Test that string paths are handled correctly."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path_str = tmp.name
            
        try:
            # Should work with string path
            result = check_last_modified(tmp_path_str, 1)
            assert isinstance(result, bool)
            
        finally:
            Path(tmp_path_str).unlink(missing_ok=True)


class TestFileModRecently:
    """Test cases for file_mod_recently function."""

    def test_file_modified_recently_days_int(self):
        """Test file modified recently with int days parameter."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
            
        try:
            # File just created, should be recent
            assert file_mod_recently(tmp_path, 1) is True
            
            # Make file appear 10 days old
            old_time = datetime.now() - timedelta(days=10)
            os.utime(tmp_path, (old_time.timestamp(), old_time.timestamp()))
            
            # Should return False (file is not recent within 5 days)
            assert file_mod_recently(tmp_path, 5) is False
            
            # Should return True (file is recent within 15 days)
            assert file_mod_recently(tmp_path, 15) is True
            
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_file_modified_recently_date(self):
        """Test file modified recently with date parameter."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
            
        try:
            # Set file modification time to a specific date
            specific_date = datetime(2024, 1, 15)
            os.utime(tmp_path, (specific_date.timestamp(), specific_date.timestamp()))
            
            # Test with date object - file should be after cutoff
            compare_date = date(2024, 1, 10)  # 5 days earlier than file
            assert file_mod_recently(tmp_path, compare_date) is True
            
            # Test with date object - file should be before cutoff
            compare_date = date(2024, 1, 20)  # 5 days later than file
            assert file_mod_recently(tmp_path, compare_date) is False
            
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_file_modified_recently_datetime(self):
        """Test file modified recently with datetime parameter."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
            
        try:
            # Set file modification time to a specific datetime
            specific_datetime = datetime(2024, 1, 15, 12, 0, 0)
            os.utime(tmp_path, (specific_datetime.timestamp(), specific_datetime.timestamp()))
            
            # Test with datetime object - file should be after cutoff
            compare_datetime = datetime(2024, 1, 15, 6, 0, 0)  # 6 hours earlier
            assert file_mod_recently(tmp_path, compare_datetime) is True
            
            # Test with datetime object - file should be before cutoff
            compare_datetime = datetime(2024, 1, 15, 18, 0, 0)  # 6 hours later
            assert file_mod_recently(tmp_path, compare_datetime) is False
            
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_opposite_behavior_of_check_last_modified(self):
        """Test that file_mod_recently is opposite of check_last_modified."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
            
        try:
            # For the same parameters, results should be opposite
            days_param = 5
            
            result_check = check_last_modified(tmp_path, days_param)
            result_recent = file_mod_recently(tmp_path, days_param)
            
            assert result_check != result_recent
            
            # Test with date parameter
            date_param = date(2024, 6, 15)
            result_check_date = check_last_modified(tmp_path, date_param)
            result_recent_date = file_mod_recently(tmp_path, date_param)
            
            assert result_check_date != result_recent_date
            
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_nonexistent_file_raises_error(self):
        """Test that FileNotFoundError is raised for nonexistent files."""
        nonexistent_path = Path("/nonexistent/file.txt")
        
        with pytest.raises(FileNotFoundError, match="File not found"):
            file_mod_recently(nonexistent_path, 5)

    def test_invalid_days_parameter_raises_error(self):
        """Test that TypeError is raised for invalid days parameter."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
            
        try:
            with pytest.raises(TypeError, match="days parameter must be either"):
                file_mod_recently(tmp_path, "invalid")
                
            with pytest.raises(TypeError, match="days parameter must be either"):
                file_mod_recently(tmp_path, {"invalid": "param"})
                
        finally:
            tmp_path.unlink(missing_ok=True)