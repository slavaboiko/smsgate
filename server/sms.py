# -----------------------------------------------------------------------------
# Copyright (c) 2022 Martin Schobert, Pentagrid AG
#
# All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
#  ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
#  WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
#  ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#  (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
#  ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
#  The views and conclusions contained in the software and documentation are those
#  of the authors and should not be interpreted as representing official policies,
#  either expressed or implied, of the project.
#
#  NON-MILITARY-USAGE CLAUSE
#  Redistribution and use in source and binary form for military use and
#  military research is not permitted. Infringement of these clauses may
#  result in publishing the source code of the utilizing applications and
#  libraries to the public. As this software is developed, tested and
#  reviewed by *international* volunteers, this clause shall not be refused
#  due to the matter of *national* security concerns.
# -----------------------------------------------------------------------------

from __future__ import annotations

import datetime
import uuid
import base64
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from modem import Modem  # avoid circular dependency


class SMS:
    def __init__(
        self,
        sms_id: Optional[str],
        recipient: str,
        text: str,
        timestamp: Optional[datetime.datetime] = None,
        sender: Optional[str] = None,
        receiving_modem: Optional[Modem] = None,
        flash: bool = False,
        # New fields for multi-part messages
        message_ref: Optional[int] = None,
        total_parts: Optional[int] = None,
        part_number: Optional[int] = None,
    ) -> None:
        """
        This class represents an SMS.
        @param sms_id: Each SMS has an ID, which is technically a UUID.
        @param recipient: The recipient's phone number in international format as string.
        @param text: The SMS text as string.
        @param timestamp: A datetime representing the creation timestampt of this SMS.
        @param sender: The sender's phone number in international format as string. For received SMS, this is sometimes a human readable string with a name.
        @param receiving_modem: The receiving modem's identifier.
        @param flash: Send SMS as flash message, which should pop up on the destination phone and then disappear.
        @param message_ref: Reference number for multi-part messages to identify parts of the same message.
        @param total_parts: Total number of parts in a multi-part message. Defaults to 1 for single messages.
        @param part_number: Current part number in a multi-part message.
        """
        self.sms_id = sms_id if sms_id else str(uuid.uuid4())
        self.recipient = recipient
        self.text = text
        self.timestamp = timestamp if timestamp else datetime.datetime.now()
        self.created_timestamp = datetime.datetime.now()
        self.sender = sender
        self.receiving_modem = receiving_modem
        self.flash = flash
        # Multi-part message fields
        self.message_ref = message_ref
        self.total_parts = total_parts if total_parts is not None else 1  # Default to 1 for single messages
        self.part_number = part_number
        self.parts = {}  # Dictionary to store message parts

    def get_timestamp(self) -> datetime.datetime:
        """ Returns the timestamp as Python datetime. """
        return self.timestamp

    def get_age(self) -> datetime.timedelta:
        """ Returns the age as Python timedelta. """
        return datetime.datetime.now(datetime.timezone.utc) - self.timestamp

    def get_id(self) -> str:
        """ Returns the SMS ID, which is a UUID string. """
        return self.sms_id

    def get_text(self) -> str:
        """ Returns the SMS message test as string. """
        return self.text

    def get_recipient(self) -> str:
        """ Returns the recipient as string. """
        return self.recipient

    def get_sender(self) -> str:
        """ Returns the sender as string. """
        return self.sender

    def is_flash(self) -> bool:
        """ Returns status if the SMS is a flash SMS. """
        return self.flash

    def has_sender(self) -> bool:
        """
        Check if the object has a sender set.
        @return: Returns True or False.
        """
        return self.sender is not None and self.sender != ""

    def get_receiving_modem(self) -> Modem:
        """
        Get the modem that received the message.
        @return: Returns the receiving modem as Modem object.
        """
        return self.receiving_modem

    def to_string(self, content=True) -> str:
        """
        Format the whole message into a string.
        @return: Returns the entire SMS as formatted string.
        """
        ts_fmt = "%Y-%m-%d %H:%M:%S  %z"
        text = (
            f"SMS ID            : {self.sms_id}\n"
            + f"Sender            : {self.sender}\n"
            + f"Recipient         : {self.recipient}\n"
            + f"Message timestamp : {self.timestamp.strftime(ts_fmt)}\n"
            + f"Created timestamp : {self.created_timestamp.strftime(ts_fmt)}\n"
            + f"Flash message     : {self.flash}\n"
        )
        if self.receiving_modem:
            text += f"Receiving modem   : {self.receiving_modem.get_identifier()}\n"
            text += (
                f"Receiving network : {self.receiving_modem.get_current_network()}\n"
            )

        if content:
            text += (
                f"Text              :\n\n"
                + "---------------------------------------------------------\n"
                + self.text
                + "\n"
                + "---------------------------------------------------------\n"
            )

        return text

    def to_dict(self, include_modem: bool = True) -> dict:
        """
        Convert the SMS object to a dictionary format suitable for RPC responses.
        @param include_modem: Whether to include the modem identifier in the output
        @return: Returns a dictionary containing all relevant SMS information
        """
        # Always encode text in base64 for consistent format
        text = self.get_concatenated_text() if self.is_multipart() else self.get_text() or ""
        text_encoded = base64.b64encode(text.encode('latin1')).decode('ascii')

        # Convert timestamp to ISO format string for XML-RPC serialization
        timestamp = self.get_timestamp()
        if isinstance(timestamp, datetime.datetime):
            timestamp = timestamp.isoformat()

        result = {
            "id": str(self.get_id() or ""),
            "recipient": str(self.get_recipient() or ""),
            "text": str(text_encoded),
            "sender": str(self.get_sender() or ""),
            "timestamp": timestamp,
            "flash": bool(self.is_flash() if hasattr(self, 'is_flash') else False),
            "is_multipart": bool(self.is_multipart()),
            "total_parts": int(self.total_parts),
            "received_parts": int(len(self.parts) if self.is_multipart() else 1)
        }
        
        if include_modem and self.receiving_modem:
            result["modem"] = str(self.receiving_modem.get_identifier())
            
        return result

    def is_multipart(self) -> bool:
        """Returns True if this is a multi-part message."""
        # Check if we have multiple parts stored or if total_parts was explicitly set
        return len(self.parts) > 1 or (self.total_parts is not None and self.total_parts > 1)

    def is_part_complete(self) -> bool:
        """Returns True if all parts of a multi-part message have been received."""
        if not self.is_multipart():
            return True
        return len(self.parts) == self.total_parts

    def get_concatenated_text(self) -> str:
        """Returns the concatenated text of all parts in order."""
        if not self.is_multipart():
            return self.text
        if not self.is_part_complete():
            return self.text  # Return current text if not complete
        # Concatenate all parts in order
        try:
            return ''.join(self.parts[i] for i in range(1, self.total_parts + 1))
        except KeyError as e:
            # If we're missing a part, return the current text
            return self.text

    def add_part(self, part_number: int, text: str) -> None:
        """
        Add a part to the multi-part message.
        @param part_number: The part number (1-based index)
        @param text: The text content of this part
        @raises ValueError: If part_number is invalid or out of range
        """
        if part_number < 1:
            raise ValueError(f"Invalid part number {part_number}. Must be positive")
            
        if part_number > self.total_parts:
            self.total_parts = part_number
            
        self.parts[part_number] = text
        # Update the main text if this is the first part
        if part_number == 1:
            self.text = text
