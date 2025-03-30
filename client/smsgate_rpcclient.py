#!/usr/bin/env python3
import xmlrpc.client
import ssl
import os
import time
import base64
from typing import Dict, List, Optional, Union, Tuple
from datetime import datetime

class SMSGateRPCClient:
    """
    A reusable RPC client for SMSGate server that handles all XMLRPC communication.
    This class can be used by both CLI and Telegram bot clients.
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 7000,
        ca_file: Optional[str] = None,
        api_token: Optional[str] = None
    ):
        """
        Initialize the RPC client.
        
        Args:
            host: Server hostname
            port: Server port
            ca_file: Path to CA certificate file
            api_token: API token (can also be set via SMSGATE_APITOKEN env var)
        """
        self.host = host
        self.port = port
        self.ca_file = ca_file
        self.api_token = api_token or os.getenv('SMSGATE_APITOKEN')
        
        if not self.api_token:
            raise ValueError("API token must be provided or set via SMSGATE_APITOKEN environment variable")
        
        # Create SSL context
        context = ssl._create_unverified_context()
        if ca_file and os.path.exists(ca_file):
            context.load_verify_locations(ca_file)
            
        # Create XMLRPC client
        self.client = xmlrpc.client.ServerProxy(
            f"https://{host}:{port}",
            context=context
        )

    def get_stats(self) -> Dict[str, Dict[str, Union[str, int, float]]]:
        """
        Get modem status information.
        
        Returns:
            Dictionary containing status information for each modem
        """
        result = self.client.get_stats(self.api_token)
        return result[1]  # Return the stats dictionary

    def _decode_text(self, text: str) -> str:
        """
        Decode text that might be base64 encoded.
        @param text: The text to decode
        @return: Decoded text
        """
        return base64.b64decode(text.encode('ascii')).decode("ascii")

    def get_sms(self, phone_number: str = "") -> List[Dict[str, Union[str, bool, datetime]]]:
        """
        Get SMS messages.
        
        Args:
            phone_number: Optional phone number to filter messages
            
        Returns:
            List of SMS messages as dictionaries
        """
        messages = self.client.get_sms(self.api_token, phone_number)
        for msg in messages:
            msg['text'] = self._decode_text(msg['text'])
        return messages

    def send_ussd(self, sender: str, ussd_code: str) -> Tuple[str, str]:
        """
        Send USSD code.
        
        Args:
            sender: Phone number to use
            ussd_code: USSD code to send
            
        Returns:
            Tuple of (status, response)
        """
        return self.client.send_ussd(self.api_token, sender, ussd_code)

    def send_sms(
        self,
        sender: str,
        recipient: str,
        text: str,
        flash: bool = False,
        wait_for_delivery: bool = True
    ) -> str:
        """
        Send SMS message.
        
        Args:
            sender: Phone number to use
            recipient: Recipient phone number
            text: Message text
            flash: Whether to send as flash message
            wait_for_delivery: Whether to wait for delivery confirmation
            
        Returns:
            SMS ID
        """
        sms_id = self.client.send_sms(self.api_token, sender, recipient, text, flash)
        
        if wait_for_delivery:
            while not self.client.get_delivery_status(self.api_token, sms_id):
                time.sleep(3)
                
        return sms_id

    def get_delivery_status(self, sms_id: str) -> bool:
        """
        Check SMS delivery status.
        
        Args:
            sms_id: SMS ID to check
            
        Returns:
            True if delivered, False otherwise
        """
        return self.client.get_delivery_status(self.api_token, sms_id)

    def read_stored_sms(self) -> List[Dict[str, Union[str, bool, datetime]]]:
        """
        Read stored SMS from all modems.
        
        Returns:
            List of SMS messages as dictionaries
        """
        return self.client.read_stored_sms(self.api_token)

    def get_health_state(self) -> Tuple[str, str]:
        """
        Get system health state.
        
        Returns:
            Tuple of (level, message)
        """
        return self.client.get_health_state(self.api_token)

    def ping(self) -> str:
        """
        Check if server is reachable.
        
        Returns:
            "OK" if server is reachable
        """
        return self.client.ping()

    def get_all_sms(self) -> List[Dict[str, Union[str, bool, datetime]]]:
        """
        Get all SMS messages from all modems.
        @return: Returns a list of dictionaries containing SMS data or an empty list.
        """
        messages = self.client.get_all_sms(self.api_token)
        for msg in messages:
            msg['text'] = self._decode_text(msg['text'])
        return messages