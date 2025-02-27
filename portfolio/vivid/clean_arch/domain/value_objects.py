from enum import Enum, unique


@unique
class Lang(str, Enum):
    EN = 'en'
    DE = 'de'
    FR = 'fr'
    ES = 'es'
    IT = 'it'
