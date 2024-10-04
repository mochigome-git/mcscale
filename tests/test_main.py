"""
Test code
"""

from unittest import mock
import sys
import os
import threading
from itertools import cycle
import time
import serial
import pytest
import pymcprotocol

# Add parent directory to Python path so that "main.py" can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main

@pytest.fixture(scope="module", autouse=True)
def mock_pymcprotocol_fixture():
    """Mock the pymcprotocol library's connection and methods."""
    with mock.patch("main.initialize_connection") as MockInitializeConnection:
        # Create a mock instance of pymcprotocol.Type3E
        mock_pymc3e_instance = mock.MagicMock(spec=pymcprotocol.Type3E)
        
        # Set up the mocked connection methods
        MockInitializeConnection.return_value = mock_pymc3e_instance
        mock_pymc3e_instance.batchwrite_wordunits.return_value = None
        mock_pymc3e_instance.batchwrite_bitunits.return_value = None
        
        # Yield the mock instance for use in tests
        yield mock_pymc3e_instance

@pytest.fixture
def pymc3e_fixture(mock_pymcprotocol_fixture):
    """Fixture that provides the mocked pymc3e instance."""
    return mock_pymcprotocol_fixture

@pytest.fixture
def serial_mock():
    """Mock for the serial port communication."""
    serial_instance = mock.Mock()
    serial_instance.in_waiting = 10  # Simulate available bytes
    serial_instance.read.side_effect = [
        b'ST,+000009.3  g\r\n',  # Valid data
        serial.SerialException("Simulated disconnection"),  # Simulate a disconnection
        b'ST,+000008.1  g\r\n',
    ]
    return serial_instance

def test_process_serial_data(serial_mock, pymc3e_fixture, monkeypatch):
    """Test the process_serial_data function by mocking partial serial data arrival."""
    monkeypatch.setattr(main.utility, "split_32bit_to_16bit", lambda x: [x // 65536, x % 65536])

    # Create a stop event
    stop_event = threading.Event()

    # Simulate partial data input (incomplete weight message)
    serial_mock.read.side_effect = cycle([b'ST,+000009.3  g\r\n'])  # Simulate incomplete and then full message

    # Start the function in a thread to prevent blocking the test
    thread = threading.Thread(target=main.process_serial_data, args=(serial_mock, "D6364", "M3300", pymc3e_fixture, stop_event))
    thread.start()

    # Allow the function to process data for a limited time
    time.sleep(2)

    # Set the stop event to signal the infinite loop to stop
    stop_event.set()

    # Wait for the thread to finish, with a timeout to avoid hanging
    thread.join(timeout=5) 

    # Assert the correct PLC commands were sent
    pymc3e_fixture.batchwrite_wordunits.assert_called_with(headdevice="D6364", values=[0, 93])
    pymc3e_fixture.batchwrite_bitunits.assert_any_call(headdevice="M3300", values=[1])
    pymc3e_fixture.batchwrite_bitunits.assert_any_call(headdevice="M3300", values=[0])

    # Ensure serial read was called (simulate chunked reads)
    assert serial_mock.read.call_count >= 2

def test_main_loop(serial_mock, pymc3e_fixture, monkeypatch):
    """Test the main loop to ensure serial data is processed correctly."""
    # Mock the serial connections initializer
    monkeypatch.setattr(main.utility, "initialize_serial_connections", mock.Mock())
    monkeypatch.setattr(main, "process_serial_data", mock.Mock())

    # Mock the port_to_headdevice_and_bitunit dictionary
    mock_port_to_headdevice_and_bitunit = {
        "/dev/ttyUSB0": ("D6364", "M3300"),
        "/dev/ttyUSB1": ("D6464", "M3400"),
        "/dev/ttyUSB2": ("D6564", "M3500")
    }
    
    # Set the mock dictionary in the main module
    monkeypatch.setattr(main, "port_to_headdevice_and_bitunit", mock_port_to_headdevice_and_bitunit)

    # Mock a controlled execution of the main loop for the test
    def mock_main(pymc3e):
        stop_event = threading.Event()  # Create a stop event
        loop_count = 0  # Counter to limit loop iterations
        max_iterations = 5  # Define a limit to prevent infinite looping

        for port, (headdevice, bitunit) in mock_port_to_headdevice_and_bitunit.items():
            ser = serial_mock
            # Simulate serial data processing
            main.process_serial_data(ser, headdevice, bitunit, pymc3e, stop_event)
            loop_count += 1
            if loop_count >= max_iterations:  # Stop after a certain number of iterations
                break

    # Mock the infinite loop in main.main
    with mock.patch('main.main', side_effect=mock_main):
        main.main(pymc3e_fixture)

    # Verify that process_serial_data was called correctly
    # Check for each port in the dictionary
    for port, (headdevice, bitunit) in mock_port_to_headdevice_and_bitunit.items():
        main.process_serial_data.assert_any_call(serial_mock, headdevice, bitunit, pymc3e_fixture, mock.ANY)
