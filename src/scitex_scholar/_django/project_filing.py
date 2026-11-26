"""Project filing for the Library: validate, provision, file, and filter.

A project is a filing location ``<library_root>/<project>/`` holding
``<library_id> -> ../MASTER/<library_id>`` links. The SDK provider owns
project identity and access; Scholar owns this library layout.

``views`` re-exports the underscore names below, so existing imports keep
working.
"""

from pathlib import Path


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


def _assert_safe_project_name(project: str) -> str:
    """A project filing/filter target is a single path component.

    Same jail class as ``_assert_safe_library_id``: a project name becomes
    ``<library_root>/<project>/``, so a separator, NUL, or traversal token
    would escape the library root. The refusal message is FIXED -- it never
    carries the value (same reflection class as the library_id echoes).
    Reserved store names (MASTER, downloads, ...) are refused too: they are
    real directories under the root but never projects, and the picker
    filter excludes them for the same reason.

    The SDK header picker navigates with ``?project=<owner>/<slug>`` (the
    provider id contract), so a value carrying exactly one ``owner/``
    prefix is accepted by filtering on its last component -- the slug is
    the filing directory, the owner is identity context, not a path.
    Anything else with a separator still fails closed.
    """
    from scitex_scholar.storage._project_reconcile import RESERVED_LIBRARY_DIRS

    if not isinstance(project, str):
        raise ValueError("unsafe project name: not a string")
    if "\\" in project or "\x00" in project:
        raise ValueError("unsafe project name: not a single path component")
    # Accept the SDK picker id form ``owner/slug``: the slug (last
    # component) is the filing directory. Deeper paths stay refused.
    parts = project.split("/")
    if len(parts) == 2 and all(parts):
        project = parts[1]
    elif not project or "/" in project:
        raise ValueError("unsafe project name: not a single path component")
    if project in (".", ".."):
        raise ValueError("unsafe project name: traversal token")
    if project.upper() in {name.upper() for name in RESERVED_LIBRARY_DIRS}:
        raise ValueError("unsafe project name: reserved store name")
    return project


def _checked_project_dir(root: Path, project: str, *, request=None) -> Path:
    """Validate a filing/filter target and return its directory.

    Unsafe, reserved, non-directory and symlinked targets fail before a paper
    is written. With a request, a missing directory may be provisioned only
    for a project offered by that request's SDK provider. Without a request,
    this remains a check of an existing directory.
    """
    name = _assert_safe_project_name(project)
    pdir = root / name
    if request is not None and not pdir.exists() and not pdir.is_symlink():
        from .views import _project_provider

        return ensure_project_filing(
            root, name, project, request, _project_provider(request)
        )
    if pdir.is_symlink() or not pdir.is_dir():
        raise ValueError("unknown project: no such project in this library")
    return pdir


def _file_paper_into_project(root: Path, library_id: str, project: str) -> None:
    """File a saved paper under ``<root>/<project>/`` (project sync).

    Creates ``<project>/<library_id> -> ../MASTER/<library_id>`` and stamps
    ``container.projects`` via the existing reconcile verb. The link name is
    the validated library_id (safe, unique); membership and reconcile are
    name-agnostic, so no readable-name machinery is needed here.

    The project directory MUST already exist: callers check it with
    ``_checked_project_dir`` BEFORE the save. A real file occupying the link
    path, or a symlink failure, raises OSError (fail loud, fixed message).
    """
    from scitex_scholar.storage._project_reconcile import add_project_to_master

    from .views import _assert_safe_library_id

    pdir = _checked_project_dir(root, project)
    master_id = _assert_safe_library_id(library_id)
    link = pdir / master_id
    for existing in pdir.iterdir():
        if not existing.is_symlink() or existing == link:
            continue
        try:
            if existing.resolve().name == master_id:
                existing.unlink()
        except (OSError, RuntimeError):
            continue
    if link.is_symlink():
        try:
            resolved = link.resolve().name == master_id
        except (OSError, RuntimeError):
            resolved = False
        if resolved:
            add_project_to_master(root, master_id, pdir.name)
            return
        link.unlink()
    elif link.exists():
        raise OSError("cannot file into project: link path is occupied")
    link.symlink_to(f"../MASTER/{master_id}")
    add_project_to_master(root, master_id, pdir.name)


def listing_project_filter(project: str) -> str:
    """Resolve a Library listing's ``?project=`` to the filing name to filter on.

    Returns ``""`` for no selection. An unsafe value raises ``ValueError``
    (fixed message, never the value).

    A selected project lists ONLY the papers filed under it, whether or not
    its folder exists yet. A project created on the host has no folder until
    its first save (issue #312); it has filed nothing, so it lists nothing.
    Falling back to the whole library there showed other projects' papers
    under the new selection. Membership comes from real ``<project>/`` link
    folders only, so a symlinked or missing folder contributes no rows.
    """
    project = (project or "").strip()
    if not project:
        return ""
    return _assert_safe_project_name(project)
