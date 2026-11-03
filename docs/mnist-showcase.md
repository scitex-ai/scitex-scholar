# MNIST showcase references

The worked project and Scholar's Library are separate stores. A manuscript or
bibliography copied into a project does not populate the user's Scholar
`MASTER/` catalog or its project membership links.

The explicit `scitex_scholar.showcase` adapter supplies four actual supporting
references: MNIST background (Le Cun et al.), scikit-learn, OpenML and Matplotlib.
The bundled `showcase/mnist.json` records primary publisher/author/arXiv/official
software URLs and the verification date. It contains no invented abstract,
citation count, impact factor, PDF or verification result. The JMLR article has
no fabricated DOI. This is a curated starting library, not a claim that an
existing manuscript cites these papers.

## Explicit admission

Resolve the authenticated user's durable home through the host's existing
`SCITEX_USER_HOME_PROVIDER` and authorize the project before calling this API.
Supply the canonical user library root and a **slug**, not a host filesystem
path or `owner/slug`. The helper performs no user or project discovery.

```python
from scitex_scholar.showcase import seed_mnist_library

# `authorized_library_root` and `authorized_project_slug` come from the caller's
# actual user/project capability checks, never untrusted browser paths.
plan = seed_mnist_library(
    authorized_library_root, project=authorized_project_slug
)
# An explicitly authorized bootstrap operation can apply the same plan:
result = seed_mnist_library(
    authorized_library_root, project=authorized_project_slug, dry_run=False
)
```

Default dry-run is standard-library/resource-read only. It creates no directory
or lock and does not instantiate PaperIO, an API client or a store. No GET route
seeds anything. This is a POSIX filesystem operation requiring flock, symlinks
and hardlinks, not a new host admission mechanism.

Apply serializes **new** entries through the real `Paper` and `PaperIO` into a
private stage, then publishes missing metadata without replacing existing
files. It locks the library directory before inspecting existing records, so
concurrent jobs cannot mistake an in-progress publication for a conflict. This
requires no new lock file when an incompatible existing library is refused.
It matches existing DOI/title identities, preserves their metadata and
annotations byte for byte, honors existing readable project links and adds
only missing standard links into `MASTER/`. New records carry their project;
existing metadata remains untouched because filesystem links are the library's
authoritative membership. It adds deterministic `.mnist-showcase-v1.json`
provenance to that library project directory. Existing conflicting files,
provenance or escaping directory/metadata links refuse admission.

Repeated successful applies leave file/link bytes unchanged. Publication is
atomic **per file**, not a transaction across the batch: an interrupted job can
leave valid additions. A repeat finishes compatible additions; incomplete or
conflicting entries require operator review. Nothing rolls back by deleting
user data. The shared PostgreSQL derived index is not opened or rebuilt.

## Other apps and existing work

The manifest distinguishes the actually computed Live Paper bundle
(`examples/make_example_project_mnist.py`: OpenML `mnist_784` version 1,
logistic regression and k-nearest neighbors) from the research template's
illustrative torchvision/UMAP/SVM scripts. This adapter does not execute or
validate those computations. Read the selected project's `provenance.yaml`
and claims status for its actual scientific evidence.

`mnist_reference_bibtex()` exports the **same catalog** through Scholar's
existing formatter, which escapes plain bibliographic text for TeX while
preserving identifiers and URLs. A consumer may explicitly add it as a separate bibliography;
the helper never overwrites the project's consumer-owned Writer bibliography
or imports its placeholder `10.1234/...` citations as research. It does not
fabricate Stats observations, FigRecipe recipes, Writer manuscripts or Journal
decisions. Those apps must consume real, separately qualified artifacts.

## Evidence

The `tests/scitex_scholar/showcase/` and
`tests/integration/scitex_scholar/showcase/` tests use owned temporary libraries: real
Paper/PaperIO, two native seed processes, production user-home Web resolution,
Library reads, traversal/symlink/conflict refusals and a cold no-site dry-run.
No user library, model, paid API or service is called by those tests.
