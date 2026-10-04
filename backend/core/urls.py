from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ClothRollViewSet,
    DipRunViewSet,
    LoftViewSet,
    PassTokenViewSet,
    dashboard_stats,
)

router = DefaultRouter()
router.register("lofts", LoftViewSet, basename="loft")
router.register("rolls", ClothRollViewSet, basename="roll")
router.register("dips", DipRunViewSet, basename="dip")
router.register("pass-tokens", PassTokenViewSet, basename="pass-token")

urlpatterns = [
    path("dashboard/", dashboard_stats, name="dashboard"),
    path("", include(router.urls)),
]
