"""
Tests for .env-driven serial settings in utility/initialserial.py
"""

import os
import sys
from unittest import mock

import pytest
import serial

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utility import initialserial  # noqa: E402

ENV_KEYS = ["SERIAL_BAUDRATE", "SERIAL_BYTESIZE", "SERIAL_PARITY", "SERIAL_STOPBITS", "SERIAL_TIMEOUT"]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Make sure no SERIAL_* values leak in from the host environment."""
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_defaults_when_env_missing():
    assert initialserial.load_serial_settings() == initialserial.DEFAULT_SERIAL_SETTINGS


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("SERIAL_BAUDRATE", "9600")
    monkeypatch.setenv("SERIAL_BYTESIZE", "eightbits")
    monkeypatch.setenv("SERIAL_PARITY", "none")
    monkeypatch.setenv("SERIAL_STOPBITS", "TWO")
    monkeypatch.setenv("SERIAL_TIMEOUT", "0.5")

    assert initialserial.load_serial_settings() == {
        "baudrate": 9600,
        "bytesize": "EIGHTBITS",
        "parity": "NONE",
        "stopbits": "TWO",
        "timeout": 0.5,
    }


def test_short_aliases_and_quotes(monkeypatch):
    monkeypatch.setenv("SERIAL_BAUDRATE", '"4800"')
    monkeypatch.setenv("SERIAL_BYTESIZE", "8")
    monkeypatch.setenv("SERIAL_PARITY", "O")
    monkeypatch.setenv("SERIAL_STOPBITS", "1.5")

    s = initialserial.load_serial_settings()
    assert s["baudrate"] == 4800
    assert s["bytesize"] == "8"
    assert s["parity"] == "O"
    assert s["stopbits"] == "1.5"


@pytest.mark.parametrize("key,value", [
    ("SERIAL_BAUDRATE", "fast"),
    ("SERIAL_BAUDRATE", "-1"),
    ("SERIAL_BYTESIZE", "NINEBITS"),
    ("SERIAL_PARITY", "X"),
    ("SERIAL_STOPBITS", "3"),
    ("SERIAL_TIMEOUT", "abc"),
    ("SERIAL_TIMEOUT", "-2"),
])
def test_invalid_values_fall_back(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    assert initialserial.load_serial_settings() == initialserial.DEFAULT_SERIAL_SETTINGS


def test_empty_values_fall_back(monkeypatch):
    for key in ENV_KEYS:
        monkeypatch.setenv(key, "")
    assert initialserial.load_serial_settings() == initialserial.DEFAULT_SERIAL_SETTINGS


def test_initialize_uses_env_settings(monkeypatch):
    monkeypatch.setenv("SERIAL_BAUDRATE", "9600")
    monkeypatch.setenv("SERIAL_BYTESIZE", "8")
    monkeypatch.setenv("SERIAL_PARITY", "N")
    monkeypatch.setenv("SERIAL_STOPBITS", "1")
    monkeypatch.setenv("SERIAL_TIMEOUT", "2")

    with mock.patch.object(initialserial.serial, "Serial") as mock_serial:
        ports = initialserial.initialize_serial_connections({"/dev/ttyUSB0": None, "/dev/ttyUSB1": None})

    assert mock_serial.call_count == 2
    mock_serial.assert_any_call(
        port="/dev/ttyUSB0",
        baudrate=9600,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=2.0,
    )
    assert all(v is mock_serial.return_value for v in ports.values())


def test_initialize_uses_fallback_without_env():
    with mock.patch.object(initialserial.serial, "Serial") as mock_serial:
        initialserial.initialize_serial_connections({"/dev/ttyUSB0": None})

    mock_serial.assert_called_once_with(
        port="/dev/ttyUSB0",
        baudrate=19200,
        bytesize=serial.SEVENBITS,
        parity=serial.PARITY_EVEN,
        stopbits=serial.STOPBITS_ONE,
        timeout=1.0,
    )


def test_explicit_args_override_env(monkeypatch):
    monkeypatch.setenv("SERIAL_BAUDRATE", "9600")
    monkeypatch.setenv("SERIAL_PARITY", "ODD")

    with mock.patch.object(initialserial.serial, "Serial") as mock_serial:
        initialserial.initialize_serial_connections({"/dev/ttyUSB0": None}, baudrate=115200, parity="none")

    kwargs = mock_serial.call_args.kwargs
    assert kwargs["baudrate"] == 115200
    assert kwargs["parity"] == serial.PARITY_NONE


def test_open_failure_marks_port_none():
    with mock.patch.object(initialserial.serial, "Serial", side_effect=serial.SerialException("no device")):
        ports = initialserial.initialize_serial_connections({"/dev/ttyUSB9": None})
    assert ports == {"/dev/ttyUSB9": None}
