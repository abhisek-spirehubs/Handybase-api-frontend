import httpx
from django.conf import settings

class APIError(Exception):
    """Custom exception to capture FastAPI error details."""
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API Error {status_code}")

class APIClient:
    def __init__(self, token=None):
        self.base_url = getattr(settings, "API_BASE_URL", "http://127.0.0.1:8000/api/v1")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        self._client = httpx.Client(
            base_url=self.base_url, 
            headers=headers, 
            timeout=30.0  # Increased timeout for file uploads
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._client.close()

    def _handle_response(self, response):
        """Processes the response, handling errors and non-JSON content safely."""
        # Handle 4xx and 5xx errors
        if response.status_code >= 400:
            try:
                error_data = response.json()
            except Exception:
                # Fallback if the backend sends an HTML error page (prevents JSONDecodeError)
                error_data = {"message": f"Server Error {response.status_code}", "detail": response.text[:200]}
            raise APIError(response.status_code, error_data)
        
        # Handle empty responses (like 204 No Content)
        if not response.content or response.text.strip() == "":
            return {"success": True, "data": {}}

        # Parse valid JSON
        try:
            return response.json()
        except Exception:
            return {"success": True, "data": {}, "message": "Response was not JSON"}

    def _request_without_content_type(self, method, path, **kwargs):
        """Removes JSON Content-Type so httpx can automatically generate multipart boundaries."""
        client_headers = dict(self._client.headers)
        # Safely remove any Content-Type header
        client_headers.pop("content-type", None)
        client_headers.pop("Content-Type", None)

        with httpx.Client(
            base_url=self.base_url,
            headers=client_headers,
            timeout=30.0
        ) as temp_client:
            response = getattr(temp_client, method)(path, **kwargs)
            return self._handle_response(response)

    def get(self, path, params=None, **kwargs):
        """Supports query parameters for listing plans."""
        return self._handle_response(self._client.get(path, params=params, **kwargs))

    def post(self, path, json=None, data=None, files=None, **kwargs):
        """Supports JSON body, form data, and file uploads."""
        if files is not None or data is not None:
            return self._request_without_content_type("post", path, data=data, files=files, **kwargs)
        return self._handle_response(self._client.post(path, json=json, **kwargs))

    def patch(self, path, json=None, data=None, files=None, **kwargs):
        """Supports JSON body and multipart data."""
        if files is not None or data is not None:
            return self._request_without_content_type("patch", path, data=data, files=files, **kwargs)
        return self._handle_response(self._client.patch(path, json=json, **kwargs))

    def put(self, path, json=None, data=None, files=None, **kwargs):
        """Supports JSON body and multipart data."""
        if files is not None or data is not None:
            return self._request_without_content_type("put", path, data=data, files=files, **kwargs)
        return self._handle_response(self._client.put(path, json=json, **kwargs))

    def delete(self, path, **kwargs):
        return self._handle_response(self._client.delete(path, **kwargs))


# ── HELPER FUNCTIONS ──────────────────────────────────────────────────────────

def get_api_client(request):
    """Used for authenticated requests (Dashboard, Upgrade, Profile)."""
    token = request.session.get("access_token")
    return APIClient(token=token)

def get_anon_client():
    """Used for non-authenticated requests (Login, Register)."""
    return APIClient(token=None)