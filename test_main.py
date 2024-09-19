import unittest
from unittest.mock import MagicMock, patch, call
import logging
from io import StringIO
import pymcprotocol
import utility
import sys
import your_module  # Replace this with the actual name of the module containing your code

class TestSerialPLCIntegration(unittest.TestCase):

    @patch('pymcprotocol.Type3E')  # Mock pymcprotocol Type3E PLC connection
    @patch('serial.Serial')  # Mock the serial connection
    def test_process_serial_data(self, mock_serial, mock_plc):
        # Setup the mock PLC
        mock_plc_instance = mock_plc.return_value
        mock_plc_instance.batchwrite_wordunits.return_value = None
        mock_plc_instance.batchwrite_bitunits.return_value = None

        # Mock serial data
        mock_serial_instance = mock_serial.return_value
        mock_serial_instance.in_waiting = 10
        mock_serial_instance.read.return_value = b'ST,+00123g\r\n'

        # Setup logger to capture output
        log_stream = StringIO()
        logging.basicConfig(stream=log_stream, level=logging.INFO)

        # Mock utility.split_32bit_to_16bit function
        with patch('utility.split_32bit_to_16bit') as mock_split:
            mock_split.return_value = [12, 34]  # Mock the split result
            
            # Call the function to process the serial data
            your_module.process_serial_data(mock_serial_instance, 'D6364', 'M3300')

            # Assert that the PLC was written with correct values
            mock_plc_instance.batchwrite_wordunits.assert_called_with(headdevice='D6364', values=[12, 34])
            mock_plc_instance.batchwrite_bitunits.assert_has_calls([call(headdevice='M3300', values=[1]),
                                                                    call(headdevice='M3300', values=[0])])
            
            # Check if the logging captured the correct output
            log_output = log_stream.getvalue()
            self.assertIn("Received weight data: ST,+00123g", log_output)
            self.assertIn("Target value: 1230", log_output)  # 123g * 10 = 1230

    @patch('pymcprotocol.Type3E')  # Mock pymcprotocol Type3E PLC connection
    @patch('utility.initialize_serial_connections')  # Mock utility function
    def test_main(self, mock_initialize_serial_connections, mock_plc):
        # Mock PLC and serial ports
        mock_plc_instance = mock_plc.return_value
        mock_initialize_serial_connections.return_value = None

        # Setup the mock serial ports
        serial_ports = {
            "/dev/ttyUSB0": MagicMock(),
        }

        with patch('your_module.serial_ports', serial_ports):
            with patch('your_module.process_serial_data') as mock_process_serial_data:
                # Mock serial processing function to avoid infinite loop
                mock_process_serial_data.side_effect = KeyboardInterrupt  # Stop after first call

                # Run the main function and check if it works
                try:
                    your_module.main()
                except KeyboardInterrupt:
                    pass  # Expecting this to exit the loop

                # Verify process_serial_data was called
                mock_process_serial_data.assert_called_with(serial_ports["/dev/ttyUSB0"], 'D6364', 'M3300')

    # Additional tests can be added for edge cases, error handling, etc.

if __name__ == "__main__":
    unittest.main()
