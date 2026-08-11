# Paket yüzeyi BİLEREK burada: `import database` diyen bir çağıran
# `database.db` ve `database.init_db`'yi ayrıca import etmek zorunda
# kalmasın. Kullanılmıyor görünmeleri normal — noqa bu yüzden.
from . import db  # noqa: F401
from . import init_db  # noqa: F401
