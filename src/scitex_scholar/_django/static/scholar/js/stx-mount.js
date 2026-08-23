// Mount-prefix base for every Scholar client call. SINGLE DECLARATION.
//
// These are classic <script> tags, not modules, so they share one global
// scope: declaring `const STX_MOUNT` in two files is a SyntaxError
// ("Identifier 'STX_MOUNT' has already been declared") that breaks the whole
// page, not just the second file. Hence one file, loaded first.
//
// scitex-app's `stx-mount` contract (scitex-app >= 0.8.0): the SERVER declares
// where the app is mounted; the browser joins endpoint names onto it.
//
// THE PREFIX NEVER ENDS IN "/". Root is "", embedded is "/apps/u/scholar".
// So ENDPOINT NAMES CARRY THE LEADING SLASH: STX_MOUNT + "/api/search".
//
// That convention was chosen by comparing each option's MISUSE, not its
// correct use -- both look identical when used correctly:
//     old ("/" base) + an endpoint written "/api/x"  ->  //api/x
//                                                    ->  https://api/x
//         a PROTOCOL-RELATIVE url: the request LEAVES THE ORIGIN carrying
//         whatever the fetch carries.
//     new ("" base)  + an endpoint written "api/x"   ->  /api/x  (404, right host)
// The old convention's likeliest mistake exfiltrates; the new one 404s.
//
// WE THROW rather than defaulting. scholar's first prefix fix nearly shipped
// as a silent no-op: nothing emitted the marker, the client fell back to root,
// and the diff looked complete. A missing marker is a broken contract, and it
// should fail where it breaks.
//
// NOT EVERY URL TAKES THIS BASE. Platform routes (/platform/api/..., /apps/...)
// live at the SERVER ROOT, not under this app's mount, and must stay
// root-absolute. Scholar currently calls none of them -- verified, no
// "platform/" reference in any scholar script.
const _stxMountEl = document.querySelector('meta[name="stx-mount"]');
if (!_stxMountEl) {
  throw new Error(
    "stx-mount marker missing: the page was not served by a scitex-app " +
    "shell, or the template stopped emitting it. Scholar cannot build API " +
    "URLs without knowing its mount prefix."
  );
}
const STX_MOUNT = _stxMountEl.content;
