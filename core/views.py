
from django.views.generic import TemplateView
from core.mixins import PassIdPermissionMixin


class HomeView(PassIdPermissionMixin, TemplateView):
    template_name = "core/home.html"
    required_permission = "core.view_home"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context
