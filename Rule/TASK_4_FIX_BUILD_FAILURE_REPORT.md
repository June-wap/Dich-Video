# Task 4 — Fix Build Failure (voiceProfileService.test.ts strict-null errors)

**Status: EXECUTED (fix applied) — full project `npm run build` / `npx vitest run` totals are NOT VERIFIED (two independent execution blockers this turn, both explained below). A scoped, real compiler reproduction of the exact error/fix IS verified (details below).**

## Changed files

- `frontend/src/services/voiceProfileService.test.ts` — the only file changed. Committed to `D:\Tool Dich Cho Khach\...` and verified byte-for-byte via fresh stage-back + `cmp`.

No production code was touched (per requirements) — `voiceProfileService.ts` and `httpClient.ts` are unchanged; this was purely a test-file typing fix.

## Root cause

`httpClient.ts`'s `apiFetch` is declared as:
```ts
export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T>
```
The default value on `options` makes it an **optional** parameter in `apiFetch`'s type signature, so `Parameters<typeof apiFetch>` is `[path: string, options?: ApiFetchOptions]`. Vitest's `MockContext<T>.calls` is typed as `Parameters<T>[]`, so `apiFetchSpy.mock.calls[0]`'s second element inherits that optionality: `ApiFetchOptions | undefined`. The test file destructured/indexed straight into `.method`/`.body` on that value, which is exactly the reported error shape - not an indexing-safety issue (`noUncheckedIndexedAccess` isn't even set in `tsconfig.app.json`), but the optional-parameter-in-a-tuple pattern.

## Fix

Added explicit runtime narrowing at each of the two call sites that touch `options` (both in the `create()` tests), instead of a non-null assertion (which asserts without proving anything) or any type-check suppression:

```ts
const [path, options] = apiFetchSpy.mock.calls[0];
...
if (!options) {
  throw new Error('apiFetch was called without an options argument');
}
expect(options.method).toBe('POST');
```

and, in the second test:

```ts
const [, options] = apiFetchSpy.mock.calls[0];
if (!options) {
  throw new Error('apiFetch was called without an options argument');
}
const form = options.body as FormData;
```

This throws (failing the test loudly, with a clear message) if `apiFetch` were somehow ever called without an options argument - which proves the value to the compiler via real control-flow narrowing, matching the "explicit assertions/narrowing that prove the mocked call and options exist" requirement. No `any`, no `@ts-ignore`, no relaxed compiler options, and test intent (what's being asserted) is unchanged - only the null-safety of getting there changed.

## What I verified, and how

I could not run the project's real `npm run build` / `npx vitest run` this turn - both available execution paths failed, independently:

1. **`device_bash` (the user's Windows machine) is still broken** - re-tested at the start of this turn and failed with the same "Windows update / Plan9 drive" mount error as every previous check this session.
2. **This cloud sandbox's network egress does not allow `registry.npmjs.org`** - I attempted to reproduce the full project build/test run here instead (staged the entire `frontend/` source tree + lockfiles into the cloud workspace and tried `npm install`), and it failed with `403 Forbidden - Host not in allowlist: registry.npmjs.org`. This is an org-level egress policy, not a transient error, so I did not attempt to work around it (e.g. fetching packages from a CDN mirror).

Rather than stop at BLOCKED again, I isolated the **specific compiler behavior in question** - which does not depend on the rest of the project's dependency tree - and reproduced it directly with a TypeScript compiler that **is** available in this sandbox: the globally-installed `typescript@6.0.3` (which satisfies the project's own `"typescript": "~6.0.2"` range). I wrote a minimal, dependency-free `.ts` file that reconstructs the exact type shape involved (an `apiFetch`-like function with a defaulted second parameter, and a `Parameters<...>[]`-typed `calls` array, exactly mirroring vitest's `MockContext.calls`), and ran `tsc --strict --noEmit` against both the original (reported) code shape and the fixed shape:

- **Before the fix:** `tsc --strict` reports `error TS18048: 'options' is possibly 'undefined'.` at the exact line pattern the report described.
- **After the fix:** `tsc --strict` exits `0` with zero errors.

This proves the fix's TypeScript-level correctness with a real compiler run (not reasoning alone), scoped to exactly the mechanism in question. It is **not** a substitute for the full project build/test, which needs the project's real `tsconfig.app.json`, all its actual type dependencies, and vitest's own runtime - none of which I could reach this turn.

## Please run and report back

```bash
cd frontend
npm run build      # tsc -b && vite build
npx vitest run
```

If either surfaces anything else, send me the exact output and I'll fix the smallest root cause, per the instructions - I'm not declaring this checkpoint PASS myself either way.
