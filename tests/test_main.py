import pytest
from unittest import mock
import sys
import os
import threading

# Add parent directory to Python path so that "main.py" can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main

@pytest.fixture(scope="module", autouse=True)
def mock_pymcprotocol_fixture():
    with mock.patch("main.initialize_connection") as MockInitializeConnection:
        mock_pymc3e_instance = MockInitializeConnection.return_value
        # Mock the connection and any other method you expect to be called
        mock_pymc3e_instance.batchwrite_wordunits.return_value = None
        mock_pymc3e_instance.batchwrite_bitunits.return_value = None
        yield mock_pymc3e_instance

@pytest.fixture
def pymc3e_fixture(mock_pymcprotocol_fixture):
    return mock_pymcprotocol_fixture

@pytest.fixture
def serial_mock():
    serial_instance = mock.Mock()
    serial_instance.in_waiting = 10  # Simulate available bytes
    serial_instance.read.return_value = b'ST,+0001234g\r\n'  # Example weight data
    return serial_instance

def test_process_serial_data(serial_mock, pymc3e_fixture, monkeypatch):
    # Mock the utility function for splitting values
    monkeypatch.setattr(main.utility, "split_32bit_to_16bit", lambda x: [x // 2, x // 2])

    # Create a stop event for threading
    stop_event = threading.Event()

    # Call the function under test with the required stop_event
    main.process_serial_data(serial_mock, "D6364", "M3300", pymc3e_fixture, stop_event)

    # Assertions to verify the expected calls
    pymc3e_fixture.batchwrite_wordunits.assert_called_with(headdevice="D6364", values=[617, 617])
    pymc3e_fixture.batchwrite_bitunits.assert_any_call(headdevice="M3300", values=[1])
    pymc3e_fixture.batchwrite_bitunits.assert_any_call(headdevice="M3300", values=[0])

def test_main_loop(serial_mock, monkeypatch):
    # Mock the serial connections initializer
    monkeypatch.setattr(main.utility, "initialize_serial_connections", mock.Mock())
    monkeypatch.setattr(main, "process_serial_data", mock.Mock())

    # Mock the port_to_headdevice_and_bitunit dictionary
    mock_port_to_headdevice_and_bitunit = {
        "/dev/ttyUSB0": ("D6364", "M3300"),
    }
    
    # Set the mock dictionary in the main module
    monkeypatch.setattr(main, "port_to_headdevice_and_bitunit", mock_port_to_headdevice_and_bitunit)

    # Replace the main loop logic with a controlled execution for the test
    def mock_main(pymc3e):
        stop_event = threading.Event()  # Create a stop event
        for port, (headdevice, bitunit) in mock_port_to_headdevice_and_bitunit.items():
            ser = serial_mock
            main.process_serial_data(ser, headdevice, bitunit, pymc3e, stop_event)

    # Mock the infinite loop in main.main
    with mock.patch('main.main', side_effect=mock_main) as mock_main_function:
        mock_main_function(pymc3e_fixture)

    # Verify that process_serial_data was called correctly
    main.process_serial_data.assert_called_with(serial_mock, "D6364", "M3300", pymc3e_fixture, mock.ANY)

