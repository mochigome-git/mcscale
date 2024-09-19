import pytest
from unittest import mock

# Mock pymcprotocol globally before importing main.py to prevent real connections
with mock.patch("pymcprotocol.Type3E") as MockType3E:
    # Create a mock instance and set up the connect method
    mock_pymc3e_instance = MockType3E.return_value
    mock_pymc3e_instance.connect.return_value = None
    import main

@pytest.fixture
def mock_pymc3e():
    mock_pymc3e = mock.Mock(spec=main.pymcprotocol.Type3E)
    mock_pymc3e.connect.return_value = None
    mock_pymc3e.batchwrite_wordunits.return_value = None
    mock_pymc3e.batchwrite_bitunits.return_value = None
    return mock_pymc3e

@pytest.fixture
def mock_serial():
    serial_mock = mock.Mock()
    serial_mock.in_waiting = 0
    serial_mock.read.return_value = b""
    return serial_mock

def test_process_serial_data(mock_serial, mock_pymc3e, monkeypatch):
    monkeypatch.setattr(main.utility, "split_32bit_to_16bit", lambda x: [x // 2, x // 2])

    mock_serial.in_waiting = 10
    mock_serial.read.return_value = b"ST,+01234g\r\n"

    main.process_serial_data(mock_serial, "D6364", "M3300")

    mock_pymc3e.batchwrite_wordunits.assert_called_with(headdevice="D6364", values=[617, 617])
    mock_pymc3e.batchwrite_bitunits.assert_any_call(headdevice="M3300", values=[1])
    mock_pymc3e.batchwrite_bitunits.assert_any_call(headdevice="M3300", values=[0])

def test_main_loop(mock_serial, monkeypatch):
    monkeypatch.setattr(main.utility, "initialize_serial_connections", mock.Mock())
    monkeypatch.setattr(main, "process_serial_data", mock.Mock())

    # Mock the port_to_headdevice_and_bitunit dictionary
    mock_port_to_headdevice_and_bitunit = {
        "/dev/ttyUSB0": ("D6364", "M3300"),
    }
    
    with monkeypatch.context() as m:
        m.setattr(main, "port_to_headdevice_and_bitunit", mock_port_to_headdevice_and_bitunit)

        serial_ports = {"/dev/ttyUSB0": mock_serial}

        with mock.patch.dict(main.port_to_headdevice_and_bitunit, serial_ports):
            with pytest.raises(KeyboardInterrupt):
                main.main()

        main.process_serial_data.assert_called_with(mock_serial, "D6364", "M3300")
