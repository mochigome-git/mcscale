import pymcprotocol

# Qシリーズがデフォルトです
pymc3e = pymcprotocol.Type3E()
"""
Qシリーズ以外の場合はインスタンス化にplctypeを与えてください

例:
pymc3e = pymcprotocol.Type3E(plctype="L") 
pymc3e = pymcprotocol.Type3E(plctype="iQ-R")
pymc3e = pymcprotocol.Type3E(plctype="QnA")
pymc3e = pymcprotocol.Type3E(plctype="iQ-L")
"""


# イーサネットの接続形式をASCIIにした場合はここで"ascii"を与えてください
# もしMCプロトコルのアクセス経路をデフォルトから変更する場合もこのメソッドから可能です.
# pymc3e.setaccessopt(commtype="ascii")
# PLCに設定したIPアドレス, MCプロトコル用ポートに接続
pymc3e.connect("192.168.3.111", 5013)


def convert_to_base256(value):
    """Breaks down the target_value into an array where each element represents a byte (base 256).

    Args:
        value (int): The number to convert.

    Returns:
        list of int: The base256 representation of the number.
    """
    base256 = []
    while value > 0:
        base256.append(value % 256)
        value //= 256
    base256.reverse()  # Reverse to get the correct order
    return base256


def convert_to_32bit(value):
    """Converts a given integer to its 32-bit representation (4 bytes)."""
    if value < 0 or value > 0xFFFFFFFF:
        raise ValueError("Value out of range for 32-bit conversion")

    # Convert to 4 bytes (32 bits)
    base256 = [
        (value >> 24) & 0xFF,  # Most significant byte
        (value >> 16) & 0xFF,
        (value >> 8) & 0xFF,
        value & 0xFF,  # Least significant byte
    ]
    return base256


def split_32bit_to_16bit(value):
    """Splits a 32-bit integer into two 16-bit words.

    Args:
        value (int): The 32-bit integer to split.

    Returns:
        list of int: A list containing two 16-bit integers [high_word, low_word].
    """
    if value < 0 or value > 0xFFFFFFFF:
        raise ValueError("Value out of range for 32-bit conversion")

    # Extract the lower 16 bits and upper 16 bits
    low_word = value & 0xFFFF  # Lower 16 bits (0 - 65535)
    high_word = (value >> 16) & 0xFFFF  # Upper 16 bits (0 - 65535)

    return [low_word, high_word]


# D100からD110まで読み込み
# wordunits_values = pymc3e.batchread_wordunits(headdevice="D6564", readsize=1)
# print(wordunits_values)
#
# #X10からX20まで読み込み(ビットデバイスアクセス)
# bitunits_values = pymc3e.batchread_bitunits(headdevice="X10", readsize=10)
#
# D10からD15まで与えた数値を書き込み
# Example usage:
target_value = 1
converted_values = split_32bit_to_16bit(target_value)
# print(f"Converted values (32-bit split into 16-bit): {converted_values}")
# Write the split 16-bit values to the PLC
pymc3e.batchwrite_wordunits(headdevice="D6564", values=converted_values)
#
# #Y10からY15まで与えた数値を書き込み(ビットデバイスアクセス)
# pymc3e.batchwrite_bitunits(headdevice="M3300", values=[1])
#
# #"D1000", "D2000"をワード単位で読み込み
# #"D3000"をダブルワードで読み込み. (D3001が上位16ビットD3000が下位16ビット)
# word_values, dword_values = pymc3e.randomread(word_devices=["D1000", "D2000"], dword_devices=["D3000"])
#
# #"D1000"に1000 "D2000"に2000を書き込み
# #"D3000"に655362を書き込み. (D3001が上位16ビットD3000が下位16ビット)
# pymc3e.randomwrite(word_devices=["D1000", "D1002"], word_values=[1000, 2000],
#                    dword_devices=["D1004"], dword_values=[655362])
#
# #X0とX10にそれぞれ1と0を書き込み
# pymc3e.randomwrite_bitunits(bit_devices=["X0", "X10"], values=[1, 0])
