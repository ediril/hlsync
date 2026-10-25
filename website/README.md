# HLSync website

This directory is the complete shared-hosting document root. It requires PHP
8.3 and Apache; there is no build step or package installation.

For local rendering without managing the user's application server:

```console
php -S 127.0.0.1:8080 -t website
```

Deploy the contents of `website/`, including `.htaccess`, directly into the
site's configured remote document root. The page uses Google Fonts for Space
Mono and IBM Plex Mono; Apache's content security policy permits only those
font resources in addition to same-origin assets.

The page derives its canonical URL from the validated request host and exposes
Open Graph and Twitter large-image metadata for `assets/social-preview.jpg`.
It also provides search-engine directives, SoftwareApplication JSON-LD, and a
v2 `rel="describedby"` link to the root `llms.txt` project summary.
The existing hook mark is provided as SVG and 32-pixel PNG favicons, a
multi-size root `favicon.ico`, and a 180-pixel Apple touch icon.

The homepage includes a licensing and pricing section at `#pricing`, with use
at no charge under PolyForm Strict 1.0.0 and commercial licensing by inquiry.
The copy identifies noncommercial purposes, the listed personal uses without
anticipated commercial application, and use by the listed organizations
regardless of funding source or obligations resulting from funding.
Commercial pricing is not published; the contact links open an email to Emrah
Diril. The JSON-LD distinguishes the free offer from the commercial offer
without assigning a price to the latter. The repository `LICENSE` governs;
summaries grant no additional permissions. It grants no rights to modify,
redistribute, or create works based on HLSync.
