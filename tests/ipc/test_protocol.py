"""Tests for IPC protocol encoding/decoding."""

from __future__ import annotations

from tak.ipc.protocol import IPCRequest, IPCResponse


class TestIPCRequest:
    def test_encode_decode_roundtrip(self) -> None:
        req = IPCRequest(method="list_agents", params={"foo": "bar"}, request_id=42)
        encoded = req.encode()
        header = encoded[:4]
        payload = encoded[4:]
        length = int.from_bytes(header, byteorder="big")
        assert length == len(payload)

        decoded = IPCRequest.decode(payload)
        assert decoded.method == "list_agents"
        assert decoded.params == {"foo": "bar"}
        assert decoded.request_id == 42

    def test_encode_empty_params(self) -> None:
        req = IPCRequest(method="status")
        encoded = req.encode()
        payload = encoded[4:]
        decoded = IPCRequest.decode(payload)
        assert decoded.method == "status"
        assert decoded.params == {}


class TestIPCResponse:
    def test_success_roundtrip(self) -> None:
        resp = IPCResponse(success=True, data={"agents": []}, request_id=1)
        encoded = resp.encode()
        payload = encoded[4:]
        decoded = IPCResponse.decode(payload)
        assert decoded.success is True
        assert decoded.data == {"agents": []}

    def test_error_roundtrip(self) -> None:
        resp = IPCResponse(success=False, error="not found", request_id=2)
        encoded = resp.encode()
        payload = encoded[4:]
        decoded = IPCResponse.decode(payload)
        assert decoded.success is False
        assert decoded.error == "not found"
