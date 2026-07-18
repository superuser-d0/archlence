# Geriye dönük uyumluluk: DashboardService bir ekran değil sorgu servisiydi,
# services/queries.py'ye taşındı.
from services.queries import DashboardService  # noqa: F401
