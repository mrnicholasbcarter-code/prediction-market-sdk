with open("tests/test_http_errors.py") as f:
    code = f.read()

# Add httpx to imports
if "import httpx_mock" not in code and "import httpx" not in code:
    code = code.replace("import pytest_asyncio", "import pytest_asyncio\nimport httpx")

# Fix num_requests for each test
replacements = [
    (
        """    async def test_get_balance_maps_http_errors(self, httpx_mock, kalshi_client, status_code, expected_error):
        httpx_mock.add_response(
            method="GET",
            url="https://demo-api.kalshi.co/trade-api/v2/portfolio/balance",
            status_code=status_code,
            json={"error": f"status {status_code}"},
        )""",
        """    async def test_get_balance_maps_http_errors(self, httpx_mock, kalshi_client, status_code, expected_error):
        num_requests = 3 if status_code in (429, 500) else 1
        for _ in range(num_requests):
            httpx_mock.add_response(
                method="GET",
                url="https://demo-api.kalshi.co/trade-api/v2/portfolio/balance",
                status_code=status_code,
                json={"error": f"status {status_code}"},
            )""",
    ),
    (
        """    async def test_submit_order_maps_http_errors(self, httpx_mock, kalshi_client, status_code, expected_error):
        httpx_mock.add_response(
            method="POST",
            url="https://demo-api.kalshi.co/trade-api/v2/portfolio/orders",
            status_code=status_code,
            json={"error": f"status {status_code}"},
        )""",
        """    async def test_submit_order_maps_http_errors(self, httpx_mock, kalshi_client, status_code, expected_error):
        num_requests = 3 if status_code in (429, 500) else 1
        for _ in range(num_requests):
            httpx_mock.add_response(
                method="POST",
                url="https://demo-api.kalshi.co/trade-api/v2/portfolio/orders",
                status_code=status_code,
                json={"error": f"status {status_code}"},
            )""",
    ),
    (
        """    async def test_get_markets_maps_http_errors(self, httpx_mock, polymarket_client, status_code, expected_error):
        httpx_mock.add_response(
            method="GET",
            url="https://clob.sandbox.polymarket.com/markets",
            status_code=status_code,
            json={"error": f"status {status_code}"},
        )""",
        """    async def test_get_markets_maps_http_errors(self, httpx_mock, polymarket_client, status_code, expected_error):
        num_requests = 3 if status_code in (429, 500) else 1
        for _ in range(num_requests):
            httpx_mock.add_response(
                method="GET",
                url="https://clob.sandbox.polymarket.com/markets",
                status_code=status_code,
                json={"error": f"status {status_code}"},
            )""",
    ),
]

for orig, new in replacements:
    code = code.replace(orig, new)

# Append tests for proper timeout retries
new_tests = """

    @pytest.mark.asyncio
    async def test_kalshi_timeout_retry(self, httpx_mock, kalshi_client):
        def raise_timeout(*args, **kwargs):
            raise httpx.TimeoutException("Read timeout")
            
        for _ in range(3):
            httpx_mock.add_callback(raise_timeout, url="https://demo-api.kalshi.co/trade-api/v2/portfolio/balance")
            
        with pytest.raises(KalshiExchangeServerError, match="timeout"):
            await kalshi_client.get_balance()
"""

if "test_kalshi_timeout_retry" not in code:
    # Insert inside TestKalshiHttpErrors
    kalshi_class_split = code.split("class TestPolymarketHttpErrors:")
    code_part1 = kalshi_class_split[0] + new_tests + "\nclass TestPolymarketHttpErrors:"
    code = code_part1 + kalshi_class_split[1]

poly_new_tests = """

    @pytest.mark.asyncio
    async def test_polymarket_timeout_retry(self, httpx_mock, polymarket_client):
        def raise_timeout(*args, **kwargs):
            raise httpx.TimeoutException("Read timeout")
            
        for _ in range(3):
            httpx_mock.add_callback(raise_timeout, url="https://clob.sandbox.polymarket.com/markets")
            
        with pytest.raises(PolymarketExchangeServerError, match="timeout"):
            await polymarket_client.get_markets()
"""

if "test_polymarket_timeout_retry" not in code:
    code = code + poly_new_tests

with open("tests/test_http_errors.py", "w") as f:
    f.write(code)
