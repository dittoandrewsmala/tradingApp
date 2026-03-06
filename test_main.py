import unittest
from unittest.mock import Mock, patch
import sys
import os

# Add the current directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(__file__))

from main import on_tick

class TestMain(unittest.TestCase):

    def setUp(self):
        # Reset global variables before each test
        import main
        main.lotIndex = 0
        main.isTradeActive = False
        main.signalStarted = False
        main.isProfitable = False

    @patch('main.strategy')
    @patch('main.position')
    @patch('main.trade')
    def test_on_tick_no_signal_no_profit(self, mock_trade, mock_position, mock_strategy):
        # Arrange
        mock_strategy.signal.return_value = None
        mock_position.get_positions.return_value = False  # Not profitable

        # Act
        on_tick(100.0)

        # Assert
        mock_strategy.signal.assert_called_once_with(100.0)
        mock_position.get_positions.assert_called_once()
        mock_trade.on_signal.assert_not_called()
        # Check that lotIndex is reset
        import main
        self.assertEqual(main.lotIndex, 0)

    @patch('main.strategy')
    @patch('main.position')
    @patch('main.trade')
    def test_on_tick_signal_not_profitable_first_time(self, mock_trade, mock_position, mock_strategy):
        # Arrange
        mock_strategy.signal.return_value = "BUY"
        mock_position.get_positions.return_value = False  # Not profitable

        # Act
        on_tick(100.0)

        # Assert
        mock_strategy.signal.assert_called_once_with(100.0)
        mock_position.get_positions.assert_called_once()
        mock_trade.on_signal.assert_called_once_with("BUY", 100.0, 1)  # lotnumbers[0] = 1
        import main
        self.assertEqual(main.lotIndex, 0)
        self.assertTrue(main.signalStarted)

    @patch('main.strategy')
    @patch('main.position')
    @patch('main.trade')
    def test_on_tick_signal_not_profitable_subsequent(self, mock_trade, mock_position, mock_strategy):
        # Arrange
        import main
        main.signalStarted = True
        main.lotIndex = 0
        mock_strategy.signal.return_value = "BUY"
        mock_position.get_positions.return_value = False  # Not profitable

        # Act
        on_tick(100.0)

        # Assert
        mock_strategy.signal.assert_called_once_with(100.0)
        mock_position.get_positions.assert_called_once()
        mock_trade.on_signal.assert_called_once_with("BUY", 100.0, 2)  # lotnumbers[1] = 2
        self.assertEqual(main.lotIndex, 1)

    @patch('main.strategy')
    @patch('main.position')
    @patch('main.trade')
    def test_on_tick_no_signal_profitable(self, mock_trade, mock_position, mock_strategy):
        # Arrange
        mock_strategy.signal.return_value = None
        mock_position.get_positions.return_value = True  # Profitable

        # Act
        on_tick(100.0)

        # Assert
        mock_strategy.signal.assert_called_once_with(100.0)
        mock_position.get_positions.assert_called_once()
        mock_trade.on_signal.assert_not_called()
        import main
        self.assertEqual(main.lotIndex, 0)

if __name__ == '__main__':
    unittest.main()</content>
<parameter name="filePath">d:\flat_trade\tradingApp\test_main.py