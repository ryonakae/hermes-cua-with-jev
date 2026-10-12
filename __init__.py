if __package__:
    from .hermes_cua_with_jev.plugin import register
else:
    from hermes_cua_with_jev.plugin import register

__all__ = ["register"]
