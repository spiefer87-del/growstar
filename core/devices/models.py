from dataclasses import dataclass, field
from typing import Dict


@dataclass
class Device:

    id: str = ""

    name: str = ""

    manufacturer: str = ""

    model: str = ""

    ip: str = ""

    mac: str = ""

    firmware: str = ""

    online: bool = False

    properties: Dict = field(default_factory=dict)
