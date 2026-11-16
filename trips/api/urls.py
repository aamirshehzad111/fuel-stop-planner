from django.urls import path

from trips.api.views import TripPlanView

urlpatterns = [
    path("trips/plan/", TripPlanView.as_view(), name="trip-plan"),
]
