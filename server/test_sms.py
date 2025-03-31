#!/usr/bin/env python3
import pytest
from gsmmodem.pdu import decodeSmsPdu

from unittest import mock
from server import sms
import datetime

def test_concatenation():
    """
    Test concatenation of multi-part SMS messages.
    Tests that parts are properly combined in order and the complete message is assembled correctly.
    """
    # Create a mock modem
    mock_modem = mock.Mock()
    mock_modem.get_identifier.return_value = "00"
    mock_modem.get_current_network.return_value = "Fake Operator"

    expected_text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."
    parts = [expected_text[i:i+140] for i in range(0, len(expected_text), 140)]

    # Create SMS parts
    sms_parts = [
        sms.SMS(
            sms_id=None,
            recipient="+44123456789",
            text=parts[i],
            timestamp=datetime.datetime(2025, 3, 31, 9, 7, 54, tzinfo=datetime.timezone(datetime.timedelta(hours=1))),
            sender="+44123456789",
            receiving_modem=mock_modem,
            message_ref=202,
            total_parts=len(parts),
            part_number=i+1
        ) for i in range(len(parts))
    ]

    # Create base SMS object to add parts to
    base_sms = sms_parts[0]

    # Add remaining parts
    for part in sms_parts[1:]:
        print("Adding part: ", part.part_number, part.text)
        base_sms.add_part(part.part_number, part.text)

    assert base_sms.is_multipart() == True
    assert base_sms.total_parts == len(parts)
    assert len(base_sms.parts) == len(parts)
    assert base_sms.get_concatenated_text() == expected_text
    assert base_sms.is_part_complete() == True
    assert base_sms.text == expected_text


def test_cyrillic_sms_to_dict():
        # Create a mock modem
    mock_modem = mock.Mock()
    mock_modem.get_identifier.return_value = "00"
    mock_modem.get_current_network.return_value = "Fake Operator"

    expected_text = "Противоположная точка зрения подразумевает, что некоторые особенности внутренней политики заблокированы в рамках своих собственных рациональных ограничений. Имеется спорная точка зрения, гласящая примерно следующее: стремящиеся вытеснить традиционное производство, нанотехнологии будут обнародованы. Банальные, но неопровержимые выводы, а также ключевые особенности структуры проекта призывают нас к новым свершениям, которые, в свою очередь, должны быть объективно рассмотрены соответствующими инстанциями. Современные технологии достигли такого уровня, что реализация намеченных плановых заданий предполагает независимые способы реализации распределения внутренних резервов и ресурсов."

    # Create SMS parts
    complete_sms = sms.SMS(
        sms_id=None,
        recipient="+44123456789",
        text=expected_text,
        timestamp=datetime.datetime(2025, 3, 31, 9, 7, 54, tzinfo=datetime.timezone(datetime.timedelta(hours=1))),
        sender="+44123456789",
        receiving_modem=mock_modem,
        message_ref=None,
        total_parts=None,
        part_number=None
    )

    complete_sms.to_dict()

if __name__ == '__main__':
    pytest.main()
