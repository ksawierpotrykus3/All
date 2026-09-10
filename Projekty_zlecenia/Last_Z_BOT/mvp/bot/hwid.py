
import hashlib
import logging
import platform
import subprocess
from functools import lru_cache

logger = logging.getLogger(__name__)


def _machine_guid() -> str:
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        ) as key:
            return str(winreg.QueryValueEx(key, "MachineGuid")[0])
    except Exception as exc:
        logger.debug("MachineGuid read failed: %s", exc)
        return ""


def _smbios_uuid() -> str:
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_ComputerSystemProduct).UUID",
            ],
            text=True,
            timeout=5,
        )
        return out.strip()
    except Exception as exc:
        logger.debug("SMBIOS UUID read failed: %s", exc)
        return ""


@lru_cache(maxsize=1)
def get_hwid() -> str:
    guid = _machine_guid()
    uuid_ = _smbios_uuid()
    parts = [p for p in (guid, uuid_) if p]
    if not parts:
        parts = [platform.node()]
    raw = ":".join(parts)
    if not raw:
        raise RuntimeError(
            "Could not obtain any hardware identifier (MachineGuid/SMBIOS/hostname)"
        )
    hwid = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return hwid
