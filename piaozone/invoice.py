from copy import deepcopy


class Invoice:
    def __init__(self, client):
        self._client = client

    def issue_blue(self, serial_no, payload):
        """2.1.01: acceptance is not issuance. Reuse serial_no for result queries."""
        if not isinstance(serial_no, str) or not serial_no.strip() or len(serial_no) > 50:
            raise ValueError("serial_no is required and must not exceed 50 characters.")
        data = deepcopy(payload)
        if data.get("serialNo", serial_no) != serial_no:
            raise ValueError("Conflicting invoice serial number.")
        if str(data.get("invoiceProperty", "0")) != "0":
            raise ValueError("issue_blue cannot issue a red invoice.")
        if data.get("invoiceType") not in ("01", "02"):
            raise ValueError("Only digital normal and special invoices are supported.")
        for key in ("sellerName", "sellerTaxpayerId", "buyerName", "invoiceDetail"):
            if not data.get(key):
                raise ValueError(f"Missing {key}.")
        data.update(serialNo=serial_no, invoiceProperty="0")
        # The vendor success example returns a plain serialNo even though the schema
        # describes it as encrypted. Submission data is opaque; query establishes truth.
        return self._client.call("ALLE.INVOICE.OPEN", data, decode_data=False)

    def query(self, serial_no, seller_taxpayer_id):
        """4.1.04: query the original externally assigned serial number."""
        if not serial_no or not seller_taxpayer_id:
            raise ValueError("Original serial number and seller tax ID are required.")
        return self._client.call("ALLE.INVOICE.QUERY", {
            "serialNo": serial_no, "sellerTaxpayerId": seller_taxpayer_id,
        })
