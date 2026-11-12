from .forms import LoginForm, RegistroUsuarioForm
from usuarios.forms import PasswordResetRequestForm


AUTH_TEMPLATE = "autenticacion/auth_portal.html"


def build_auth_context(request, active_mode, active_form=None):
    forms = {
        "login": LoginForm(request=request),
        "register": RegistroUsuarioForm(),
        "reset": PasswordResetRequestForm(),
    }
    if active_form is not None:
        forms[active_mode] = active_form

    return {
        "auth_mode": active_mode,
        "login_form": forms["login"],
        "registration_form": forms["register"],
        "password_reset_form": forms["reset"],
    }
