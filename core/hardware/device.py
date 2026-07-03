from dataclasses import dataclass, field


@dataclass
class HardwareDevice:

    id: str = ""

    name: str = ""

    manufacturer: str = ""

    model: str = ""

    type: str = ""

    online: bool = False

    properties: dict = field(default_factory=dict)
