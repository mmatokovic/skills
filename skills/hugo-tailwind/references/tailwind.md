# Tailwind CSS v4 in Hugo

Hugo runs the Tailwind CLI itself through `css.TailwindCSS`. Tailwind scans `hugo_stats.json` — the classes, IDs and tags Hugo found in the rendered HTML — so only used classes are generated.

## Contents
1. Setup (from the Hugo docs)
   - npm packages in a theme or module
2. Theme tokens, fonts, dark mode
3. Typography for Markdown content
4. Classes Tailwind cannot see
5. Components without a framework
6. Options

## 1. Setup

Install (v0.161+ requires the npm CLI; the standalone binary is unsupported):

```sh
npm install --save-dev tailwindcss @tailwindcss/cli @tailwindcss/typography
```

`hugo.toml`:

```toml
[build]
  [build.buildStats]
    enable = true
  [[build.cachebusters]]
    source = 'assets/notwatching/hugo_stats\.json'
    target = 'css'
  [[build.cachebusters]]
    source = '(postcss|tailwind)\.config\.js'
    target = 'css'
[module]
  [[module.mounts]]
    source = 'assets'
    target = 'assets'
  [[module.mounts]]
    disableWatch = true
    source = 'hugo_stats.json'
    target = 'assets/notwatching/hugo_stats.json'
[security.exec]
  allow = ['^(dart-)?sass$', '^go$', '^git$', '^node$', '^postcss$', '^tailwindcss$']
```

The `hugo_stats.json` mount has `disableWatch` and the cachebuster is what triggers the CSS rebuild — this pair avoids an endless rebuild loop.

`assets/css/main.css`:

```css
@import "tailwindcss";
@plugin "@tailwindcss/typography";
@source "hugo_stats.json";
```

`@source "hugo_stats.json"` is required when `hugo_stats.json` is in `.gitignore` — Tailwind skips git-ignored files otherwise.

`layouts/_partials/css.html`:

```go-html-template
{{ with resources.Get "css/main.css" }}
  {{ $opts := dict "minify" (not hugo.IsDevelopment) }}
  {{ with . | css.TailwindCSS $opts }}
    {{ if hugo.IsDevelopment }}
      <link rel="stylesheet" href="{{ .RelPermalink }}">
    {{ else }}
      {{ with . | fingerprint }}
        <link rel="stylesheet" href="{{ .RelPermalink }}" integrity="{{ .Data.Integrity }}" crossorigin="anonymous">
      {{ end }}
    {{ end }}
  {{ end }}
{{ end }}
```

`layouts/baseof.html` — `templates.Defer` runs the partial after every page is rendered, so `hugo_stats.json` is complete:

```go-html-template
<head>
  {{ with (templates.Defer (dict "key" "global")) }}
    {{ partial "css.html" . }}
  {{ end }}
</head>
```

The Tailwind CLI may only read paths in `security.node.permissions.allowRead` (default: the project directory). Add parent paths there for a monorepo with a hoisted `node_modules`.

If the build fails on Node permissions, also allow Tailwind's native addon and worker:

```toml
[security.node.permissions]
  allowAddons = ['tailwindcss']
  allowWorker = ['tailwindcss']
```

With pnpm, set `nodeLinker: hoisted` in `pnpm-workspace.yaml` so Hugo finds the Tailwind CLI in `node_modules`.

### npm packages in a theme or module

Since Hugo v0.159 a theme or module lists its npm packages in a normal `package.json` at its root. `package.hugo.json` is still read (and wins if both exist), but only for backward compatibility; rename it to `package.json`.

`hugo mod npm pack` in the site collects the packages of every module, including a theme in `themes/` set with `theme = '…'`, into `packages/hugoautogen/package.json`, and adds `"workspaces": ["packages/hugoautogen"]` to the site's `package.json`. Then run `npm install`. Packages the site already lists itself are left out of the generated file.

- pnpm ignores the `workspaces` field; it reads workspaces from `pnpm-workspace.yaml`. A site that lists its packages itself does not need `hugo mod npm pack` at all.
- A `"comments": { "devDependencies": { "<pkg>": "<theme>" } }` block in a site's `package.json` is output of the pre-v0.159 command and can be deleted.
- Dependabot can update a theme's `package.json` (npm ecosystem) but never read `package.hugo.json`, which is how the two drift apart.

## 2. Theme tokens, fonts, dark mode

v4 is configured in CSS — there is no `tailwind.config.js`.

```css
@import "tailwindcss";
@plugin "@tailwindcss/typography";
@source "hugo_stats.json";

@theme {
  --color-brand-50: oklch(0.97 0.02 250);
  --color-brand-500: oklch(0.55 0.18 250);
  --color-brand-900: oklch(0.28 0.09 250);
  --font-sans: "Inter", ui-sans-serif, system-ui, sans-serif;
}

/* class-based dark mode instead of the default prefers-color-scheme */
@custom-variant dark (&:where(.dark, .dark *));
```

Each `--color-brand-*` token generates `bg-brand-500`, `text-brand-900` and so on. Self-host fonts under `static/fonts/` (or a page-independent `assets/` file) and declare `@font-face` in `main.css`.

For class-based dark mode, set the class before first paint to avoid a flash — an inline script in `<head>` that reads `localStorage` and `prefers-color-scheme` and toggles `document.documentElement.classList`.

## 3. Typography for Markdown content

Wrap rendered Markdown in `prose`:

```go-html-template
<article class="prose prose-slate dark:prose-invert max-w-none lg:prose-lg">
  {{ .Content }}
</article>
```

Style elements inside prose with modifiers (`prose-a:text-brand-500`, `prose-img:rounded-lg`). For full control over one element type, use a render hook (`templates.md`) instead of fighting prose styles.

## 4. Classes Tailwind cannot see

Tailwind only generates classes that appear in `hugo_stats.json` (rendered HTML) or other `@source` files:

- **Added by JavaScript** (menu toggles, `hidden` → `flex`): safelist them — `@source inline("flex hidden rotate-180");` — or add them to an element that is rendered anyway.
- **Built from strings in templates** (`bg-{{ .Params.color }}-500`): works only for values actually rendered on some page. Prefer a map from param to complete class names:

  ```go-html-template
  {{ $colors := dict "info" "bg-blue-100 text-blue-900" "warn" "bg-amber-100 text-amber-900" }}
  <div class="{{ index $colors (.Get "type") }}">
  ```

- **In JS files under `assets/js/`**: `@source "../js";` (path relative to `main.css`).

## 5. Components without a framework

- Repeated markup → a partial (`_partials/card.html`), not `@apply`.
- `@apply` only for content you cannot add classes to (third-party HTML); prefer render hooks.
- Small interactivity: `<details>`/`<summary>`, or a short script bundled with `js.Build` from `assets/js/main.js`.
- Keep state in attributes the script toggles (`aria-expanded`, `hidden`, `data-shown`) and style it with Tailwind variants that appear in the markup (`group-aria-expanded:hidden`, `group-data-shown:opacity-100`), so no `@source inline` safelist is needed.
- Avoid Alpine.js for a couple of toggles: its standard build evaluates attribute expressions with `new Function`, which forces `'unsafe-eval'` into the Content Security Policy.

## 6. Options

Passed as a map: `css.TailwindCSS (dict "minify" true)`.

| Option | Default | Effect |
|---|---|---|
| `minify` | `false` | optimise and minify |
| `optimize` | `false` | optimise without minifying |
| `disableInlineImports` | `false` | keep `@import` statements as they are |
| `skipInlineImportsNotFound` | `false` | keep unresolved imports instead of failing |
| `importContext` | — | resolve `@import` through a resource getter first (v0.165+) |
