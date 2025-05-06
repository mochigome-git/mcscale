"""
Test code
"""

from unittest import mock
import sys
import os
import threading
from itertools import cycle
import socket
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
    with mock.patch("main.connect.initialize_connection") as MockInitializeConnection:
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
    return mock.MagicMock(spec=pymcprotocol.Type3E)

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

    stop_event = threading.Event()

    # Simulate byte-by-byte serial data
    test_data = b"ST,+000009.3  g\r\n"
    serial_mock.in_waiting = len(test_data)
    serial_mock.read = mock.MagicMock(return_value=test_data)  # Changed to return full data

    # Minimal logger and shared state
    class DummyLogger:
        def info(self, *args): pass
        def error(self, *args): pass
        def critical(self, *args): pass
        def warning(self, *args): pass 


    state = {
        "buffer": b"",
        "last_weight": 0,
        "last_reset": time.time(),
        "last_update_time": time.time()  # Added to avoid KeyError
    }

    context = {
        "ser": serial_mock,
        "headdevice": "D6364",
        "bitunit": "M3300",
        "pymc3e": pymc3e_fixture,
        "logger": DummyLogger(),
        "state": state,
        "stop_event": stop_event
    }

    # Mocking batchwrite_wordunits to verify it's called
    pymc3e_fixture.batchwrite_wordunits = mock.MagicMock()

    thread = threading.Thread(target=main.process.smode_process_serial_data, args=(context,))
    thread.start()
    time.sleep(2)
    stop_event.set()
    thread.join(timeout=5)

    # Verify that the mocked PLC method was called with expected value
    pymc3e_fixture.batchwrite_wordunits.assert_called_with("D6364", [0, 930])


    # Debugging output
    print("batchwrite_wordunits called:", pymc3e_fixture.batchwrite_wordunits.called)
    print("call arguments:", pymc3e_fixture.batchwrite_wordunits.call_args_list)


def test_main_loop(monkeypatch, pymc3e_fixture):
    """Test that main.main starts threads and handles serial mapping and shutdown correctly."""

    # Use your provided port-to-device mapping
    mock_port_to_headdevice_and_bitunit = {
        "/dev/ttyUSB0": ("D6364", "M3300"),
        "/dev/ttyUSB1": ("D6464", "M3400"),
        "/dev/ttyUSB2": ("D6564", "M3500")
    }

    # Prepare mock serial ports
    mock_serial_connections = {
        port: mock.Mock(name=port) for port in mock_port_to_headdevice_and_bitunit
    }

    # Patch the utility functions to inject mocks
    monkeypatch.setattr(main.utility, "initialize_serial_connections", lambda ports: ports.update(mock_serial_connections))
    monkeypatch.setattr(main.utility, "parse_serial_ports_config", lambda _: mock_port_to_headdevice_and_bitunit)
    monkeypatch.setattr(main.connect, "check_connection", lambda *_args, **_kwargs: True)

    # Patch monitor_serial_ports to simulate activity and stop shortly after
    def mock_monitor_serial_ports(data_queue, serial_ports, port_map, states, stop_event):
        time.sleep(0.1)
        stop_event.set()  # trigger shutdown early

    monkeypatch.setattr(main.utility, "monitor_serial_ports", mock_monitor_serial_ports)

    # Patch the worker to simulate work
    monkeypatch.setattr(main.utility, "worker", lambda *_args, **_kwargs: time.sleep(0.1))

    # Run main in a thread to simulate app lifecycle
    t = threading.Thread(target=main.main, args=(pymc3e_fixture, "127.0.0.1", 5000))
    
    # Catch SystemExit in the thread to avoid pytest warnings
    def target_with_exit_handling():
        try:
            main.main(pymc3e_fixture, "127.0.0.1", 5000)
        except SystemExit as e:
            assert e.code == 1  # Ensure that the exit code is 1 as expected

    t = threading.Thread(target=target_with_exit_handling)
    t.start()
    t.join(timeout=5)

    # After the thread has completed, check that it has shut down properly
    assert not t.is_alive(), "main.main() should complete and shut down"

    # Ensure flush and close were called on all mock serial connections
    for port in mock_serial_connections:
        mock_serial_connections[port].flush.assert_called_once()
        mock_serial_connections[port].close.assert_called_once()


