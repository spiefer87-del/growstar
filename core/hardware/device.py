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

    def to_dict(self):

        return {

            "id": self.id,

            "name": self.name,

            "manufacturer": self.manufacturer,

            "model": self.model,

            "type": self.type,

            "online": self.online

        }
