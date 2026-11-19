"""Create filing directories for projects authorized by the SDK provider."""


def ensure_project_filing(root, name, project_id, request, provider):
    """Provision a missing collection only for a selectable project.

    The provider owns project identity/access, while Scholar owns its library
    layout. A bare slug may also identify the authenticated user's own project
    when the mounted provider publishes canonical ``owner/slug`` identifiers.
    """
    allowed = {entry.id for entry in provider.list_projects(request)}
    user = getattr(request, "user", None)
    own_id = None
    if user is not None and getattr(user, "is_authenticated", False):
        own_id = f"{user.username}/{name}"
    if project_id not in allowed and not (
        "/" not in project_id and own_id is not None and own_id in allowed
    ):
        raise ValueError("unknown project: no such project in this library")

    directory = root / name
    if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
        raise ValueError("unknown project: no such project in this library")
    directory.mkdir(parents=True, exist_ok=True)
    if directory.is_symlink():
        raise ValueError("unknown project: no such project in this library")
    return directory
