from app.adapters.bina_az import BinaAzAdapter
from app.adapters.binatap_az import BinatapAzAdapter
from app.adapters.emlak_az import EmlakAzAdapter
from app.adapters.ev10_az import Ev10AzAdapter
from app.adapters.vipemlak_az import VipemlakAzAdapter
from app.adapters.evv_az import EvvAzAdapter
from app.adapters.emlakbazari_az import EmlakbazariAzAdapter
from app.adapters.binam_az import BinamAzAdapter
# ebaz.az is a pure React SPA with no accessible API — disabled until they add SSR or a public API
# from app.adapters.ebaz_az import EbazAzAdapter

ALL_ADAPTERS = [
    BinaAzAdapter,
    BinatapAzAdapter,
    EmlakAzAdapter,
    Ev10AzAdapter,
    VipemlakAzAdapter,
    EvvAzAdapter,
    EmlakbazariAzAdapter,
    BinamAzAdapter,
]
