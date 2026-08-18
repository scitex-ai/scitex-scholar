// Mount-prefix base for every Scholar client call. SINGLE DECLARATION.
//
// These are classic <script> tags, not modules, so they share one global
// scope: declaring `const STX_MOUNT` in two files is a SyntaxError
// ("Identifier 'STX_MOUNT' has already been declared") that breaks the whole
// page, not just the second file. Hence one file, loaded first.
//
// scitex-app's `stx-mount` contract (scitex-app >= 0.7.0): the SERVER
// declares where the app is mounted; the browser joins relative endpoint
// names onto it. The value ALWAYS ends in "/", so endpoint names must not
// begin with one, and nothing here may strip or re-add it -- re-deriving a
// value the server already computed correctly is the nine-implementations
// problem one level down. A missing marker means standalone at root.
//
// Do NOT "simplify" call sites to plain relative URLs. A relative URL INFERS
// the base from wherever the document happens to sit, so it works mounted at
// "/scholar/" and 404s at "/scholar". Measured, both ways, 2026-08-18.
// Relative URLs are not prefix-safe, they are prefix-lucky.
const STX_MOUNT =
  document.querySelector('meta[name="stx-mount"]')?.content ?? "/";
