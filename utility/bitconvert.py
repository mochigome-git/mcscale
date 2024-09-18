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
        value & 0xFF           # Least significant byte
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
    low_word = value & 0xFFFF      # Lower 16 bits (0 - 65535)
    high_word = (value >> 16) & 0xFFFF  # Upper 16 bits (0 - 65535)

    return [low_word, high_word]