"""
LibreView API Client
Provides access to LibreView glucose monitoring API endpoints.
"""

import hashlib
import logging
from typing import Dict, Optional, Tuple

import requests


logger = logging.getLogger(__name__)


class LibreViewClient:
    """Client for interacting with the LibreView API."""

    HOST = "https://api.libreview.io"

    DEFAULT_HEADERS = {
        "accept-encoding": "gzip",
        "Content-Type": "application/json",
        "Accept": "application/json, application/xml, multipart/form-data",
        "product": "llu.ios",
        "version": "4.16.0",
        "User-Agent": "LibreLink/4.16.0 (iPhone; iOS 17.0; Scale/3.00)",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    }

    def __init__(self, email: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize the LibreView client.

        Args:
            email: User email for authentication
            password: User password for authentication
        """
        self.email = email
        self.password = password
        self._auth_token: Optional[str] = None
        # self._user_id: Optional[str] = None
        self._account_id: Optional[str] = None

    @property
    def auth_token(self) -> Optional[str]:
        """Get the current authentication token."""
        if not self._auth_token:
            self.authenticate()
        return self._auth_token

    @property
    def account_id(self) -> Optional[str]:
        """Get the current account id token."""
        if not self._account_id:
            self.authenticate()
        return self._account_id

    # @property
    # def user_id(self) -> Optional[str]:
    #     """Get the current user ID."""
    #     if not self._user_id:
    #         self.authenticate()
    #     return self._user_id

    def _make_request(
        self,
        url: str,
        method: str = "GET",
        auth_token: Optional[str] = None,
        account_id: Optional[str] = None,
        json_payload: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        anonymous: bool = False,
    ) -> Dict:
        """
        Make an HTTP request and return the response JSON.

        Args:
            url: The full URL to request
            method: HTTP method (GET or POST)
            auth_token: Optional Bearer token for authentication
            json_payload: Optional JSON payload for POST requests
            headers: Optional custom headers (merged with defaults)

        Returns:
            The response JSON as a dictionary

        Raises:
            ValueError: If the request fails or response is invalid
        """
        reply = "Error"
        merged_headers = (headers or self.DEFAULT_HEADERS).copy()

        if not anonymous:
            # avoid triggering an loop calling authenticate
            token = auth_token or self._auth_token
            account_id = account_id or self._account_id
            if not token or not account_id:
                raise ValueError("Authentication required. Call authenticate() first.")

            if token:
                merged_headers["Authorization"] = f"Bearer {auth_token}"

            if account_id:
                merged_headers["account-id"] = hashlib.sha256(
                    account_id.encode()
                ).hexdigest()

        try:
            if method.upper() == "POST":
                response = requests.post(
                    url, json=json_payload, headers=merged_headers, timeout=10
                )
            elif method.upper() == "GET":
                response = requests.get(url, headers=merged_headers, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            reply = response.json()
            response.raise_for_status()
            return reply

        except requests.RequestException as e:
            logger.error("HTTP request failed: %s", e)
            raise ValueError(f"Failed to fetch data from {url}: {str(reply)}") from e
        except ValueError as e:
            logger.error(
                "Response content is not valid JSON or had an unexpected value: %s", e
            )
            raise
        except KeyError as e:
            logger.error("Expected key missing in response: %s", e)
            raise

    def authenticate(
        self, email: Optional[str] = None, password: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Authenticate with LibreView API and store the Bearer token.

        Args:
            email: User email (uses instance email if not provided)
            password: User password (uses instance password if not provided)

        Returns:
            Tuple of (auth_token, user_id)

        Raises:
            ValueError: If authentication fails or credentials are missing
        """
        email = email or self.email
        password = password or self.password

        if not email or not password:
            raise ValueError("Email and password are required for authentication")

        response = self._make_request(
            url=f"{self.HOST}/llu/auth/login",
            method="POST",
            json_payload={"email": email, "password": password},
            anonymous=True,
        )

        try:
            self._auth_token = response["data"]["authTicket"]["token"]
            self._account_id = response["data"]["user"]["id"]
            return self._auth_token, self._account_id
        except KeyError:
            logger.error("Authentication response structure unexpected: %s", response)
            raise ValueError("Authentication response missing expected fields")

    def get_connections(self, auth_token: Optional[str] = None) -> Dict:
        """
        Get available connections for authenticated user.

        Args:
            auth_token: Optional auth token (uses stored token if not provided)

        Returns:
            Connections data dictionary
        """
        token = auth_token or self._auth_token
        if not token:
            raise ValueError("Authentication required. Call authenticate() first.")

        return self._make_request(
            url=f"{self.HOST}/llu/connections", method="GET", auth_token=token
        )

    def fetch_graph(self, patient_id: str, auth_token: Optional[str] = None) -> Dict:
        """
        Fetch graph data for a specific patient.

        Args:
            patient_id: The patient ID to fetch data for
            auth_token: Optional auth token (uses stored token if not provided)

        Returns:
            Graph data dictionary
        """
        token = auth_token or self._auth_token
        if not token:
            raise ValueError("Authentication required. Call authenticate() first.")

        return self._make_request(
            url=f"{self.HOST}/llu/connections/{patient_id}/graph",
            method="GET",
            auth_token=token,
        )

    def fetch_logbook(self, patient_id: str, auth_token: Optional[str] = None) -> Dict:
        """
        Fetch logbook data for a specific patient.

        Args:
            patient_id: The patient ID to fetch data for
            auth_token: Optional auth token (uses stored token if not provided)

        Returns:
            Logbook data dictionary
        """
        token = auth_token or self._auth_token
        if not token:
            raise ValueError("Authentication required. Call authenticate() first.")

        return self._make_request(
            url=f"{self.HOST}/llu/connections/{patient_id}/logbook",
            method="GET",
            auth_token=token,
        )

    def fetch_account_data(self, auth_token: Optional[str] = None) -> Dict:
        """
        Fetch user account data.

        Args:
            auth_token: Optional auth token (uses stored token if not provided)

        Returns:
            Account data dictionary
        """
        token = auth_token or self._auth_token
        if not token:
            raise ValueError("Authentication required. Call authenticate() first.")

        return self._make_request(
            url=f"{self.HOST}/account", method="GET", auth_token=token
        )

    def accept_terms(self, terms_token: str) -> Dict:
        """
        Accept terms of use with provided token.

        Args:
            terms_token: The terms acceptance token

        Returns:
            Response data dictionary
        """
        return self._make_request(
            url=f"{self.HOST}/auth/continue/tou", method="POST", auth_token=terms_token
        )

    def fetch_reading(
        self, account_id: Optional[str] = None, auth_token: Optional[str] = None
    ) -> Dict:
        """
        Fetch user reading with account-specific headers.

        This method uses a hashed account-id header as required by the API.
        Thanks to: https://github.com/TA2k/ioBroker.libre/commit/e29c214919ae493d8b2ef92ae395e98435b03179

        Args:
            account_id: The account ID to fetch readings for
            auth_token: Optional auth token (uses stored token if not provided)

        Returns:
            Reading data dictionary

        Raises:
            ValueError: If the request fails
        """

        return self._make_request(f"{self.HOST}/llu/connections")
