#!/usr/bin/env python3
import pytest
from gsmmodem.pdu import decodeSmsPdu

# Define test cases as a list of tuples
@pytest.mark.parametrize("test_input,expected,description", [
    (
        "050003B4D0B5D0BBD0B5D0B3D0BED0B2D0B0D0B9D182D0B5",
        "елеговайте",
        "Russian text in PDU format ('елеговайте' in UTF-8 hex)"
    ),
    (
        "Hello, World!",
        "Hello, World!",
        "Non-PDU text (should remain unchanged)"
    ),
    (
        "050003B4invalid",
        "050003B4invalid",
        "Invalid PDU format (should return original text if decoding fails)"
    ),
    (
        "050003B4",
        "050003B4",
        "Empty PDU header (should return original text if no data after header)"
    ),
    (
        "050003B4D0B5D0B",
        "050003B4D0B5D0B",
        "Malformed hex data (should return original text if hex is invalid)"
    ),
    (
        "050003B507070442043D0430044F00200433043E0440044F04470430044F0020043B0438043D0438044F0020043200200440043E0443043C0438043D04330435003A0020003000350030003000200438043B04380020002B00370039003200360031003100310030003900390039",
        "Большой текст с цифрами: 0500 887926111099",
        "Large text with numbers: 0500 887926111099"
    )
])
def test_pdu_decoding(test_input, expected, description):
    """
    Test PDU decoding functionality.
    PDU format: 050003B4<hex_data>
    - 05: Data coding scheme (DCS)
    - 00: Message class
    - 03: Message reference
    - B4: User data length
    - <hex_data>: UTF-8 encoded text
    """
    
    result = decodeSmsPdu(test_input)
    
    assert result == expected

if __name__ == '__main__':
    result = decodeSmsPdu("050003B4D0B5D0BBD0B5D0B3D0BED0B2D0B0D0B9D182D0B5")
    print(result)
    #pytest.main()
