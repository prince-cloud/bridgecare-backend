import json
import requests
from django.conf import settings
from django.core.cache import cache


class PayStack:
    PAYSTACK_PRIVATE_KEY = settings.PAYSTACK_PRIVATE_KEY
    PAYSTACK_PUBLIC_KEY = settings.PAYSTACK_PUBLIC_KEY
    HEADERS = {"Authorization": f"Bearer {PAYSTACK_PRIVATE_KEY}"}

    base_url = "https://api.paystack.co"

    def make_request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Helper function to make the appropriate request to paystack"""
        options = {
            "GET": requests.get,
            "POST": requests.post,
            "PUT": requests.put,
            "DELETE": requests.delete,
        }
        url = "{}{}".format(self.base_url, path)
        headers = {
            "Authorization": "Bearer {}".format(self.PAYSTACK_PRIVATE_KEY),
            "Content-Type": "application/json",
        }
        return options[method](url, headers=headers, **kwargs)

    def initialize_payment(self, data):
        path = "/transaction/initialize"

        response = self.make_request(
            "POST",
            path,
            json={
                "amount": data["amount"],
                "email": data["email"],
                "reference": data["reference"],
                "currency": "GHS",
                "callback_url": data["callback_url"],
            },
        )
        print("== response: ", response.json())
        return self.verify_result(response)

    def verify_payment(self, ref, amount: int):
        path = "/transaction/verify/{}".format(ref)
        response = self.make_request("GET", path)
        return self.verify_result(response)

    def check_balance(self):
        path = "/balance/"
        response = self.make_request("GET", path)
        return self.verify_result(response)

    def verify_result(self, response: requests.Response):
        if response.status_code == 200:
            response_data = response.json()
            return response_data["status"], response_data["data"]
        response_data = response.json()
        return response_data["status"], response_data["message"]

    def get_telco_list(self):
        data = []
        telco_list = cache.get("telco-list")
        if not telco_list:
            paystack_base_url = f"{self.base_url}/bank?country=ghana"
            # make API Call
            response = requests.get(url=paystack_base_url, headers=self.HEADERS)

            # data
            if response.status_code == 200:
                body = json.loads(response.text)
                data_list = body["data"]
                for bank in data_list:
                    telco_type = bank.get("type")
                    if telco_type == "mobile_money":
                        data.append(bank)

            cache.set("telco-list", data, 60 * 60 * 12)

        else:
            data = telco_list

        return data

    def get_bank_list(self):
        data = []
        bank_list = cache.get("bank-list")

        if not bank_list:
            paystack_base_url = f"{self.base_url}/bank?country=ghana"
            # make API Call
            response = requests.get(url=paystack_base_url, headers=self.HEADERS)

            if response.status_code == 200:
                body = json.loads(response.text)
                data_list = body.get("data", [])
                seen_codes = set()

                for bank in data_list:
                    telco_type = bank.get("type")
                    code = bank.get("code")

                    # Ensure code is present and not a duplicate
                    if telco_type != "mobile_money" and code and code not in seen_codes:
                        seen_codes.add(code)
                        data.append(bank)

            cache.set("bank-list", data, 60 * 60 * 12)

        else:
            data = bank_list

        return data

    def verify_account_number(self, account_number, bank_code):

        # make api call to paystack to verify account number
        paystack_base_url = f"{self.base_url}/bank/resolve"
        params = {"account_number": account_number, "bank_code": bank_code}

        # make request
        response = requests.get(
            url=paystack_base_url,
            headers=self.HEADERS,
            params=params,
        )

        if response.status_code == 200:
            body = json.loads(response.text)
            data = body.get("data", {})

            return True, data

        else:
            return False, "Failed to verify account number"

    def create_recipient(self, data):
        url = f"{self.base_url}/transferrecipient"
        body = {
            "type": data["type"],
            "name": data["name"],
            "account_number": data["account_number"],
            "bank_code": data["bank_code"],
            "currency": data["currency"],
        }
        response = requests.post(
            url=url,
            headers=self.HEADERS,
            json=body,
        )

        if response.status_code == 201:
            body = json.loads(response.text)
            data = body.get("data", {})
            return True, data

        else:
            return False, "Failed to create recipient"

    def initiate_transfer(self, data):
        url = f"{self.base_url}/transfer"
        body = {
            "source": "balance",
            "amount": data["amount"],
            "recipient": data["recipient"],
            "reference": data["reference"],
            "reason": data["reason"],
        }

        response = requests.post(
            url=url,
            headers=self.HEADERS,
            json=body,
        )

        body = json.loads(response.text)
        if response.status_code == 200:
            data = body.get("data", {})
            return True, data
        else:
            return False, body.get("message", "Failed to initiate transfer")

    def verify_transfer(self, data):
        pass
