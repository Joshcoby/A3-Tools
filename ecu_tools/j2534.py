"""
Minimal J2534 (PassThru) ctypes wrapper for Windows.

Loads a J2534 v04.04 driver DLL (e.g. the Topdon RLINK driver) and exposes
just enough of the API to do ISO15765 (UDS-over-CAN) diagnostic requests.

Read-only by design: this module only opens a channel, sets up filters, and
sends/receives messages. It never erases or writes ECU memory.

Windows + CPython only. The J2534 driver is a native DLL, so this cannot run
on Linux/Mac.
"""

import ctypes
import sys
from ctypes import c_ulong, c_long, c_char, c_char_p, c_void_p, POINTER, Structure, byref


# --- J2534 constants -------------------------------------------------------

# Protocol IDs
CAN = 5
ISO15765 = 6

# Connect flags
CAN_29BIT_ID = 0x00000100

# TxFlags
ISO15765_FRAME_PAD = 0x00000040
CAN_29BIT_ID_TX = 0x00000100

# RxStatus bits
TX_MSG_TYPE = 0x00000001          # this is a transmit confirmation, not real data
START_OF_MESSAGE = 0x00000002     # ISO15765 first-frame indication, not real data

# Filter types
PASS_FILTER = 1
BLOCK_FILTER = 2
FLOW_CONTROL_FILTER = 3

# Return codes
STATUS_NOERROR = 0

# Ioctl IDs
GET_CONFIG = 0x01
SET_CONFIG = 0x02
CLEAR_MSG_FILTERS = 0x0A


class PASSTHRU_MSG(Structure):
    _fields_ = [
        ("ProtocolID", c_ulong),
        ("RxStatus", c_ulong),
        ("TxFlags", c_ulong),
        ("Timestamp", c_ulong),
        ("DataSize", c_ulong),
        ("ExtraDataIndex", c_ulong),
        ("Data", c_char * 4128),
    ]


class J2534Error(Exception):
    pass


class J2534:
    def __init__(self, dll_path):
        self.dll_path = dll_path
        self.dll = ctypes.WinDLL(dll_path)
        self.device_id = c_ulong(0)
        self.channel_id = c_ulong(0)
        self._bind()

    def _bind(self):
        d = self.dll
        d.PassThruOpen.argtypes = [c_void_p, POINTER(c_ulong)]
        d.PassThruOpen.restype = c_long
        d.PassThruClose.argtypes = [c_ulong]
        d.PassThruClose.restype = c_long
        d.PassThruConnect.argtypes = [c_ulong, c_ulong, c_ulong, c_ulong, POINTER(c_ulong)]
        d.PassThruConnect.restype = c_long
        d.PassThruDisconnect.argtypes = [c_ulong]
        d.PassThruDisconnect.restype = c_long
        d.PassThruReadMsgs.argtypes = [c_ulong, POINTER(PASSTHRU_MSG), POINTER(c_ulong), c_ulong]
        d.PassThruReadMsgs.restype = c_long
        d.PassThruWriteMsgs.argtypes = [c_ulong, POINTER(PASSTHRU_MSG), POINTER(c_ulong), c_ulong]
        d.PassThruWriteMsgs.restype = c_long
        d.PassThruStartMsgFilter.argtypes = [
            c_ulong, c_ulong,
            POINTER(PASSTHRU_MSG), POINTER(PASSTHRU_MSG), POINTER(PASSTHRU_MSG),
            POINTER(c_ulong),
        ]
        d.PassThruStartMsgFilter.restype = c_long
        d.PassThruGetLastError.argtypes = [c_char_p]
        d.PassThruGetLastError.restype = c_long

    def _check(self, rc, where):
        if rc != STATUS_NOERROR:
            buf = ctypes.create_string_buffer(128)
            try:
                self.dll.PassThruGetLastError(buf)
                detail = buf.value.decode(errors="replace")
            except Exception:
                detail = ""
            raise J2534Error(f"{where} failed (rc={rc}) {detail}")

    def open(self):
        self._check(self.dll.PassThruOpen(None, byref(self.device_id)), "PassThruOpen")

    def connect_iso15765(self, baud=500000, flags=0):
        self._check(
            self.dll.PassThruConnect(self.device_id, ISO15765, flags, baud, byref(self.channel_id)),
            "PassThruConnect",
        )

    def add_flow_control_filter(self, req_id, resp_id, extended=False):
        """Set up the ISO15765 flow-control filter that binds request/response CAN IDs."""
        def mk(can_id):
            m = PASSTHRU_MSG()
            m.ProtocolID = ISO15765
            m.TxFlags = ISO15765_FRAME_PAD | (CAN_29BIT_ID_TX if extended else 0)
            idb = can_id.to_bytes(4, "big")
            m.Data = idb + b"\x00" * (4128 - 4)
            m.DataSize = 4
            return m

        mask = mk(0xFFFFFFFF)
        patt = mk(resp_id)
        flow = mk(req_id)
        fid = c_ulong(0)
        self._check(
            self.dll.PassThruStartMsgFilter(
                self.channel_id, FLOW_CONTROL_FILTER,
                byref(mask), byref(patt), byref(flow), byref(fid),
            ),
            "PassThruStartMsgFilter",
        )
        return fid.value

    def write(self, req_id, payload, extended=False, timeout=1000):
        m = PASSTHRU_MSG()
        m.ProtocolID = ISO15765
        m.TxFlags = ISO15765_FRAME_PAD | (CAN_29BIT_ID_TX if extended else 0)
        data = req_id.to_bytes(4, "big") + bytes(payload)
        m.Data = data + b"\x00" * (4128 - len(data))
        m.DataSize = len(data)
        n = c_ulong(1)
        self._check(self.dll.PassThruWriteMsgs(self.channel_id, byref(m), byref(n), timeout),
                    "PassThruWriteMsgs")

    def read_one(self, timeout=1000):
        """Read a single real (non-indication) response. Returns the UDS payload bytes
        (CAN-ID stripped) or None on timeout / only-indications."""
        import time
        deadline = time.time() + timeout / 1000.0
        while time.time() < deadline:
            m = PASSTHRU_MSG()
            m.ProtocolID = ISO15765
            n = c_ulong(1)
            rc = self.dll.PassThruReadMsgs(self.channel_id, byref(m), byref(n),
                                           max(1, int((deadline - time.time()) * 1000)))
            if rc != STATUS_NOERROR or n.value == 0:
                continue
            # Skip Tx confirmations and ISO15765 first-frame indications.
            if m.RxStatus & (TX_MSG_TYPE | START_OF_MESSAGE):
                continue
            data = bytes(m.Data[:m.DataSize])
            if len(data) < 4:
                continue
            return data[4:]  # strip the 4-byte CAN ID header
        return None

    def disconnect(self):
        if self.channel_id.value:
            self.dll.PassThruDisconnect(self.channel_id)
            self.channel_id = c_ulong(0)

    def close(self):
        self.disconnect()
        if self.device_id.value:
            self.dll.PassThruClose(self.device_id)
            self.device_id = c_ulong(0)

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *a):
        self.close()


def find_drivers():
    """Enumerate installed J2534 v04.04 drivers from the Windows registry.
    Returns a list of (vendor_name, dll_path) tuples."""
    if sys.platform != "win32":
        return []
    import winreg
    results = []
    roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\PassThruSupport.04.04"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\PassThruSupport.04.04"),
    ]
    for hive, path in roots:
        try:
            base = winreg.OpenKey(hive, path)
        except OSError:
            continue
        i = 0
        while True:
            try:
                sub = winreg.EnumKey(base, i)
            except OSError:
                break
            i += 1
            try:
                k = winreg.OpenKey(base, sub)
                name, _ = winreg.QueryValueEx(k, "Name")
                dll, _ = winreg.QueryValueEx(k, "FunctionLibrary")
                results.append((name, dll))
            except OSError:
                continue
    return results
