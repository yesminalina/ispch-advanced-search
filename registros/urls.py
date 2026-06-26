from django.urls import path
from . import views

app_name = "registros"

urlpatterns = [
    path("", views.search, name="search"),
    path("acerca-de/", views.about, name="about"),
]