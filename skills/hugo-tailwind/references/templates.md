# Templates, content and images

Applies to Hugo v0.146+ (new template system).

## Contents
1. Layout names and lookup
2. Base template and blocks
3. Partials
4. Shortcodes
5. Render hooks
6. Content organisation and page bundles
7. Menus and navigation
8. Images
9. Migrating old layout names

## 1. Layout names and lookup

A template file name combines identifiers: page kind (`home`, `page`, `section`, `taxonomy`, `term`), standard layout (`list`, `single`, `all`), a custom `layout` from front matter, language, output format and suffix — e.g. `home.html`, `term.html`, `all.en.html`, `home.rss.xml`.

Weighting, most important first: custom layout → page kind → `list`/`single` → output format → `all` → language → media type → page path → `type`.

**Folders are page paths.** Any folder in `layouts/` not starting with `_` matches a content path, and closer matches win:

```text
layouts/
├── baseof.html
├── home.html
├── page.html
├── section.html
├── taxonomy.html
├── term.html
├── _partials/
├── _shortcodes/
├── _markup/render-link.html          # all links
├── blog/
│   ├── page.html                     # posts under /blog/
│   └── section.html                  # /blog/ listing
└── docs/
    ├── baseof.html                   # base for /docs/ and below
    └── _markup/render-link.html      # links inside /docs/ only
```

Target one page: front matter `layout = 'contact'` → `layouts/contact.html` (or `layouts/<section>/contact.html`). `type = 'x'` replaces the section folder in the lookup.

## 2. Base template and blocks

```go-html-template
{{/* layouts/baseof.html */}}
<!doctype html>
<html lang="{{ site.Language.Locale }}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ if .IsHome }}{{ site.Title }}{{ else }}{{ .Title }} · {{ site.Title }}{{ end }}</title>
  {{ with .Description }}<meta name="description" content="{{ . }}">{{ end }}
  {{ partial "opengraph.html" . }}
  {{ with (templates.Defer (dict "key" "global")) }}{{ partial "css.html" . }}{{ end }}
</head>
<body class="min-h-screen bg-white text-slate-900 dark:bg-slate-950 dark:text-slate-100">
  {{ partial "header.html" . }}
  <main class="mx-auto max-w-3xl px-4 py-12">{{ block "main" . }}{{ end }}</main>
  {{ partial "footer.html" . }}
</body>
</html>
```

```go-html-template
{{/* layouts/page.html */}}
{{ define "main" }}
  <article class="prose dark:prose-invert">
    <h1>{{ .Title }}</h1>
    {{ with .Date }}<time datetime="{{ .Format "2006-01-02" }}">{{ .Format "2 January 2006" }}</time>{{ end }}
    {{ .Content }}
  </article>
{{ end }}
```

```go-html-template
{{/* layouts/section.html */}}
{{ define "main" }}
  <h1>{{ .Title }}</h1>
  {{ range (.Paginate .Pages).Pages }}
    {{ partial "card.html" . }}
  {{ end }}
  {{ partial "pagination.html" . }}
{{ end }}
```

Built-in partials that replaced `_internal` templates: `opengraph.html`, `twitter_cards.html`, `schema.html`, `google_analytics.html`, `disqus.html`, `pagination.html` — call with `{{ partial "<name>" . }}`; override by creating the same file in `_partials/`.

## 3. Partials

- Not context-aware: they get exactly what you pass. Pass `.` (the page) or a dict.
- Return values: `{{ return $x }}` at the end, call with `{{ $v := partial "fn.html" . }}`.
- Expensive and identical on every page (header, footer, menu) → `partialCached`:
  `{{ partialCached "footer.html" . }}`. Add variant keys when output differs, e.g. by language: `{{ partialCached "nav.html" . .Lang }}`.

## 4. Shortcodes

`layouts/_shortcodes/callout.html`:

```go-html-template
{{ $types := dict "info" "border-blue-500 bg-blue-50" "warn" "border-amber-500 bg-amber-50" }}
<aside class="my-6 border-l-4 p-4 {{ index $types (.Get "type" | default "info") }}">
  {{ .Inner | .Page.RenderString }}
</aside>
```

In content:

```markdown
{{< callout type="warn" >}}Inner text, **rendered** by RenderString.{{< /callout >}}
```

- `{{< >}}` — inner content is passed raw; render it yourself (`RenderString`) if it is Markdown.
- `{{% %}}` — inner content is rendered as Markdown by Hugo and the result is part of the page's Markdown (headings appear in the table of contents).
- Positional `.Get 0` or named `.Get "type"`, not both in one shortcode.

## 5. Render hooks

Override how Markdown elements render — in `layouts/_markup/`:

| File | Element |
|---|---|
| `render-link.html` | links — e.g. external links with `rel="noopener"` |
| `render-image.html` | images — e.g. responsive, processed images |
| `render-heading.html` | headings — e.g. anchor links |
| `render-codeblock-<lang>.html` | fenced code blocks of one language (e.g. `mermaid`) |
| `render-blockquote.html` | blockquotes, including GitHub-style alerts |

Prefer a render hook to a shortcode when authors should write plain Markdown.

## 6. Content organisation and page bundles

```text
content/
├── _index.md                 # home page content
├── about.md                  # single page
└── blog/
    ├── _index.md             # branch bundle: section page for /blog/
    └── my-post/
        ├── index.md          # leaf bundle: the page
        ├── cover.jpg         # page resource: .Resources.Get "cover.jpg"
        └── diagram.png
```

- `_index.md` = branch bundle (has children); `index.md` = leaf bundle (resources only).
- Front matter in TOML (`+++`) or YAML (`---`); keep one format per site. Useful fields: `title`, `date`, `draft`, `description`, `tags`, `weight`, `slug`, `aliases`, `params`.
- Archetypes (`archetypes/blog.md`) pre-fill front matter for `hugo new content blog/x.md`.
- Taxonomies: `tags` and `categories` are on by default; declare others under `[taxonomies]` in `hugo.toml`.

## 7. Menus and navigation

```toml
[menus]
  [[menus.main]]
    name = 'Blog'
    pageRef = '/blog'
    weight = 10
  [[menus.main]]
    name = 'About'
    pageRef = '/about'
    weight = 20
```

```go-html-template
<nav>
  {{ range site.Menus.main }}
    <a href="{{ .URL }}" class="{{ if $.IsMenuCurrent "main" . }}font-semibold{{ end }}">{{ .Name }}</a>
  {{ end }}
</nav>
```

Use `pageRef` (resolved and checked by Hugo) rather than `url` for internal pages.

## 8. Images

```go-html-template
{{ with .Resources.Get "cover.jpg" }}
  {{ $small := .Process "resize 640x webp" }}
  {{ $large := .Process "resize 1280x webp" }}
  <img src="{{ $large.RelPermalink }}"
       srcset="{{ $small.RelPermalink }} 640w, {{ $large.RelPermalink }} 1280w"
       sizes="(min-width: 768px) 768px, 100vw"
       width="{{ $large.Width }}" height="{{ $large.Height }}"
       alt="{{ $.Title }}" loading="lazy" decoding="async" class="rounded-lg">
{{ end }}
```

- `Resize`, `Fit`, `Fill`, `Crop`, `Process` (one spec string: action, size, format, quality). Shared images go in `assets/` and use `resources.Get`.
- Processed images are cached in the image cache; persist it in CI (`[caches.images] dir = ':cacheDir/images'`) and run `hugo build --gc` after removing or renaming images.
- Very large originals cost memory and time — scale them down before committing.

## 9. Migrating old layout names

| Old | New |
|---|---|
| `layouts/_default/*` | `layouts/*` |
| `layouts/partials/` | `layouts/_partials/` |
| `layouts/shortcodes/` | `layouts/_shortcodes/` |
| `layouts/index.html` | `layouts/home.html` |
| `layouts/_default/list-baseof.html` | `layouts/baseof.list.html` |
| `taxonomy.html` covering terms | add `term.html` (or use `list.html`) |
| `{{ template "_internal/opengraph.html" . }}` | `{{ partial "opengraph.html" . }}` |

Run `myhugofixer` (SKILL.md) for everything else that changed between versions.
