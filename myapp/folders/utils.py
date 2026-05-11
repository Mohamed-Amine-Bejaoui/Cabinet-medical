def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.is_staff)